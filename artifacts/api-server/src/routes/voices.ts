/**
 * Voice routes — POST /voices, GET /voices, GET /voices/:id, DELETE /voices/:id,
 * GET /voices/providers/stats
 *
 * Voice Engine — synthesises narration audio (TTS) for a script's sections,
 * trying providers in fallback order (first success wins — audio can't be
 * merged across providers the way text sections can). Runs asynchronously
 * (setImmediate), mirroring the Timeline/Asset pipeline pattern.
 */
import { Router, type Request, type Response } from "express";
import { db } from "@workspace/db";
import { voiceResults, scriptResults } from "@workspace/db";
import { eq, and, desc } from "drizzle-orm";
import { z } from "zod";
import { randomUUID } from "crypto";

const router = Router();

// ── Validation ─────────────────────────────────────────────────────────────────

const VoiceInputSchema = z.object({
  scriptId: z.string().min(1),
  voiceId: z.string().min(1).max(100).optional().default("alloy"),
  speed: z.number().min(0.5).max(2.0).optional().default(1.0),
  language: z.string().min(2).max(10).optional().default("en"),
  targetLoudnessLufs: z.number().min(-30).max(-6).optional().default(-14.0),
  providers: z
    .array(z.enum(["openai-tts", "elevenlabs"]))
    .min(1)
    .max(2)
    .optional()
    .default(["openai-tts", "elevenlabs"]),
});

// ── Provider metadata (mirrors app/services/voice_generator.py fallback order) ──

const ALL_PROVIDERS = ["openai-tts", "elevenlabs"] as const;

// ── Helpers ────────────────────────────────────────────────────────────────────

function ts(): string {
  return `[${new Date().toTimeString().slice(0, 8)}]`;
}

function makeId(): string {
  return randomUUID();
}

function toApi(v: typeof voiceResults.$inferSelect): object {
  return {
    id: v.id,
    scriptId: v.scriptId,
    status: v.status,
    voiceId: v.voiceId,
    speed: v.speed,
    language: v.language,
    sections: v.sections || [],
    totalDurationMs: v.totalDurationMs,
    wordCount: v.wordCount,
    sampleRate: v.sampleRate,
    audioFormat: v.audioFormat,
    normalized: v.normalized,
    targetLoudnessLufs: v.targetLoudnessLufs,
    costUsd: v.costUsd,
    usedProvider: v.usedProvider,
    providers: v.providers || [],
    jobId: v.jobId,
    logs: v.logs || [],
    errorMessage: v.errorMessage,
    createdAt: v.createdAt,
    updatedAt: v.updatedAt,
    completedAt: v.completedAt,
  };
}

async function addLog(id: string, level: string, msg: string): Promise<void> {
  const [current] = await db
    .select({ logs: voiceResults.logs })
    .from(voiceResults)
    .where(eq(voiceResults.id, id));
  const logs: string[] = (current?.logs as string[]) || [];
  logs.push(`${ts()} ${level.padEnd(5)} ${msg}`);
  await db.update(voiceResults).set({ logs, updatedAt: new Date() }).where(eq(voiceResults.id, id));
}

// ── Provider simulation (placeholder — mirrors Python VoiceGenerator interface) ─
// No real TTS API is wired up yet. Cost/latency/audio metadata are estimated
// from the script text so the rest of the pipeline (Timeline sync, players,
// waveform UI) has realistic data to work against, exactly like the Asset
// Engine's provider fallback simulation.

interface ProviderAttempt {
  providerName: string;
  ok: boolean;
  error: string | null;
  durationMs: number;
  costUsd: number;
}

function estimateWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

