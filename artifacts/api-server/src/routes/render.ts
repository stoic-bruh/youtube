/**
 * Render routes — POST /renders, GET /renders, GET /renders/:id, DELETE /renders/:id,
 * GET /renders/providers/stats
 *
 * MoviePy Render Engine — merges a completed Timeline + Voice narration +
 * Assets into a real MP4. Unlike the other pipeline stages (Research, Script,
 * Storyboard, Asset, Timeline, Voice), which simulate provider calls entirely
 * in Node, rendering genuinely needs MoviePy/FFmpeg (Python-only). This route
 * builds a RenderPlan from the Node-owned Timeline/Voice/Asset rows — mirroring
 * app/services/render/plan_builder.py in the Python service — then shells out
 * to `services/youtube-factory-api/scripts/render_cli.py`, which runs the
 * exact same `MoviePyRenderer` used by the FastAPI/Celery path, and writes a
 * real .mp4 file to disk.
 */
import { Router, type Request, type Response } from "express";
import { db } from "@workspace/db";
import { renderResults, timelineResults, voiceResults, assetResults } from "@workspace/db";
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
const RENDER_CLI = path.join(PYTHON_SERVICE_DIR, "scripts", "render_cli.py");
const OUTPUT_DIR = process.env.RENDER_OUTPUT_DIR || "/tmp/render_engine/output";

const RESOLUTION_DIMENSIONS: Record<string, [number, number]> = {
  "720p": [1280, 720],
  "1080p": [1920, 1080],
  "4k": [3840, 2160],
};

// ── Validation ─────────────────────────────────────────────────────────────────

const RenderInputSchema = z.object({
  timelineId: z.string().min(1),
  voiceId: z.string().min(1).optional(),
  resolution: z.enum(["720p", "1080p", "4k"]).optional().default("1080p"),
  fps: z.number().int().min(24).max(60).optional().default(30),
  aspectRatio: z.enum(["16:9", "9:16", "1:1"]).optional().default("16:9"),
  cropMode: z.enum(["safe_crop", "letterbox", "blur_pad"]).optional().default("safe_crop"),
  hardwareAcceleration: z.boolean().optional().default(false),
  addBackgroundMusic: z.boolean().optional().default(false),
  musicVolume: z.number().min(0).max(1).optional().default(0.12),
  generatePreview: z.boolean().optional().default(true),
});

// ── Helpers ────────────────────────────────────────────────────────────────────

function ts(): string {
  return `[${new Date().toTimeString().slice(0, 8)}]`;
}

function toApi(r: typeof renderResults.$inferSelect): object {
  return {
    id: r.id,
    timelineId: r.timelineId,
    voiceId: r.voiceId,
    status: r.status,
    progress: r.progress,
    resolution: r.resolution,
    width: r.width,
    height: r.height,
    fps: r.fps,
    aspectRatio: r.aspectRatio,
    cropMode: r.cropMode,
    hardwareAcceleration: r.hardwareAcceleration,
    renderPlan: r.renderPlan || {},
    renderOutput: r.renderOutput || {},
    renderStats: r.renderStats || {},
    renderMetadata: r.metadata || {},
    previewOutput: r.previewOutput || {},
    logs: r.logs || [],
    errorMessage: r.errorMessage,
    createdAt: r.createdAt,
    updatedAt: r.updatedAt,
    completedAt: r.completedAt,
  };
}

async function addLog(id: string, level: string, msg: string): Promise<void> {
  const [current] = await db.select({ logs: renderResults.logs }).from(renderResults).where(eq(renderResults.id, id));
  const logs: string[] = (current?.logs as string[]) || [];
  logs.push(`${ts()} ${level.padEnd(5)} ${msg}`);
  await db.update(renderResults).set({ logs, updatedAt: new Date() }).where(eq(renderResults.id, id));
}

// ── RenderPlan builder (mirrors app/services/render/plan_builder.py) ───────────

const PAN_CYCLE = ["right", "left", "up", "down"];

