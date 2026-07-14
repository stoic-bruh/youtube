/**
 * Subtitle routes — POST /subtitles, GET /subtitles, GET /subtitles/:id,
 * DELETE /subtitles/:id, GET /subtitles/:id/file/:format
 *
 * Post-Processing Engine — Subtitle Engine. Like Render, this genuinely
 * needs real media tooling (FFmpeg audio extraction + faster-whisper
 * transcription), so Node shells out to
 * `services/youtube-factory-api/scripts/postprocess_cli.py subtitle`, which
 * runs the same provider-fallback registry (Whisper -> script-narration) used
 * by the FastAPI/Celery path, and writes real SRT/VTT/ASS files to disk.
 */
import { Router, type Request, type Response } from "express";
import { db } from "@workspace/db";
import { subtitleResults, renderResults, voiceResults } from "@workspace/db";
import { eq, and, desc } from "drizzle-orm";
import { z } from "zod";
import { randomUUID } from "crypto";
import { spawn } from "child_process";
import path from "path";
import fs from "fs/promises";

const router = Router();

// ── Config ───────────────────────────────────────────────────────────────────

const PYTHON_SERVICE_DIR = path.resolve(process.cwd(), "../../services/youtube-factory-api");
const PYTHON_BIN = process.env.RENDER_PYTHON_BIN || "/home/runner/workspace/.pythonlibs/bin/python3";
const POSTPROCESS_CLI = path.join(PYTHON_SERVICE_DIR, "scripts", "postprocess_cli.py");
const OUTPUT_DIR = process.env.POSTPROCESS_OUTPUT_DIR || "/tmp/postprocess_engine";
const SUBTITLE_OUTPUT_DIR = path.join(OUTPUT_DIR, "subtitles");

const DEFAULT_STYLE = {
  fontFamily: "Arial",
  fontSize: 72,
  primaryColor: "#FFFFFF",
  outlineColor: "#000000",
  backgroundColor: "#00000080",
  position: "bottom-center",
};

const CAPTION_PRESETS = [
  { id: "classic", label: "Classic", burned: false, fontSize: 48, position: "bottom-center" },
  { id: "bold-center", label: "Bold Center", burned: true, fontSize: 72, position: "middle-center" },
  { id: "karaoke-yellow", label: "Karaoke", burned: true, fontSize: 64, highlightColor: "#FFD700", position: "bottom-center" },
];

// ── Validation ─────────────────────────────────────────────────────────────────

const SubtitleInputSchema = z.object({
  renderId: z.string().min(1),
  language: z.string().min(2).max(10).optional().default("en"),
  providers: z.array(z.enum(["whisper", "script-narration"])).min(1).optional().default(["whisper", "script-narration"]),
});

// ── Helpers ────────────────────────────────────────────────────────────────────

function ts(): string {
  return `[${new Date().toTimeString().slice(0, 8)}]`;
}

function toApi(s: typeof subtitleResults.$inferSelect): object {
  return {
    id: s.id,
    renderId: s.renderId,
    status: s.status,
    language: s.language,
    usedProvider: s.usedProvider,
    providers: s.providers || [],
    words: s.words || [],
    sentences: s.sentences || [],
    paragraphs: s.paragraphs || [],
    srtContent: s.srtContent,
    vttContent: s.vttContent,
    assContent: s.assContent,
    srtPath: s.srtPath,
    vttPath: s.vttPath,
    assPath: s.assPath,
    burnedMetadata: s.burnedMetadata || {},
    animatedCaptionMetadata: s.animatedCaptionMetadata || {},
    karaokeMetadata: s.karaokeMetadata || {},
    style: s.style || {},
    captionPresets: s.captionPresets || [],
    speakerMetadata: s.speakerMetadata || [],
    avgConfidence: s.avgConfidence,
    wordCount: s.wordCount,
    durationMs: s.durationMs,
    logs: s.logs || [],
    errorMessage: s.errorMessage,
    createdAt: s.createdAt,
    updatedAt: s.updatedAt,
    completedAt: s.completedAt,
  };
}

