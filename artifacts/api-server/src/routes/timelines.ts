/**
 * Timeline routes — POST /timelines, GET /timelines, GET /timelines/:id, DELETE /timelines/:id
 *
 * Media Timeline Engine — merges Storyboard + Assets + Voice (placeholder)
 * into a structured production timeline. Does NOT invoke MoviePy rendering.
 */
import { Router, type Request, type Response } from "express";
import { db } from "@workspace/db";
import { timelineResults, storyboardResults, assetResults } from "@workspace/db";
import { eq, and, desc } from "drizzle-orm";
import { z } from "zod";
import { randomUUID } from "crypto";

const router = Router();

// ── Validation ─────────────────────────────────────────────────────────────────

const TimelineInputSchema = z.object({
  storyboardId: z.string(),
  scriptId: z.string().optional(),
  renderFormat: z.enum(["mp4", "webm"]).optional().default("mp4"),
  fps: z.number().int().min(24).max(60).optional().default(30),
  width: z.number().int().positive().optional().default(1920),
  height: z.number().int().positive().optional().default(1080),
});

// ── Helpers ────────────────────────────────────────────────────────────────────

type PipelineStage = {
  name: string; status: string; order: number;
  startedAt: string | null; completedAt: string | null;
  durationMs: number | null; error: string | null;
};

function ts(): string {
  return `[${new Date().toTimeString().slice(0, 8)}]`;
}

function makeId(): string {
  return randomUUID();
}

function toApi(t: typeof timelineResults.$inferSelect): object {
  return {
    id: t.id,
    storyboardId: t.storyboardId,
    scriptId: t.scriptId,
    topic: t.topic,
    title: t.title,
    status: t.status,
    totalDurationMs: t.totalDurationMs,
    totalScenes: t.totalScenes,
    tracks: t.tracks || [],
    scenes: t.scenes || [],
    markers: t.markers || [],
    renderPlan: t.renderPlan || {},
    metadata: t.metadata || {},
    validationErrors: t.validationErrors || [],
    logs: t.logs || [],
    errorMessage: t.errorMessage,
    createdAt: t.createdAt,
    updatedAt: t.updatedAt,
    completedAt: t.completedAt,
  };
}

async function addLog(id: string, level: string, msg: string): Promise<void> {
  const [current] = await db
    .select({ logs: timelineResults.logs })
    .from(timelineResults)
    .where(eq(timelineResults.id, id));
  const logs: string[] = (current?.logs as string[]) || [];
  logs.push(`${ts()} ${level.padEnd(5)} ${msg}`);
  await db.update(timelineResults).set({ logs, updatedAt: new Date() }).where(eq(timelineResults.id, id));
}

// ── Timeline builder ───────────────────────────────────────────────────────────

interface TimelineClip {
  clipId: string;
  trackId: string;
  sceneId: string;
  assetId: string | null;
  assetKind: string;
  startMs: number;
  endMs: number;
  durationMs: number;
  sourceUrl: string | null;
  localPath: string | null;
  inPointMs: number;
  outPointMs: number | null;
  volume: number;
  opacity: number;
  effects: object[];
}

interface TimelineTrack {
  trackId: string;
  kind: "video" | "audio" | "subtitle" | "overlay";
  order: number;
  label: string;
  clips: TimelineClip[];
  isMuted: boolean;
  isLocked: boolean;
}

interface TimelineScene {
  sceneId: string;
  sceneNumber: number;
  title: string;
  startMs: number;
  endMs: number;
  durationMs: number;
  hasVideoAsset: boolean;
  hasAudioPlaceholder: boolean;
  assetIds: string[];
  transitionIn: string;
  transitionOut: string;
  narration: string | null;
  visualDescription: string | null;
}

interface TimelineMarker {
  markerId: string;
  label: string;
  timestampMs: number;
  markerType: "chapter" | "beat" | "note";
  color: string | null;
}