function buildRenderPlan(
  timeline: typeof timelineResults.$inferSelect,
  voice: typeof voiceResults.$inferSelect | null,
  assets: (typeof assetResults.$inferSelect)[],
  opts: {
    resolution: string; fps: number; aspectRatio: string; cropMode: string;
    hardwareAcceleration: boolean; addBackgroundMusic: boolean; musicVolume: number;
  },
): object {
  let [width, height] = RESOLUTION_DIMENSIONS[opts.resolution] || RESOLUTION_DIMENSIONS["1080p"]!;
  if (opts.aspectRatio === "9:16") [width, height] = [Math.min(width, height), Math.max(width, height)];
  else if (opts.aspectRatio === "1:1") { const side = Math.min(width, height); width = height = side; }

  const assetsByScene = new Map<string, (typeof assetResults.$inferSelect)[]>();
  for (const a of assets) {
    if (!a.sceneId) continue;
    const existing = assetsByScene.get(a.sceneId) || [];
    existing.push(a);
    assetsByScene.set(a.sceneId, existing);
  }

  const voiceSections: any[] = (voice?.sections as any[]) || [];
  const timelineScenes: any[] = (timeline.scenes as any[]) || [];

  const scenes = timelineScenes.map((scene, i) => {
    const sceneId = scene.sceneId || `scene-${i}`;
    const startMs = Number(scene.startMs ?? 0);
    const endMs = Number(scene.endMs ?? startMs + 4000);
    const durationMs = Math.max(endMs - startMs, 500);
    const narration = scene.narration || voiceSections[i]?.text || "";

    const sceneAssets = assetsByScene.get(sceneId) || [];
    const clips = sceneAssets.length
      ? [{
          clip_id: `${sceneId}-clip-0`,
          scene_index: i,
          asset_id: sceneAssets[0]!.id,
          kind: "image",
          source_path: sceneAssets[0]!.localCachePath ?? null,
          start_ms: startMs, end_ms: endMs, duration_ms: durationMs,
          ken_burns: true, pan_direction: PAN_CYCLE[i % PAN_CYCLE.length],
        }]
      : [{
          clip_id: `${sceneId}-clip-placeholder`,
          scene_index: i,
          kind: "placeholder",
          source_path: null,
          start_ms: startMs, end_ms: endMs, duration_ms: durationMs,
          ken_burns: true, pan_direction: PAN_CYCLE[i % PAN_CYCLE.length],
        }];

    return {
      scene_index: i,
      title: scene.title || `Scene ${i + 1}`,
      narration,
      start_ms: startMs, end_ms: endMs, duration_ms: durationMs,
      clips,
      transition_out: {
        type: i === timelineScenes.length - 1 ? "cut" : "crossfade",
        duration_ms: 500,
      },
    };
  });

  const audioTracks: object[] = [];
  if (voiceSections.length) {
    let cursor = 0;
    for (const section of voiceSections) {
      const sStart = Number(section.startMs ?? cursor);
      const sEnd = Number(section.endMs ?? sStart + Number(section.durationMs ?? 3000));
      audioTracks.push({
        kind: "narration",
        source_path: section.localPath ?? null,
        start_ms: sStart, end_ms: sEnd, volume: 1.0,
      });
      cursor = sEnd;
    }
  }

  const totalDurationMs = scenes.length ? Math.max(...scenes.map((s) => s.end_ms)) : 0;

  return {
    timeline_id: timeline.id,
    voice_id: voice?.id ?? null,
    title: (timeline as any).title || timeline.topic || "Untitled Render",
    resolution: opts.resolution,
    width, height,
    fps: opts.fps,
    aspect_ratio: opts.aspectRatio,
    crop_mode: opts.cropMode,
    hardware_acceleration: opts.hardwareAcceleration,
    add_background_music: opts.addBackgroundMusic,
    background_music_path: null,
    music_volume: opts.musicVolume,
    scenes,
    video_tracks: [{ kind: "main", scene_indices: scenes.map((s) => s.scene_index) }],
    audio_tracks: audioTracks,
    total_duration_ms: totalDurationMs,
  };
}

// ── CLI invocation ───────────────────────────────────────────────────────────

