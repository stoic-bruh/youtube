/**
 * Thumbnail routes — POST /thumbnails, GET /thumbnails, GET /thumbnails/:id,
 * DELETE /thumbnails/:id, GET /thumbnails/:id/file/:candidateId
 *
 * Post-Processing Engine — Thumbnail Engine. Shells out to
 * `services/youtube-factory-api/scripts/postprocess_cli.py thumbnail`, which
 * extracts real candidate frames via FFmpeg and scores them with Pillow
 * (sharpness/brightness/dominant color), mirroring the FastAPI/Celery path.
 */
import { Router, type Request, type Response } from "express";
import { db } from "@workspace/db";
import { thumbnailResults, renderResults, timelineResults } from "@workspace/db";
import { eq, and, desc } from "drizzle-orm";
import { z } from "zod";
import { randomUUID } from "crypto";
import { spawn } from "child_process";
import path from "path";
import fs from "fs/promises";

const router = Router();

const PYTHON_SERVICE_DIR = path.resolve(process.cwd(), "../../services/youtube-factory-api");
const PYTHON_BIN = process.env.RENDER_PYTHON_BIN || "/home/runner/workspace/.pythonlibs/bin/python3";
const POSTPROCESS_CLI = path.join(PYTHON_SERVICE_DIR, "scripts", "postprocess_cli.py");
const OUTPUT_DIR = process.env.POSTPROCESS_OUTPUT_DIR || "/tmp/postprocess_engine";
const THUMBNAIL_OUTPUT_DIR = path.join(OUTPUT_DIR, "thumbnails");

const TEMPLATES = [
  { id: "bold-title-bottom", label: "Bold Title (bottom band)", textRegion: "lower-third" },
  { id: "minimal-corner-badge", label: "Minimal Corner Badge", textRegion: "upper-third" },
  { id: "high-contrast-split", label: "High-Contrast Split", textRegion: "lower-third" },
];

const ThumbnailInputSchema = z.object({
  renderId: z.string().min(1),
  count: z.number().int().min(1).max(10).optional().default(3),
});

function ts(): string {
  return `[${new Date().toTimeString().slice(0, 8)}]`;
}

function toApi(t: typeof thumbnailResults.$inferSelect): object {
  return {
    id: t.id,
    renderId: t.renderId,
    status: t.status,
    candidates: t.candidates || [],
    selectedCandidateIds: t.selectedCandidateIds || [],
    templates: t.templates || [],
    titleOverlay: t.titleOverlay || {},
    brandColors: t.brandColors || [],
    logs: t.logs || [],
    errorMessage: t.errorMessage,
    createdAt: t.createdAt,
    updatedAt: t.updatedAt,
    completedAt: t.completedAt,
  };
}

async function addLog(id: string, level: string, msg: string): Promise<void> {
  const [current] = await db.select({ logs: thumbnailResults.logs }).from(thumbnailResults).where(eq(thumbnailResults.id, id));
  const logs: string[] = (current?.logs as string[]) || [];
  logs.push(`${ts()} ${level.padEnd(5)} ${msg}`);
  await db.update(thumbnailResults).set({ logs, updatedAt: new Date() }).where(eq(thumbnailResults.id, id));
}

function runPostprocessCli(subcommand: "subtitle" | "thumbnail", inputPath: string): Promise<any> {
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON_BIN, [POSTPROCESS_CLI, subcommand, inputPath], {
      cwd: PYTHON_SERVICE_DIR,
      env: { ...process.env, PYTHONPATH: PYTHON_SERVICE_DIR },
    });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d) => (stdout += d.toString()));
    proc.stderr.on("data", (d) => (stderr += d.toString()));
    proc.on("close", (code) => {
      try {
        const parsed = JSON.parse(stdout.trim().split("\n").pop() || "{}");
        if (code !== 0 && !parsed.error) {
          reject(new Error(`postprocess_cli.py (${subcommand}) exited with code ${code}: ${stderr.slice(-2000)}`));
          return;
        }
        resolve(parsed);
      } catch (err) {
        reject(new Error(`Failed to parse postprocess_cli.py output: ${err}. stdout=${stdout.slice(-2000)} stderr=${stderr.slice(-2000)}`));
      }
    });
    proc.on("error", (err) => reject(err));
  });
}

