/**
 * Asset routes — POST /assets, GET /assets, GET /assets/:id, DELETE /assets/:id, GET /assets/providers
 *
 * Mock Asset Intelligence Engine decision flow, mirroring the storyboards.ts / research.ts pattern:
 * cache check → stock provider search → AI generation fallback. Runs asynchronously (setImmediate)
 * after the 202 response so the frontend can watch status/log progress per asset.
 */
import { Router, type Request, type Response } from "express";
import { db } from "@workspace/db";
import { assetResults, assetProviderMetadata, storyboardResults } from "@workspace/db";
import { eq, and, desc, inArray } from "drizzle-orm";
import { z } from "zod";
import { randomUUID } from "crypto";

const router = Router();

// ── Validation ─────────────────────────────────────────────────────────────────

const ASSET_KINDS = ["image", "video", "svg", "chart", "map", "icon"] as const;

const AssetInputSchema = z.object({
  storyboardId: z.string(),
  sceneIds: z.array(z.string()).optional().default([]),
  assetKinds: z.array(z.enum(ASSET_KINDS)).min(1).optional().default(["image"]),
  providers: z.array(z.string()).optional().default(["wikimedia", "pexels", "pixabay", "flux"]),
  forceGenerate: z.boolean().optional().default(false),
});

// ── Provider metadata (mirrors app/providers/asset/registry.py) ────────────────

const STOCK_PROVIDERS = ["wikimedia", "unsplash", "pixabay", "pexels"];
const VIDEO_PROVIDERS = ["pexels_video", "pixabay_video", "mixkit"];
const ICON_PROVIDERS = ["lucide", "heroicons", "material_icons"];
const GENERATOR_PROVIDERS = ["flux", "sdxl", "gpt_image", "gemini_image", "ideogram"];

const PROVIDER_TYPE: Record<string, "stock" | "generate" | "icon"> = {
  wikimedia: "stock", unsplash: "stock", pixabay: "stock", pexels: "stock",
  pexels_video: "stock", pixabay_video: "stock", mixkit: "stock",
  lucide: "icon", heroicons: "icon", material_icons: "icon",
  flux: "generate", sdxl: "generate", gpt_image: "generate", gemini_image: "generate", ideogram: "generate",
};

const ALL_PROVIDERS = Object.keys(PROVIDER_TYPE);

function providersForKind(kind: string, forceGenerate: boolean): string[] {
  if (forceGenerate) return GENERATOR_PROVIDERS;
  if (kind === "video") return VIDEO_PROVIDERS;
  if (kind === "icon") return ICON_PROVIDERS;
  if (kind === "chart") return GENERATOR_PROVIDERS;
  return [...STOCK_PROVIDERS, ...GENERATOR_PROVIDERS];
}

const LICENSES: Record<string, string[]> = {
  wikimedia: ["cc0", "cc_by", "cc_by_sa", "public_domain"],
  unsplash: ["cc0"],
  pixabay: ["cc0"],
  pexels: ["cc0"],
  pexels_video: ["cc0"],
  pixabay_video: ["cc0"],
  mixkit: ["commercial"],
  lucide: ["mit"],
  heroicons: ["mit"],
  material_icons: ["cc_by"],
  flux: ["generated"], sdxl: ["generated"], gpt_image: ["generated"], gemini_image: ["generated"], ideogram: ["generated"],
};

const GEN_COST_USD: Record<string, number> = {
  flux: 0.03, sdxl: 0.02, gpt_image: 0.04, gemini_image: 0.03, ideogram: 0.05,
};

// ── Helpers ────────────────────────────────────────────────────────────────────

function ts(): string {
  return `[${new Date().toTimeString().slice(0, 8)}]`;
}

class SeededRandom {
  private seed: number;
  constructor(seedStr: string) {
    let h = 0;
    for (let i = 0; i < seedStr.length; i++) h = ((h << 5) - h + seedStr.charCodeAt(i)) | 0;
    this.seed = Math.abs(h) || 1;
  }
  next(): number {
    this.seed ^= this.seed << 13;
    this.seed ^= this.seed >> 17;
    this.seed ^= this.seed << 5;
    return (Math.abs(this.seed) % 10_000) / 10_000;
  }
  int(lo: number, hi: number): number { return Math.floor(lo + this.next() * (hi - lo + 1)); }
  float(lo: number, hi: number): number { return +(lo + this.next() * (hi - lo)).toFixed(3); }
  choice<T>(arr: T[]): T { return arr[Math.floor(this.next() * arr.length)]; }
}

