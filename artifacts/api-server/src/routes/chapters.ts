/**
 * Chapter routes — POST /chapters, GET /chapters, GET /chapters/:id,
 * DELETE /chapters/:id
 *
 * Post-Processing Engine — Chapter Engine. Pure data derivation: chapters
 * come straight from the render's real RenderPlan scene timing (already
 * merged Timeline + Voice timestamps), with descriptions enriched from the
 * source Script's section content. No media analysis or CLI shell-out is
 * needed, so this runs entirely in Node (mirrors app/services/chapter_service.py).
 */
import { Router, type Request, type Response } from "express";
import { db } from "@workspace/db";
import { chapterResults, renderResults, timelineResults, scriptResults } from "@workspace/db";
import { eq, and, desc } from "drizzle-orm";
import { z } from "zod";
import { randomUUID } from "crypto";

const router = Router();

// YouTube requires the first chapter to start at 0:00 and every chapter to be at least 10s.
const YOUTUBE_MIN_CHAPTER_MS = 10_000;

const ChapterInputSchema = z.object({
  renderId: z.string().min(1),
});

function ts(): string {
  return `[${new Date().toTimeString().slice(0, 8)}]`;
}

function formatYoutubeTimestamp(ms: number): string {
  const totalSeconds = Math.max(ms, 0) / 1000 | 0;
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours) return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

interface RawChapter { title: string; startMs: number; endMs: number; description: string | null }

function mergeShortScenes(raw: RawChapter[], minDurationMs = YOUTUBE_MIN_CHAPTER_MS): RawChapter[] {
  if (!raw.length) return [];
  const merged: RawChapter[] = [{ ...raw[0]! }];
  for (const chapter of raw.slice(1)) {
    const duration = chapter.endMs - chapter.startMs;
    const prev = merged[merged.length - 1]!;
    const prevDuration = prev.endMs - prev.startMs;
    if (prevDuration < minDurationMs) {
      prev.endMs = chapter.startMs;
      merged.push({ ...chapter });
    } else if (duration < minDurationMs) {
      prev.endMs = chapter.endMs;
    } else {
      merged.push({ ...chapter });
    }
  }
  if (merged.length > 1) {
    const last = merged[merged.length - 1]!;
    if (last.endMs - last.startMs < minDurationMs) {
      merged.pop();
      merged[merged.length - 1]!.endMs = last.endMs;
    }
  }
  return merged;
}

function toApi(c: typeof chapterResults.$inferSelect): object {
  return {
    id: c.id,
    renderId: c.renderId,
    status: c.status,
    chapters: c.chapters || [],
    youtubeExport: c.youtubeExport,
    sources: c.sources || {},
    logs: c.logs || [],
    errorMessage: c.errorMessage,
    createdAt: c.createdAt,
    updatedAt: c.updatedAt,
    completedAt: c.completedAt,
  };
}

async function addLog(id: string, level: string, msg: string): Promise<void> {
  const [current] = await db.select({ logs: chapterResults.logs }).from(chapterResults).where(eq(chapterResults.id, id));
  const logs: string[] = (current?.logs as string[]) || [];
  logs.push(`${ts()} ${level.padEnd(5)} ${msg}`);
  await db.update(chapterResults).set({ logs, updatedAt: new Date() }).where(eq(chapterResults.id, id));
}