function runRenderCli(planPath: string, outputPath: string, previewPath: string | null): Promise<any> {
  return new Promise((resolve, reject) => {
    const args = [RENDER_CLI, planPath, outputPath];
    if (previewPath) args.push("--preview", previewPath);
    const proc = spawn(PYTHON_BIN, args, {
      cwd: PYTHON_SERVICE_DIR,
      env: { ...process.env, PYTHONPATH: PYTHON_SERVICE_DIR },
    });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d) => (stdout += d.toString()));
    proc.stderr.on("data", (d) => (stderr += d.toString()));
    proc.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`render_cli.py exited with code ${code}: ${stderr.slice(-2000)}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout.trim().split("\n").pop() || "{}"));
      } catch (err) {
        reject(new Error(`Failed to parse render_cli.py output: ${err}. stdout=${stdout.slice(-2000)}`));
      }
    });
    proc.on("error", (err) => reject(err));
  });
}

async function executeRender(
  renderId: string,
  timelineId: string,
  voiceId: string | null,
  opts: { resolution: string; fps: number; aspectRatio: string; cropMode: string; hardwareAcceleration: boolean; addBackgroundMusic: boolean; musicVolume: number; generatePreview: boolean },
): Promise<void> {
  try {
    await db.update(renderResults).set({ status: "running", progress: 5, updatedAt: new Date() }).where(eq(renderResults.id, renderId));

    const [timeline] = await db.select().from(timelineResults).where(eq(timelineResults.id, timelineId));
    if (!timeline) {
      await db.update(renderResults).set({ status: "failed", errorMessage: `Timeline ${timelineId} not found`, updatedAt: new Date() }).where(eq(renderResults.id, renderId));
      return;
    }
    const voice = voiceId ? (await db.select().from(voiceResults).where(eq(voiceResults.id, voiceId)))[0] || null : null;
    const assets = timeline.storyboardId
      ? await db.select().from(assetResults).where(eq(assetResults.storyboardId, timeline.storyboardId))
      : [];

    await addLog(renderId, "INFO", "Phase 1/3 — Building RenderPlan from Timeline + Voice + Assets");
    const plan: any = buildRenderPlan(timeline, voice, assets, opts);
    await db.update(renderResults).set({
      renderPlan: plan, width: plan.width, height: plan.height, progress: 15, updatedAt: new Date(),
    }).where(eq(renderResults.id, renderId));
    await addLog(renderId, "INFO", `RenderPlan assembled — ${plan.scenes.length} scene(s), ${plan.width}x${plan.height}@${plan.fps}fps`);

    await fs.mkdir(OUTPUT_DIR, { recursive: true });
    const planPath = path.join(OUTPUT_DIR, `${renderId}.plan.json`);
    await fs.writeFile(planPath, JSON.stringify(plan));
    const outputPath = path.join(OUTPUT_DIR, `${renderId}.mp4`);
    const previewPath = opts.generatePreview ? path.join(OUTPUT_DIR, `${renderId}_preview.mp4`) : null;

    await addLog(renderId, "INFO", "Phase 2/3 — Compositing with MoviePy/FFmpeg (real render)");
    await db.update(renderResults).set({ progress: 30, updatedAt: new Date() }).where(eq(renderResults.id, renderId));

    const result = await runRenderCli(planPath, outputPath, previewPath);

    const metadata = {
      sceneCount: plan.scenes.length,
      clipCount: plan.scenes.reduce((sum: number, s: any) => sum + s.clips.length, 0),
      placeholderClipCount: plan.scenes.reduce((sum: number, s: any) => sum + s.clips.filter((c: any) => c.kind === "placeholder").length, 0),
      hasNarration: !!voice,
      hasBackgroundMusic: opts.addBackgroundMusic,
      sourceTimelineId: timelineId,
      sourceVoiceId: voiceId,
    };

    await addLog(renderId, "INFO", `Phase 3/3 — Render complete: ${result.output.file_size_bytes} bytes, ${result.output.duration_seconds}s`);

    await db.update(renderResults).set({
      status: "completed",
      progress: 100,
      renderOutput: {
        localPath: result.output.local_path,
        fileSizeBytes: result.output.file_size_bytes,
        durationSeconds: result.output.duration_seconds,
        width: result.output.width,
        height: result.output.height,
        fps: result.output.fps,
        codec: result.output.codec,
        audioCodec: result.output.audio_codec,
        format: result.output.format,
      },
      renderStats: {
        renderTimeSeconds: result.stats.render_time_seconds,
        framesEncoded: result.stats.frames_encoded,
        encodeFps: result.stats.encode_fps,
        realtimeFactor: result.stats.realtime_factor,
        retries: result.stats.retries,
      },
      metadata,
      previewOutput: result.preview_output
        ? {
            localPath: result.preview_output.local_path,
            fileSizeBytes: result.preview_output.file_size_bytes,
            durationSeconds: result.preview_output.duration_seconds,
            width: result.preview_output.width,
            height: result.preview_output.height,
            fps: result.preview_output.fps,
            codec: result.preview_output.codec,
            audioCodec: result.preview_output.audio_codec,
            format: result.preview_output.format,
          }
        : {},
      completedAt: new Date(),
      updatedAt: new Date(),
    }).where(eq(renderResults.id, renderId));
  } catch (err: any) {
    const errMsg = err?.message || String(err);
    await addLog(renderId, "ERROR", `Render failed: ${errMsg}`);
    await db.update(renderResults).set({ status: "failed", errorMessage: errMsg, updatedAt: new Date() }).where(eq(renderResults.id, renderId));
  }
}

// ── Routes ────────────────────────────────────────────────────────────────────

// GET /renders/providers/stats  (must be registered before /:id)
router.get("/providers/stats", async (_req: Request, res: Response) => {
  const rows = await db.select().from(renderResults);
  const completed = rows.filter((r) => r.status === "completed");
  const failed = rows.filter((r) => r.status === "failed");
  const stats = completed.map((r) => (r.renderStats as any) || {});
  const avg = (key: string) => (stats.length ? stats.reduce((sum, s) => sum + (s[key] || 0), 0) / stats.length : 0);
  res.json({
    backend: "moviepy",
    totalRenders: rows.length,
    completed: completed.length,
    failed: failed.length,
    avgRenderTimeSeconds: avg("renderTimeSeconds"),
    avgRealtimeFactor: avg("realtimeFactor"),
    totalOutputSeconds: completed.reduce((sum, r) => sum + ((r.renderOutput as any)?.durationSeconds || 0), 0),
  });
});

// GET /renders
router.get("/", async (req: Request, res: Response) => {
  const limit = Math.min(Number(req.query.limit) || 50, 200);
  const offset = Number(req.query.offset) || 0;
  const filters = [];
  if (req.query.timelineId) filters.push(eq(renderResults.timelineId, String(req.query.timelineId)));
  if (req.query.status) filters.push(eq(renderResults.status, String(req.query.status)));

  const where = filters.length ? and(...filters) : undefined;
  const rows = where
    ? await db.select().from(renderResults).where(where).orderBy(desc(renderResults.createdAt))
    : await db.select().from(renderResults).orderBy(desc(renderResults.createdAt));

  const total = rows.length;
  res.json({ items: rows.slice(offset, offset + limit).map(toApi), total });
});

// POST /renders
router.post("/", async (req: Request, res: Response) => {
  const parse = RenderInputSchema.safeParse(req.body);
  if (!parse.success) { res.status(400).json({ error: parse.error.flatten() }); return; }
  const input = parse.data;

  const [timeline] = await db.select().from(timelineResults).where(eq(timelineResults.id, input.timelineId));
  if (!timeline) { res.status(404).json({ error: `Timeline ${input.timelineId} not found` }); return; }
  if (timeline.status !== "completed") {
    res.status(400).json({ error: `Timeline ${input.timelineId} is not ready to render (status=${timeline.status})` });
    return;
  }

  let voiceId = input.voiceId ?? null;
  if (!voiceId && timeline.scriptId) {
    const candidates = await db.select().from(voiceResults).where(and(eq(voiceResults.scriptId, timeline.scriptId), eq(voiceResults.status, "completed")));
    voiceId = candidates[0]?.id ?? null;
  }

  const id = randomUUID();
  await db.insert(renderResults).values({
    id,
    timelineId: input.timelineId,
    voiceId,
    status: "pending",
    progress: 0,
    resolution: input.resolution,
    width: 0,
    height: 0,
    fps: input.fps,
    aspectRatio: input.aspectRatio,
    cropMode: input.cropMode,
    hardwareAcceleration: input.hardwareAcceleration,
    renderPlan: {},
    renderOutput: {},
    renderStats: {},
    metadata: {},
    previewOutput: {},
    logs: [`${ts()} INFO  Render job created for timeline: ${input.timelineId}`],
    createdAt: new Date(),
    updatedAt: new Date(),
  });

  const [row] = await db.select().from(renderResults).where(eq(renderResults.id, id));
  res.status(202).json(toApi(row));

  setImmediate(() => {
    executeRender(id, input.timelineId, voiceId, input).catch(console.error);
  });
});

// GET /renders/:id/file — streams the rendered MP4 (or ?variant=preview for the short preview clip)
router.get("/:id/file", async (req: Request, res: Response) => {
  const [row] = await db.select().from(renderResults).where(eq(renderResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  const variant = req.query["variant"] === "preview" ? "preview" : "full";
  const localPath = variant === "preview" ? (row.previewOutput as any)?.localPath : (row.renderOutput as any)?.localPath;
  if (!localPath) { res.status(404).json({ error: `No ${variant} output available (status=${row.status})` }); return; }
  try {
    await fs.access(localPath);
  } catch {
    res.status(404).json({ error: "Output file no longer exists on disk" });
    return;
  }
  res.setHeader("Content-Type", "video/mp4");
  res.sendFile(localPath);
});

// GET /renders/:id
router.get("/:id", async (req: Request, res: Response) => {
  const [row] = await db.select().from(renderResults).where(eq(renderResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  res.json(toApi(row));
});

// DELETE /renders/:id
router.delete("/:id", async (req: Request, res: Response) => {
  const [row] = await db.select().from(renderResults).where(eq(renderResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  const localPath = (row.renderOutput as any)?.localPath;
  if (localPath) {
    await fs.unlink(localPath).catch(() => {});
  }
  await db.delete(renderResults).where(eq(renderResults.id, req.params["id"] as string));
  res.status(204).send();
});

export default router;