async function buildTimeline(
  timelineId: string,
  storyboardId: string,
  opts: { renderFormat: string; fps: number; width: number; height: number },
): Promise<void> {
  try {
    await db
      .update(timelineResults)
      .set({ status: "running", updatedAt: new Date() })
      .where(eq(timelineResults.id, timelineId));

    // ── Load storyboard ────────────────────────────────────────────────────
    const [sb] = await db
      .select()
      .from(storyboardResults)
      .where(eq(storyboardResults.id, storyboardId));

    if (!sb) {
      await db.update(timelineResults).set({
        status: "failed",
        errorMessage: `Storyboard ${storyboardId} not found`,
        updatedAt: new Date(),
      }).where(eq(timelineResults.id, timelineId));
      return;
    }

    await addLog(timelineId, "INFO", `Loaded storyboard: ${JSON.stringify(sb.topic)}`);
    const rawScenes: any[] = (sb.scenes as any[]) || [];
    await addLog(timelineId, "INFO", `Found ${rawScenes.length} scene(s)`);

    // ── Load acquired assets ───────────────────────────────────────────────
    const assets = await db
      .select({ id: assetResults.id, sceneId: assetResults.sceneId, sourceUrl: assetResults.sourceUrl, localCachePath: assetResults.localCachePath })
      .from(assetResults)
      .where(and(
        eq(assetResults.storyboardId, storyboardId),
        eq(assetResults.status, "ready"),
      ));
    const cachedAssets = await db
      .select({ id: assetResults.id, sceneId: assetResults.sceneId, sourceUrl: assetResults.sourceUrl, localCachePath: assetResults.localCachePath })
      .from(assetResults)
      .where(and(
        eq(assetResults.storyboardId, storyboardId),
        eq(assetResults.status, "cached"),
      ));
    const allAssets = [...assets, ...cachedAssets];
    const assetMap = new Map<string, string[]>();
    for (const a of allAssets) {
      const existing = assetMap.get(a.sceneId) || [];
      existing.push(a.id);
      assetMap.set(a.sceneId, existing);
    }
    await addLog(timelineId, "INFO", `Found ${allAssets.length} acquired asset(s)`);

    // ── Build scenes with timing ───────────────────────────────────────────
    const tlScenes: TimelineScene[] = [];
    let cursorMs = 0;

    for (let i = 0; i < rawScenes.length; i++) {
      const raw = rawScenes[i];
      const sceneId = raw?.scene_id || raw?.id || `scene_${String(i + 1).padStart(3, "0")}`;
      const durationMs = Number(
        raw?.duration_ms ||
        (raw?.estimated_video_length_seconds ? raw.estimated_video_length_seconds * 1000 : 0) ||
        5000,
      );
      const assetIds = assetMap.get(sceneId) || [];
      const VALID_TRANSITIONS = new Set(["cut", "fade", "dissolve", "wipe", "zoom"]);
      const transType = VALID_TRANSITIONS.has(raw?.transition_type) ? raw.transition_type : "cut";

      tlScenes.push({
        sceneId,
        sceneNumber: i + 1,
        title: raw?.scene_title || raw?.title || `Scene ${i + 1}`,
        startMs: cursorMs,
        endMs: cursorMs + durationMs,
        durationMs,
        hasVideoAsset: assetIds.length > 0,
        hasAudioPlaceholder: !!raw?.narration,
        assetIds,
        transitionIn: transType,
        transitionOut: "cut",
        narration: raw?.narration || null,
        visualDescription: raw?.visual_description || null,
      });
      cursorMs += durationMs;
    }

    const totalDurationMs = cursorMs;
    await addLog(timelineId, "INFO", `Total duration: ${(totalDurationMs / 1000).toFixed(1)}s`);

    // ── Video track ────────────────────────────────────────────────────────
    const videoTrackId = makeId();
    const videoClips: TimelineClip[] = tlScenes.map((scene) => ({
      clipId: makeId(),
      trackId: videoTrackId,
      sceneId: scene.sceneId,
      assetId: scene.assetIds[0] || null,
      assetKind: "image",
      startMs: scene.startMs,
      endMs: scene.endMs,
      durationMs: scene.durationMs,
      sourceUrl: null,
      localPath: null,
      inPointMs: 0,
      outPointMs: scene.durationMs,
      volume: 1.0,
      opacity: 1.0,
      effects: [],
    }));

    const videoTrack: TimelineTrack = {
      trackId: videoTrackId,
      kind: "video",
      order: 0,
      label: "Video",
      clips: videoClips,
      isMuted: false,
      isLocked: false,
    };

    // ── Audio track (placeholder) ──────────────────────────────────────────
    const audioTrackId = makeId();
    const audioClips: TimelineClip[] = tlScenes
      .filter((s) => s.hasAudioPlaceholder)
      .map((scene) => ({
        clipId: makeId(),
        trackId: audioTrackId,
        sceneId: scene.sceneId,
        assetId: null,
        assetKind: "audio",
        startMs: scene.startMs,
        endMs: scene.endMs,
        durationMs: scene.durationMs,
        sourceUrl: null,
        localPath: null,
        inPointMs: 0,
        outPointMs: null,
        volume: 1.0,
        opacity: 1.0,
        effects: [],
      }));

    const audioTrack: TimelineTrack = {
      trackId: audioTrackId,
      kind: "audio",
      order: 1,
      label: "Narration (placeholder)",
      clips: audioClips,
      isMuted: true,  // placeholder — no real audio yet
      isLocked: false,
    };

    // ── Subtitle track (placeholder) ───────────────────────────────────────
    const subtitleTrackId = makeId();
    const subtitleClips: TimelineClip[] = tlScenes
      .filter((s) => s.narration)
      .map((scene) => ({
        clipId: makeId(),
        trackId: subtitleTrackId,
        sceneId: scene.sceneId,
        assetId: null,
        assetKind: "subtitle",
        startMs: scene.startMs,
        endMs: scene.endMs,
        durationMs: scene.durationMs,
        sourceUrl: null,
        localPath: null,
        inPointMs: 0,
        outPointMs: null,
        volume: 1.0,
        opacity: 1.0,
        effects: [],
      }));

    const subtitleTrack: TimelineTrack = {
      trackId: subtitleTrackId,
      kind: "subtitle",
      order: 2,
      label: "Subtitles (placeholder)",
      clips: subtitleClips,
      isMuted: false,
      isLocked: false,
    };

    // ── Chapter markers ────────────────────────────────────────────────────
    const markers: TimelineMarker[] = tlScenes
      .filter((s, i) => i === 0 || s.sceneNumber % 3 === 1)
      .map((s) => ({
        markerId: makeId(),
        label: s.title,
        timestampMs: s.startMs,
        markerType: "chapter" as const,
        color: null,
      }));

    // ── Render plan ────────────────────────────────────────────────────────
    const renderPlan = {
      width: opts.width,
      height: opts.height,
      fps: opts.fps,
      format: opts.renderFormat,
      codec: "h264",
      audioCodec: "aac",
      bitrateKbps: 8000,
      estimatedRenderTimeMs: totalDurationMs * 2,
    };

    // ── Metadata + validation ──────────────────────────────────────────────
    let hasGaps = false;
    let gapCount = 0;
    let prevEnd = 0;
    for (const clip of videoClips) {
      if (clip.startMs > prevEnd + 100) { hasGaps = true; gapCount++; }
      prevEnd = clip.endMs;
    }

    const scenesWithAssets = tlScenes.filter((s) => s.hasVideoAsset).length;
    const coveragePct = tlScenes.length > 0 ? (scenesWithAssets / tlScenes.length) * 100 : 0;

    const metadata = {
      totalDurationMs,
      totalScenes: tlScenes.length,
      videoClipCount: videoClips.length,
      audioClipCount: audioClips.length,
      hasGaps,
      gapCount,
      transitionCount: Math.max(0, tlScenes.length - 1),
      estimatedFileSizeBytes: Math.round(totalDurationMs * 8000 / 8),
      assetCoveragePct: Math.round(coveragePct * 10) / 10,
    };

    const validationErrors: string[] = [];
    if (!tlScenes.length) validationErrors.push("No scenes found in storyboard");
    if (hasGaps) validationErrors.push(`${gapCount} gap(s) detected in video track`);
    if (coveragePct < 50) validationErrors.push(`Only ${coveragePct.toFixed(0)}% of scenes have assets — acquire assets first`);

    const statusLine = validationErrors.length === 0
      ? "✓ complete"
      : `⚠ ${validationErrors.length} warning(s)`;

    await addLog(timelineId, "INFO",
      `Timeline built — ${tlScenes.length} scenes, ${(totalDurationMs / 1000).toFixed(1)}s, ${statusLine}`,
    );

    await db.update(timelineResults).set({
      status: "completed",
      topic: sb.topic,
      title: (sb as any).title || sb.topic,
      totalDurationMs,
      totalScenes: tlScenes.length,
      tracks: [videoTrack, audioTrack, subtitleTrack] as object[],
      scenes: tlScenes as object[],
      markers: markers as object[],
      renderPlan,
      metadata,
      validationErrors,
      completedAt: new Date(),
      updatedAt: new Date(),
    }).where(eq(timelineResults.id, timelineId));

  } catch (err: any) {
    const errMsg = err?.message || String(err);
    await addLog(timelineId, "ERROR", `Timeline build failed: ${errMsg}`);
    await db.update(timelineResults).set({
      status: "failed",
      errorMessage: errMsg,
      updatedAt: new Date(),
    }).where(eq(timelineResults.id, timelineId));
  }
}