async function executeChapter(chapterId: string, renderId: string): Promise<void> {
  try {
    await db.update(chapterResults).set({ status: "running", updatedAt: new Date() }).where(eq(chapterResults.id, chapterId));
    await addLog(chapterId, "INFO", `Starting chapter derivation for render=${renderId}`);

    const [render] = await db.select().from(renderResults).where(eq(renderResults.id, renderId));
    if (!render) throw new Error(`Source render ${renderId} no longer exists`);
    const scenes: any[] = ((render.renderPlan as any)?.scenes) || [];
    if (!scenes.length) throw new Error("Render has no scene timing to derive chapters from");

    const [timeline] = render.timelineId
      ? await db.select().from(timelineResults).where(eq(timelineResults.id, render.timelineId))
      : [null];
    const [script] = timeline?.scriptId
      ? await db.select().from(scriptResults).where(eq(scriptResults.id, timeline.scriptId))
      : [null];
    const sectionsByTitle = new Map<string, any>();
    for (const s of (script as any)?.sections || []) {
      sectionsByTitle.set(String(s.title || "").trim().toLowerCase(), s);
    }

    await addLog(chapterId, "INFO", `Phase 1/2 — Building ${scenes.length} raw chapter(s) from real scene timing`);
    const sortedScenes = [...scenes].sort((a, b) => (a.scene_index ?? 0) - (b.scene_index ?? 0));
    const rawChapters: RawChapter[] = sortedScenes.map((scene, i) => {
      const title = scene.title || `Chapter ${i + 1}`;
      const startMs = Number(scene.start_ms ?? 0);
      const endMs = Number(scene.end_ms ?? startMs);
      const section = sectionsByTitle.get(String(title).trim().toLowerCase());
      const narration = scene.narration || "";
      const description: string | null = (section?.content || narration || null)?.slice(0, 280) || null;
      return { title, startMs, endMs, description };
    });
    if (rawChapters.length) rawChapters[0]!.startMs = 0;

    await addLog(chapterId, "INFO", "Phase 2/2 — Merging sub-10s scenes to satisfy YouTube's minimum chapter length");
    const merged = mergeShortScenes(rawChapters);
    await addLog(chapterId, "INFO", `${rawChapters.length} raw scene(s) -> ${merged.length} YouTube-valid chapter(s)`);

    const chapters = merged.map((c) => ({ title: c.title, startMs: c.startMs, endMs: c.endMs, description: c.description }));
    const youtubeExport = merged.map((c) => `${formatYoutubeTimestamp(c.startMs)} ${c.title}`).join("\n");

    await db.update(chapterResults).set({
      status: "completed",
      chapters,
      youtubeExport,
      sources: { renderId, timelineId: render.timelineId, scriptId: timeline?.scriptId ?? null, voiceId: render.voiceId },
      completedAt: new Date(),
      updatedAt: new Date(),
    }).where(eq(chapterResults.id, chapterId));
  } catch (err: any) {
    const errMsg = err?.message || String(err);
    await addLog(chapterId, "ERROR", `Chapter generation failed: ${errMsg}`);
    await db.update(chapterResults).set({ status: "failed", errorMessage: errMsg, updatedAt: new Date() }).where(eq(chapterResults.id, chapterId));
  }
}

// GET /chapters
router.get("/", async (req: Request, res: Response) => {
  const limit = Math.min(Number(req.query.limit) || 50, 200);
  const offset = Number(req.query.offset) || 0;
  const filters = [];
  if (req.query.renderId) filters.push(eq(chapterResults.renderId, String(req.query.renderId)));
  if (req.query.status) filters.push(eq(chapterResults.status, String(req.query.status)));

  const where = filters.length ? and(...filters) : undefined;
  const rows = where
    ? await db.select().from(chapterResults).where(where).orderBy(desc(chapterResults.createdAt))
    : await db.select().from(chapterResults).orderBy(desc(chapterResults.createdAt));

  const total = rows.length;
  res.json({ items: rows.slice(offset, offset + limit).map(toApi), total });
});

// POST /chapters
router.post("/", async (req: Request, res: Response) => {
  const parse = ChapterInputSchema.safeParse(req.body);
  if (!parse.success) { res.status(400).json({ error: parse.error.flatten() }); return; }
  const input = parse.data;

  const [render] = await db.select().from(renderResults).where(eq(renderResults.id, input.renderId));
  if (!render) { res.status(404).json({ error: `Render ${input.renderId} not found` }); return; }
  if (render.status !== "completed") {
    res.status(400).json({ error: `Render ${input.renderId} is not completed (status=${render.status})` });
    return;
  }
  if (!((render.renderPlan as any)?.scenes?.length)) {
    res.status(400).json({ error: `Render ${input.renderId} has no scene timing to derive chapters from` });
    return;
  }

  const id = randomUUID();
  await db.insert(chapterResults).values({
    id,
    renderId: input.renderId,
    status: "pending",
    logs: [`${ts()} INFO  Chapter job created for render: ${input.renderId}`],
    createdAt: new Date(),
    updatedAt: new Date(),
  });

  const [row] = await db.select().from(chapterResults).where(eq(chapterResults.id, id));
  res.status(202).json(toApi(row));

  setImmediate(() => {
    executeChapter(id, input.renderId).catch(console.error);
  });
});

// GET /chapters/:id
router.get("/:id", async (req: Request, res: Response) => {
  const [row] = await db.select().from(chapterResults).where(eq(chapterResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  res.json(toApi(row));
});

// DELETE /chapters/:id
router.delete("/:id", async (req: Request, res: Response) => {
  const [row] = await db.select().from(chapterResults).where(eq(chapterResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  await db.delete(chapterResults).where(eq(chapterResults.id, req.params["id"] as string));
  res.status(204).send();
});

export default router;