async function executeThumbnail(thumbnailId: string, renderId: string, count: number): Promise<void> {
  try {
    await db.update(thumbnailResults).set({ status: "running", updatedAt: new Date() }).where(eq(thumbnailResults.id, thumbnailId));
    await addLog(thumbnailId, "INFO", `Starting thumbnail extraction for render=${renderId}`);

    const [render] = await db.select().from(renderResults).where(eq(renderResults.id, renderId));
    if (!render) throw new Error(`Source render ${renderId} no longer exists`);
    const videoPath = (render.renderOutput as any)?.localPath;
    if (!videoPath) throw new Error(`Render output file not found for ${renderId}`);
    await fs.access(videoPath);

    const durationSeconds = (render.renderOutput as any)?.durationSeconds;
    await addLog(thumbnailId, "INFO", "Phase 1/2 — Extracting real candidate frames via FFmpeg");
    await fs.mkdir(THUMBNAIL_OUTPUT_DIR, { recursive: true });
    const inputPath = path.join(THUMBNAIL_OUTPUT_DIR, `${thumbnailId}.input.json`);
    await fs.writeFile(
      inputPath,
      JSON.stringify({
        videoPath,
        count,
        durationMs: durationSeconds ? Math.round(durationSeconds * 1000) : undefined,
        outputDir: THUMBNAIL_OUTPUT_DIR,
        idPrefix: thumbnailId,
      }),
    );

    const result = await runPostprocessCli("thumbnail", inputPath);
    for (const line of result.logs || []) {
      await addLog(thumbnailId, "INFO", line);
    }
    if (result.error) throw new Error(result.error);

    await addLog(thumbnailId, "INFO", "Phase 2/2 — Scoring complete, best candidates selected");

    let titleOverlay: object = { fontFamily: "Anton", color: "#FFFFFF", strokeColor: "#000000", strokeWidth: 6 };
    if (render.timelineId) {
      const [timeline] = await db.select().from(timelineResults).where(eq(timelineResults.id, render.timelineId));
      titleOverlay = { ...titleOverlay, text: (timeline as any)?.title || (timeline as any)?.topic || null };
    }

    await db.update(thumbnailResults).set({
      status: "completed",
      candidates: result.candidates,
      selectedCandidateIds: result.selectedCandidateIds,
      templates: TEMPLATES,
      titleOverlay,
      brandColors: result.brandColors,
      completedAt: new Date(),
      updatedAt: new Date(),
    }).where(eq(thumbnailResults.id, thumbnailId));
  } catch (err: any) {
    const errMsg = err?.message || String(err);
    await addLog(thumbnailId, "ERROR", `Thumbnail generation failed: ${errMsg}`);
    await db.update(thumbnailResults).set({ status: "failed", errorMessage: errMsg, updatedAt: new Date() }).where(eq(thumbnailResults.id, thumbnailId));
  }
}

// GET /thumbnails
router.get("/", async (req: Request, res: Response) => {
  const limit = Math.min(Number(req.query.limit) || 50, 200);
  const offset = Number(req.query.offset) || 0;
  const filters = [];
  if (req.query.renderId) filters.push(eq(thumbnailResults.renderId, String(req.query.renderId)));
  if (req.query.status) filters.push(eq(thumbnailResults.status, String(req.query.status)));

  const where = filters.length ? and(...filters) : undefined;
  const rows = where
    ? await db.select().from(thumbnailResults).where(where).orderBy(desc(thumbnailResults.createdAt))
    : await db.select().from(thumbnailResults).orderBy(desc(thumbnailResults.createdAt));

  const total = rows.length;
  res.json({ items: rows.slice(offset, offset + limit).map(toApi), total });
});

// POST /thumbnails
router.post("/", async (req: Request, res: Response) => {
  const parse = ThumbnailInputSchema.safeParse(req.body);
  if (!parse.success) { res.status(400).json({ error: parse.error.flatten() }); return; }
  const input = parse.data;

  const [render] = await db.select().from(renderResults).where(eq(renderResults.id, input.renderId));
  if (!render) { res.status(404).json({ error: `Render ${input.renderId} not found` }); return; }
  if (render.status !== "completed") {
    res.status(400).json({ error: `Render ${input.renderId} is not completed (status=${render.status})` });
    return;
  }
  if (!(render.renderOutput as any)?.localPath) {
    res.status(400).json({ error: `Render ${input.renderId} has no output file to extract frames from` });
    return;
  }

  const id = randomUUID();
  await db.insert(thumbnailResults).values({
    id,
    renderId: input.renderId,
    status: "pending",
    logs: [`${ts()} INFO  Thumbnail job created for render: ${input.renderId}`],
    createdAt: new Date(),
    updatedAt: new Date(),
  });

  const [row] = await db.select().from(thumbnailResults).where(eq(thumbnailResults.id, id));
  res.status(202).json(toApi(row));

  setImmediate(() => {
    executeThumbnail(id, input.renderId, input.count).catch(console.error);
  });
});

// GET /thumbnails/:id/file/:candidateId — must be registered before /:id
router.get("/:id/file/:candidateId", async (req: Request, res: Response) => {
  const [row] = await db.select().from(thumbnailResults).where(eq(thumbnailResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  const candidate = ((row.candidates as any[]) || []).find((c) => c.candidateId === req.params["candidateId"]);
  if (!candidate?.path) { res.status(404).json({ error: `Candidate ${req.params["candidateId"]} not found` }); return; }
  try {
    await fs.access(candidate.path);
  } catch {
    res.status(404).json({ error: "Output file no longer exists on disk" });
    return;
  }
  res.sendFile(candidate.path);
});

// GET /thumbnails/:id
router.get("/:id", async (req: Request, res: Response) => {
  const [row] = await db.select().from(thumbnailResults).where(eq(thumbnailResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  res.json(toApi(row));
});

// DELETE /thumbnails/:id
router.delete("/:id", async (req: Request, res: Response) => {
  const [row] = await db.select().from(thumbnailResults).where(eq(thumbnailResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  for (const c of (row.candidates as any[]) || []) {
    if (c.path) await fs.unlink(c.path).catch(() => {});
  }
  await db.delete(thumbnailResults).where(eq(thumbnailResults.id, req.params["id"] as string));
  res.status(204).send();
});

export default router;