// ── Routes ────────────────────────────────────────────────────────────────────

// GET /timelines
router.get("/", async (req: Request, res: Response) => {
  const limit = Math.min(Number(req.query.limit) || 50, 200);
  const offset = Number(req.query.offset) || 0;
  const filters = [];
  if (req.query.storyboardId) filters.push(eq(timelineResults.storyboardId, String(req.query.storyboardId)));
  if (req.query.status) filters.push(eq(timelineResults.status, String(req.query.status)));

  const where = filters.length ? and(...filters) : undefined;
  const rows = where
    ? await db.select().from(timelineResults).where(where).orderBy(desc(timelineResults.createdAt))
    : await db.select().from(timelineResults).orderBy(desc(timelineResults.createdAt));

  const total = rows.length;
  res.json({ items: rows.slice(offset, offset + limit).map(toApi), total });
});

// POST /timelines
router.post("/", async (req: Request, res: Response) => {
  const parse = TimelineInputSchema.safeParse(req.body);
  if (!parse.success) { res.status(400).json({ error: parse.error.flatten() }); return; }
  const input = parse.data;

  const [storyboard] = await db
    .select()
    .from(storyboardResults)
    .where(eq(storyboardResults.id, input.storyboardId));
  if (!storyboard) { res.status(404).json({ error: `Storyboard ${input.storyboardId} not found` }); return; }

  const id = randomUUID();
  await db.insert(timelineResults).values({
    id,
    storyboardId: input.storyboardId,
    scriptId: input.scriptId,
    topic: storyboard.topic,
    title: (storyboard as any).title || storyboard.topic,
    status: "pending",
    tracks: [],
    scenes: [],
    markers: [],
    renderPlan: {},
    metadata: {},
    validationErrors: [],
    logs: [`${ts()} INFO  Timeline build queued for storyboard: ${storyboard.topic}`],
    createdAt: new Date(),
    updatedAt: new Date(),
  });

  const [row] = await db.select().from(timelineResults).where(eq(timelineResults.id, id));
  res.status(202).json(toApi(row));

  setImmediate(() => {
    buildTimeline(id, input.storyboardId, {
      renderFormat: input.renderFormat,
      fps: input.fps,
      width: input.width,
      height: input.height,
    }).catch(console.error);
  });
});

// GET /timelines/:id
router.get("/:id", async (req: Request, res: Response) => {
  const [row] = await db.select().from(timelineResults).where(eq(timelineResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  res.json(toApi(row));
});

// DELETE /timelines/:id
router.delete("/:id", async (req: Request, res: Response) => {
  const [row] = await db.select().from(timelineResults).where(eq(timelineResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  await db.delete(timelineResults).where(eq(timelineResults.id, req.params["id"] as string));
  res.status(204).send();
});

export default router;