function toApi(a: typeof assetResults.$inferSelect): object {
  return {
    id: a.id, storyboardId: a.storyboardId, sceneId: a.sceneId,
    assetKind: a.assetKind, provider: a.provider, providerAssetId: a.providerAssetId,
    sourceUrl: a.sourceUrl, license: a.license,
    prompt: a.prompt, negativePrompt: a.negativePrompt, generationParameters: a.generationParameters || {},
    width: a.width, height: a.height, aspectRatio: a.aspectRatio,
    status: a.status, costEstimateUsd: a.costEstimateUsd, generationTimeMs: a.generationTimeMs,
    fileSizeBytes: a.fileSizeBytes, localCachePath: a.localCachePath, thumbnailPath: a.thumbnailPath,
    tags: a.tags || [], qualityScore: a.qualityScore, relevanceScore: a.relevanceScore,
    logs: a.logs || [], errorMessage: a.errorMessage,
    createdAt: a.createdAt, updatedAt: a.updatedAt, completedAt: a.completedAt,
  };
}

async function addLog(id: string, level: string, msg: string): Promise<void> {
  const [current] = await db.select({ logs: assetResults.logs }).from(assetResults).where(eq(assetResults.id, id));
  const logs: string[] = (current?.logs as string[]) || [];
  logs.push(`${ts()} ${level.padEnd(5)} ${msg}`);
  await db.update(assetResults).set({ logs, updatedAt: new Date() }).where(eq(assetResults.id, id));
}

async function recordProviderRequest(
  providerName: string,
  opts: { success: boolean; latencyMs: number; costUsd?: number; cacheHit?: boolean },
): Promise<void> {
  const [existing] = await db.select().from(assetProviderMetadata).where(eq(assetProviderMetadata.providerName, providerName));
  if (!existing) {
    await db.insert(assetProviderMetadata).values({
      id: randomUUID(),
      providerName,
      providerType: PROVIDER_TYPE[providerName] ?? "stock",
      totalRequests: 1,
      successfulRequests: opts.success ? 1 : 0,
      failedRequests: opts.success ? 0 : 1,
      avgLatencyMs: opts.latencyMs,
      avgCostUsd: opts.costUsd ?? null,
      totalCostUsd: opts.costUsd ?? 0,
      cacheHits: opts.cacheHit ? 1 : 0,
      supportedKinds: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    });
    return;
  }
  const n = existing.totalRequests + 1;
  const avgLatencyMs = existing.avgLatencyMs == null ? opts.latencyMs : ((existing.avgLatencyMs * (n - 1)) + opts.latencyMs) / n;
  const avgCostUsd = opts.costUsd && opts.costUsd > 0
    ? (existing.avgCostUsd == null ? opts.costUsd : (existing.avgCostUsd + opts.costUsd) / 2)
    : existing.avgCostUsd;
  await db.update(assetProviderMetadata).set({
    totalRequests: n,
    successfulRequests: existing.successfulRequests + (opts.success ? 1 : 0),
    failedRequests: existing.failedRequests + (opts.success ? 0 : 1),
    avgLatencyMs,
    avgCostUsd,
    totalCostUsd: (existing.totalCostUsd || 0) + (opts.costUsd ?? 0),
    cacheHits: existing.cacheHits + (opts.cacheHit ? 1 : 0),
    updatedAt: new Date(),
  }).where(eq(assetProviderMetadata.providerName, providerName));
}

// ── Async decision engine (mock) ────────────────────────────────────────────────