async function synthesizeWithProvider(
  providerName: string,
  sections: { title: string; text: string }[],
  speed: number,
  sampleRate: number,
): Promise<{ attempt: ProviderAttempt; sectionAudio: object[]; totalDurationMs: number; wordCount: number }> {
  // Simulated latency proportional to text length — deterministic, no network calls.
  const totalWords = sections.reduce((sum, s) => sum + estimateWords(s.text), 0);
  const latencyMs = Math.max(200, totalWords * 8);
  const costPerWord = providerName === "elevenlabs" ? 0.00025 : 0.000075;

  let cursorMs = 0;
  const sectionAudio: object[] = [];
  for (let i = 0; i < sections.length; i++) {
    const section = sections[i]!;
    const words = estimateWords(section.text);
    // ~150 wpm baseline narration rate, adjusted for playback speed.
    const durationMs = Math.round(((words / 150) * 60_000) / speed) || 800;
    sectionAudio.push({
      sectionIndex: i,
      sectionTitle: section.title,
      text: section.text,
      startMs: cursorMs,
      endMs: cursorMs + durationMs,
      durationMs,
      wordCount: words,
      localPath: `/storage/voice/${providerName}/${randomUUID()}.mp3`,
      sampleRate,
    });
    cursorMs += durationMs;
  }

  return {
    attempt: { providerName, ok: true, error: null, durationMs: latencyMs, costUsd: totalWords * costPerWord },
    sectionAudio,
    totalDurationMs: cursorMs,
    wordCount: totalWords,
  };
}

async function generateVoice(
  voiceId: string,
  scriptId: string,
  opts: { voiceLabel: string; speed: number; language: string; targetLoudnessLufs: number; providers: string[] },
): Promise<void> {
  try {
    await db.update(voiceResults).set({ status: "running", updatedAt: new Date() }).where(eq(voiceResults.id, voiceId));

    const [script] = await db.select().from(scriptResults).where(eq(scriptResults.id, scriptId));
    if (!script) {
      await db.update(voiceResults).set({
        status: "failed",
        errorMessage: `Script ${scriptId} not found`,
        updatedAt: new Date(),
      }).where(eq(voiceResults.id, voiceId));
      return;
    }

    await addLog(voiceId, "INFO", `Loaded script sections for narration`);

    const rawSections: any[] = (script as any).sections || [];
    const sections = rawSections.length
      ? rawSections.map((s, i) => ({
          title: s?.title || s?.section_title || `Section ${i + 1}`,
          text: s?.content || s?.text || "",
        }))
      : [
          { title: "Hook", text: (script as any).hook || "" },
          { title: "Introduction", text: (script as any).introduction || "" },
          { title: "Outro", text: (script as any).outro || "" },
        ].filter((s) => s.text);

    const sampleRate = 44100;
    let lastError = "";

    for (const providerName of opts.providers) {
      await addLog(voiceId, "INFO", `Trying provider: ${providerName}`);
      try {
        const { attempt, sectionAudio, totalDurationMs, wordCount } = await synthesizeWithProvider(
          providerName,
          sections,
          opts.speed,
          sampleRate,
        );

        await addLog(
          voiceId,
          "INFO",
          `Provider ${providerName} succeeded — ${sectionAudio.length} section(s), ${(totalDurationMs / 1000).toFixed(1)}s, $${attempt.costUsd.toFixed(4)}`,
        );

        await db.update(voiceResults).set({
          status: "completed",
          sections: sectionAudio,
          totalDurationMs,
          wordCount,
          sampleRate,
          audioFormat: "mp3",
          normalized: true,
          costUsd: attempt.costUsd,
          usedProvider: providerName,
          completedAt: new Date(),
          updatedAt: new Date(),
        }).where(eq(voiceResults.id, voiceId));
        return;
      } catch (err: any) {
        lastError = err?.message || String(err);
        await addLog(voiceId, "WARN", `Provider ${providerName} failed: ${lastError}`);
      }
    }

    await addLog(voiceId, "ERROR", `All providers failed — ${lastError}`);
    await db.update(voiceResults).set({
      status: "failed",
      errorMessage: lastError || "All voice providers failed",
      updatedAt: new Date(),
    }).where(eq(voiceResults.id, voiceId));
  } catch (err: any) {
    const errMsg = err?.message || String(err);
    await addLog(voiceId, "ERROR", `Voice generation failed: ${errMsg}`);
    await db.update(voiceResults).set({
      status: "failed",
      errorMessage: errMsg,
      updatedAt: new Date(),
    }).where(eq(voiceResults.id, voiceId));
  }
}