async function addLog(id: string, level: string, msg: string): Promise<void> {
  const [current] = await db.select({ logs: subtitleResults.logs }).from(subtitleResults).where(eq(subtitleResults.id, id));
  const logs: string[] = (current?.logs as string[]) || [];
  logs.push(`${ts()} ${level.padEnd(5)} ${msg}`);
  await db.update(subtitleResults).set({ logs, updatedAt: new Date() }).where(eq(subtitleResults.id, id));
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

async function executeSubtitle(
  subtitleId: string,
  renderId: string,
  opts: { language: string; providers: string[] },
): Promise<void> {
  try {
    await db.update(subtitleResults).set({ status: "running", updatedAt: new Date() }).where(eq(subtitleResults.id, subtitleId));
    await addLog(subtitleId, "INFO", `Starting transcription for render=${renderId}`);

    const [render] = await db.select().from(renderResults).where(eq(renderResults.id, renderId));
    if (!render) throw new Error(`Source render ${renderId} no longer exists`);
    const videoPath = (render.renderOutput as any)?.localPath;
    if (!videoPath) throw new Error(`Render output file not found for ${renderId}`);
    await fs.access(videoPath);

    let sections: { text: string; startMs: number; endMs: number }[] = [];
    if (render.voiceId) {
      const [voice] = await db.select().from(voiceResults).where(eq(voiceResults.id, render.voiceId));
      sections = ((voice?.sections as any[]) || []).map((s) => ({
        text: s.text || "",
        startMs: s.startMs ?? 0,
        endMs: s.endMs ?? 0,
      }));
    }

    await addLog(subtitleId, "INFO", `Phase 1/2 — Transcribing (providers: ${opts.providers.join(", ")})`);
    await fs.mkdir(SUBTITLE_OUTPUT_DIR, { recursive: true });
    const inputPath = path.join(SUBTITLE_OUTPUT_DIR, `${subtitleId}.input.json`);
    await fs.writeFile(
      inputPath,
      JSON.stringify({
        videoPath,
        language: opts.language,
        providers: opts.providers,
        sections,
        outputDir: SUBTITLE_OUTPUT_DIR,
        idPrefix: subtitleId,
      }),
    );

    const result = await runPostprocessCli("subtitle", inputPath);
    for (const line of result.logs || []) {
      await addLog(subtitleId, "INFO", line);
    }
    if (result.error) throw new Error(result.error);

    await addLog(subtitleId, "INFO", `Transcription complete via ${result.provider} — ${result.wordCount} word(s)`);
    await addLog(subtitleId, "INFO", `Phase 2/2 — Wrote ${result.srtPath}, ${result.vttPath}, ${result.assPath}`);

    await db.update(subtitleResults).set({
      status: "completed",
      usedProvider: result.provider,
      words: result.words,
      sentences: result.sentences,
      paragraphs: result.paragraphs,
      srtContent: result.srtContent,
      vttContent: result.vttContent,
      assContent: result.assContent,
      srtPath: result.srtPath,
      vttPath: result.vttPath,
      assPath: result.assPath,
      style: DEFAULT_STYLE,
      captionPresets: CAPTION_PRESETS,
      burnedMetadata: { enabled: false, presetId: "classic" },
      animatedCaptionMetadata: { enabled: true, animation: "word-pop", presetId: "bold-center" },
      karaokeMetadata: { enabled: true, highlightColor: "#FFD700", presetId: "karaoke-yellow" },
      speakerMetadata: [{ speakerId: "speaker-1", label: "Narrator", wordCount: result.wordCount }],
      avgConfidence: result.avgConfidence,
      wordCount: result.wordCount,
      durationMs: result.durationMs,
      completedAt: new Date(),
      updatedAt: new Date(),
    }).where(eq(subtitleResults.id, subtitleId));
  } catch (err: any) {
    const errMsg = err?.message || String(err);
    await addLog(subtitleId, "ERROR", `Subtitle generation failed: ${errMsg}`);
    await db.update(subtitleResults).set({ status: "failed", errorMessage: errMsg, updatedAt: new Date() }).where(eq(subtitleResults.id, subtitleId));
  }
}

// ── Routes ────────────────────────────────────────────────────────────────────

// GET /subtitles
router.get("/", async (req: Request, res: Response) => {
  const limit = Math.min(Number(req.query.limit) || 50, 200);
  const offset = Number(req.query.offset) || 0;
  const filters = [];
  if (req.query.renderId) filters.push(eq(subtitleResults.renderId, String(req.query.renderId)));
  if (req.query.status) filters.push(eq(subtitleResults.status, String(req.query.status)));

  const where = filters.length ? and(...filters) : undefined;
  const rows = where
    ? await db.select().from(subtitleResults).where(where).orderBy(desc(subtitleResults.createdAt))
    : await db.select().from(subtitleResults).orderBy(desc(subtitleResults.createdAt));

  const total = rows.length;
  res.json({ items: rows.slice(offset, offset + limit).map(toApi), total });
});

// POST /subtitles
router.post("/", async (req: Request, res: Response) => {
  const parse = SubtitleInputSchema.safeParse(req.body);
  if (!parse.success) { res.status(400).json({ error: parse.error.flatten() }); return; }
  const input = parse.data;

  const [render] = await db.select().from(renderResults).where(eq(renderResults.id, input.renderId));
  if (!render) { res.status(404).json({ error: `Render ${input.renderId} not found` }); return; }
  if (render.status !== "completed") {
    res.status(400).json({ error: `Render ${input.renderId} is not completed (status=${render.status})` });
    return;
  }
  if (!(render.renderOutput as any)?.localPath) {
    res.status(400).json({ error: `Render ${input.renderId} has no output file to transcribe` });
    return;
  }

  const id = randomUUID();
  await db.insert(subtitleResults).values({
    id,
    renderId: input.renderId,
    status: "pending",
    language: input.language,
    providers: input.providers,
    logs: [`${ts()} INFO  Subtitle job created for render: ${input.renderId}`],
    createdAt: new Date(),
    updatedAt: new Date(),
  });

  const [row] = await db.select().from(subtitleResults).where(eq(subtitleResults.id, id));
  res.status(202).json(toApi(row));

  setImmediate(() => {
    executeSubtitle(id, input.renderId, { language: input.language, providers: input.providers }).catch(console.error);
  });
});

// GET /subtitles/:id/file/:format — must be registered before /:id
router.get("/:id/file/:format", async (req: Request, res: Response) => {
  const [row] = await db.select().from(subtitleResults).where(eq(subtitleResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  const format = req.params["format"] as string;
  const pathByFormat: Record<string, string | null> = { srt: row.srtPath, vtt: row.vttPath, ass: row.assPath };
  const filePath = pathByFormat[format];
  if (!filePath) { res.status(404).json({ error: `No ${format} file available (status=${row.status})` }); return; }
  try {
    await fs.access(filePath);
  } catch {
    res.status(404).json({ error: "Output file no longer exists on disk" });
    return;
  }
  res.sendFile(filePath);
});

// GET /subtitles/:id
router.get("/:id", async (req: Request, res: Response) => {
  const [row] = await db.select().from(subtitleResults).where(eq(subtitleResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  res.json(toApi(row));
});

// DELETE /subtitles/:id
router.delete("/:id", async (req: Request, res: Response) => {
  const [row] = await db.select().from(subtitleResults).where(eq(subtitleResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  for (const p of [row.srtPath, row.vttPath, row.assPath]) {
    if (p) await fs.unlink(p).catch(() => {});
  }
  await db.delete(subtitleResults).where(eq(subtitleResults.id, req.params["id"] as string));
  res.status(204).send();
});

export default router;