async function processAsset(
  assetId: string,
  storyboardId: string,
  sceneId: string,
  assetKind: string,
  query: string,
  providerPreference: string[],
  forceGenerate: boolean,
): Promise<void> {
  const rng = new SeededRandom(`${storyboardId}:${sceneId}:${assetKind}:${query}`);
  try {
    await db.update(assetResults).set({ status: "searching", updatedAt: new Date() }).where(eq(assetResults.id, assetId));
    await addLog(assetId, "INFO", `Searching stock providers for ${JSON.stringify(query)}`);
    await new Promise((r) => setTimeout(r, rng.int(80, 250)));

    const stockCandidates = providerPreference.filter((p) => STOCK_PROVIDERS.includes(p) || VIDEO_PROVIDERS.includes(p) || ICON_PROVIDERS.includes(p));
    const generatorCandidates = providerPreference.filter((p) => GENERATOR_PROVIDERS.includes(p));
    const fallbackStock = providersForKind(assetKind, false).filter((p) => STOCK_PROVIDERS.includes(p) || VIDEO_PROVIDERS.includes(p) || ICON_PROVIDERS.includes(p));
    const fallbackGen = providersForKind(assetKind, false).filter((p) => GENERATOR_PROVIDERS.includes(p));

    const stockOrder = [...new Set([...stockCandidates, ...fallbackStock])];
    const genOrder = [...new Set([...generatorCandidates, ...fallbackGen])];

    let hitProvider: string | null = null;
    let usedGeneration = false;

    if (!forceGenerate && assetKind !== "chart") {
      for (const provider of stockOrder) {
        const t0 = Date.now();
        const found = rng.next() > 0.35; // ~65% stock hit rate per provider tried
        const latency = rng.int(150, 900);
        await recordProviderRequest(provider, { success: found, latencyMs: latency });
        if (found) {
          hitProvider = provider;
          await addLog(assetId, "INFO", `Stock hit from ${provider} (${Date.now() - t0}ms)`);
          break;
        }
        await addLog(assetId, "WARN", `${provider} — no acceptable match`);
      }
    }

    if (!hitProvider) {
      await addLog(assetId, "INFO", "No stock asset found — generating with AI");
      await db.update(assetResults).set({ status: "generating", updatedAt: new Date() }).where(eq(assetResults.id, assetId));
      for (const provider of genOrder.length ? genOrder : GENERATOR_PROVIDERS) {
        const t0 = Date.now();
        await new Promise((r) => setTimeout(r, rng.int(200, 600)));
        const success = rng.next() > 0.1; // generators succeed ~90% of the time
        const latency = Date.now() - t0;
        await recordProviderRequest(provider, { success, latencyMs: latency, costUsd: GEN_COST_USD[provider] ?? 0.03 });
        if (success) {
          hitProvider = provider;
          usedGeneration = true;
          await addLog(assetId, "INFO", `Generated with ${provider} (${latency}ms)`);
          break;
        }
        await addLog(assetId, "WARN", `Generator ${provider} failed — trying next`);
      }
    }

    if (!hitProvider) {
      await addLog(assetId, "ERROR", "All providers failed — asset acquisition failed");
      await db.update(assetResults).set({ status: "failed", errorMessage: "All providers failed", updatedAt: new Date() }).where(eq(assetResults.id, assetId));
      return;
    }

    await db.update(assetResults).set({ status: "downloading", updatedAt: new Date() }).where(eq(assetResults.id, assetId));
    await new Promise((r) => setTimeout(r, rng.int(80, 200)));

    const width = assetKind === "icon" ? rng.choice([24, 32, 48, 64]) : 1920;
    const height = assetKind === "icon" ? width : 1080;
    const licenseOptions = LICENSES[hitProvider] ?? ["unknown"];
    const license = rng.choice(licenseOptions);
    const qualityScore = usedGeneration ? +rng.float(0.7, 0.98).toFixed(2) : +rng.float(0.6, 0.95).toFixed(2);
    const relevanceScore = +rng.float(0.55, 0.97).toFixed(2);
    const fileSizeBytes = assetKind === "video" ? rng.int(2_000_000, 20_000_000) : rng.int(80_000, 900_000);

    await addLog(assetId, "INFO", `Cached asset from ${hitProvider} — quality ${qualityScore}, relevance ${relevanceScore}`);

    await db.update(assetResults).set({
      provider: hitProvider,
      providerAssetId: `${hitProvider}_${rng.int(100000, 999999)}`,
      sourceUrl: usedGeneration ? null : `https://${hitProvider.replace(/_/g, "-")}.example/${randomUUID()}`,
      license,
      generationParameters: usedGeneration ? { prompt: query, steps: rng.int(20, 40), guidance_scale: +rng.float(3, 9).toFixed(1) } : {},
      width, height,
      aspectRatio: `${width}:${height}`.replace(/^(\d+):\1$/, "1:1"),
      status: usedGeneration ? "ready" : "cached",
      costEstimateUsd: usedGeneration ? (GEN_COST_USD[hitProvider] ?? 0.03) : 0,
      generationTimeMs: rng.int(400, 4000),
      fileSizeBytes,
      localCachePath: `/cache/assets/${assetId}.${assetKind === "video" ? "mp4" : assetKind === "icon" ? "svg" : "jpg"}`,
      thumbnailPath: `/cache/assets/${assetId}_thumb.jpg`,
      tags: [assetKind, hitProvider, usedGeneration ? "generated" : "stock"],
      qualityScore,
      relevanceScore,
      completedAt: new Date(),
      updatedAt: new Date(),
    }).where(eq(assetResults.id, assetId));
  } catch (err: any) {
    const errMsg = err?.message || String(err);
    await addLog(assetId, "ERROR", `Asset acquisition failed: ${errMsg}`);
    await db.update(assetResults).set({ status: "failed", errorMessage: errMsg, updatedAt: new Date() }).where(eq(assetResults.id, assetId));
  }
}

// ── Routes ────────────────────────────────────────────────────────────────────