// ── Routes ────────────────────────────────────────────────────────────────────

// GET /voices/providers/stats  (must be registered before /:id)
router.get("/providers/stats", async (_req: Request, res: Response) => {
  const rows = await db.select().from(voiceResults);
  const items = ALL_PROVIDERS.map((name) => {
    const used = rows.filter((r) => r.usedProvider === name);
    const successful = used.filter((r) => r.status === "completed" || r.status === "cached");
    const failed = rows.filter((r) => (r.providers || []).includes(name) && r.status === "failed" && r.usedProvider !== name);
    const totalRequests = used.length + failed.length;
    const totalCostUsd = used.reduce((sum, r) => sum + (r.costUsd || 0), 0);
    const totalDurationMsGenerated = used.reduce((sum, r) => sum + (r.totalDurationMs || 0), 0);
    return {
      providerName: name,
      isEnabled: true,
      totalRequests,
      successfulRequests: successful.length,
      failedRequests: failed.length,
      avgLatencyMs: null,
      avgCostUsd: used.length ? totalCostUsd / used.length : null,
      totalCostUsd,
      totalDurationMsGenerated,
    };
  });
  res.json({ items });
});

// GET /voices
router.get("/", async (req: Request, res: Response) => {
  const limit = Math.min(Number(req.query.limit) || 50, 200);
  const offset = Number(req.query.offset) || 0;
  const filters = [];
  if (req.query.scriptId) filters.push(eq(voiceResults.scriptId, String(req.query.scriptId)));
  if (req.query.status) filters.push(eq(voiceResults.status, String(req.query.status)));

  const where = filters.length ? and(...filters) : undefined;
  const rows = where
    ? await db.select().from(voiceResults).where(where).orderBy(desc(voiceResults.createdAt))
    : await db.select().from(voiceResults).orderBy(desc(voiceResults.createdAt));

  const total = rows.length;
  res.json({ items: rows.slice(offset, offset + limit).map(toApi), total });
});

// POST /voices
router.post("/", async (req: Request, res: Response) => {
  const parse = VoiceInputSchema.safeParse(req.body);
  if (!parse.success) { res.status(400).json({ error: parse.error.flatten() }); return; }
  const input = parse.data;

  const [script] = await db.select().from(scriptResults).where(eq(scriptResults.id, input.scriptId));
  if (!script) { res.status(404).json({ error: `Script ${input.scriptId} not found` }); return; }

  const id = randomUUID();
  await db.insert(voiceResults).values({
    id,
    scriptId: input.scriptId,
    status: "pending",
    voiceId: input.voiceId,
    speed: input.speed,
    language: input.language,
    sections: [],
    normalized: false,
    targetLoudnessLufs: input.targetLoudnessLufs,
    providers: input.providers,
    logs: [`${ts()} INFO  Voice generation queued for script: ${input.scriptId}`],
    createdAt: new Date(),
    updatedAt: new Date(),
  });

  const [row] = await db.select().from(voiceResults).where(eq(voiceResults.id, id));
  res.status(202).json(toApi(row));

  setImmediate(() => {
    generateVoice(id, input.scriptId, {
      voiceLabel: input.voiceId,
      speed: input.speed,
      language: input.language,
      targetLoudnessLufs: input.targetLoudnessLufs,
      providers: input.providers,
    }).catch(console.error);
  });
});

// GET /voices/:id
router.get("/:id", async (req: Request, res: Response) => {
  const [row] = await db.select().from(voiceResults).where(eq(voiceResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  res.json(toApi(row));
});

// DELETE /voices/:id
router.delete("/:id", async (req: Request, res: Response) => {
  const [row] = await db.select().from(voiceResults).where(eq(voiceResults.id, req.params["id"] as string));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  await db.delete(voiceResults).where(eq(voiceResults.id, req.params["id"] as string));
  res.status(204).send();
});

export default router;