// GET /assets
router.get("/", async (req: Request, res: Response) => {
  const limit = Math.min(Number(req.query.limit) || 50, 200);
  const offset = Number(req.query.offset) || 0;
  const filters = [];
  if (req.query.storyboardId) filters.push(eq(assetResults.storyboardId, String(req.query.storyboardId)));
  if (req.query.sceneId) filters.push(eq(assetResults.sceneId, String(req.query.sceneId)));
  if (req.query.status) filters.push(eq(assetResults.status, String(req.query.status)));
  if (req.query.assetKind) filters.push(eq(assetResults.assetKind, String(req.query.assetKind)));
  if (req.query.provider) filters.push(eq(assetResults.provider, String(req.query.provider)));

  const where = filters.length ? and(...filters) : undefined;
  const rows = where
    ? await db.select().from(assetResults).where(where).orderBy(desc(assetResults.createdAt))
    : await db.select().from(assetResults).orderBy(desc(assetResults.createdAt));

  const total = rows.length;
  const page = rows.slice(offset, offset + limit);
  res.json({ items: page.map(toApi), total });
});

// GET /assets/providers  (must be registered before /:id)
router.get("/providers", async (_req: Request, res: Response) => {
  const rows = await db.select().from(assetProviderMetadata);
  const byName = new Map(rows.map((r) => [r.providerName, r]));
  const items = ALL_PROVIDERS.map((name) => {
    const r = byName.get(name);
    if (!r) {
      return {
        providerName: name, providerType: PROVIDER_TYPE[name], isEnabled: true,
        totalRequests: 0, successfulRequests: 0, failedRequests: 0,
        avgLatencyMs: null, avgCostUsd: null, totalCostUsd: 0, cacheHits: 0, supportedKinds: [],
      };
    }
    return {
      providerName: r.providerName, providerType: r.providerType, isEnabled: r.isEnabled,
      totalRequests: r.totalRequests, successfulRequests: r.successfulRequests, failedRequests: r.failedRequests,
      avgLatencyMs: r.avgLatencyMs, avgCostUsd: r.avgCostUsd, totalCostUsd: r.totalCostUsd,
      cacheHits: r.cacheHits, supportedKinds: r.supportedKinds || [],
    };
  });
  res.json({ items });
});

// POST /assets
router.post("/", async (req: Request, res: Response) => {
  const parse = AssetInputSchema.safeParse(req.body);
  if (!parse.success) { res.status(400).json({ error: parse.error.flatten() }); return; }
  const input = parse.data;

  const [storyboard] = await db.select().from(storyboardResults).where(eq(storyboardResults.id, input.storyboardId));
  if (!storyboard) { res.status(404).json({ error: `Storyboard ${input.storyboardId} not found` }); return; }

  let sceneIds = input.sceneIds;
  if (!sceneIds.length) {
    const scenes = (storyboard.scenes as any[]) || [];
    sceneIds = scenes.map((s, i) => s?.scene_id || s?.id || `scene_${String(i + 1).padStart(3, "0")}`);
  }
  if (!sceneIds.length) { res.status(400).json({ error: "Storyboard has no scenes to acquire assets for" }); return; }

  const created: (typeof assetResults.$inferSelect)[] = [];
  for (const sceneId of sceneIds) {
    for (const kind of input.assetKinds) {
      const id = randomUUID();
      await db.insert(assetResults).values({
        id,
        storyboardId: input.storyboardId,
        sceneId,
        assetKind: kind,
        status: "pending",
        license: "unknown",
        generationParameters: {},
        tags: [],
        logs: [`${ts()} INFO  Asset acquisition queued — kind: ${kind}`],
        createdAt: new Date(),
        updatedAt: new Date(),
      });
      const [row] = await db.select().from(assetResults).where(eq(assetResults.id, id));
      created.push(row);
    }
  }

  res.status(202).json({
    items: created.map(toApi),
    total: created.length,
    message: `Asset acquisition queued for ${created.length} scene/kind combinations`,
  });

  setImmediate(() => {
    for (const asset of created) {
      processAsset(
        asset.id,
        asset.storyboardId,
        asset.sceneId,
        asset.assetKind,
        `${storyboard.topic} — ${asset.sceneId}`,
        input.providers,
        input.forceGenerate,
      ).catch(console.error);
    }
  });
});

// GET /assets/:id
router.get("/:id", async (req: Request, res: Response) => {
  const id = req.params["id"] as string;
  const [row] = await db.select().from(assetResults).where(eq(assetResults.id, id));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  res.json(toApi(row));
});

// DELETE /assets/:id
router.delete("/:id", async (req: Request, res: Response) => {
  const id = req.params["id"] as string;
  const [row] = await db.select().from(assetResults).where(eq(assetResults.id, id));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  await db.delete(assetResults).where(eq(assetResults.id, id));
  res.status(204).send();
});

export default router;
