/**
 * Production Asset routes — GET /production-assets, GET /production-assets/:renderId
 *
 * Post-Processing Engine — aggregates the latest completed Subtitle,
 * Thumbnail, and Chapter results for a render into one bundle with a
 * computed status (pending/partial/completed) and an export manifest of
 * real on-disk file paths.
 */
import { Router, type Request, type Response } from "express";
import { db } from "@workspace/db";
import {
  productionAssets,
  subtitleResults,
  thumbnailResults,
  chapterResults,
  renderResults,
} from "@workspace/db";
import { eq, desc } from "drizzle-orm";
import { randomUUID } from "crypto";

const router = Router();

function toApi(bundle: typeof productionAssets.$inferSelect, joined: { subtitle: any; thumbnail: any; chapter: any }): object {
  return {
    id: bundle.id,
    renderId: bundle.renderId,
    status: bundle.status,
    subtitleId: bundle.subtitleId,
    thumbnailId: bundle.thumbnailId,
    chapterId: bundle.chapterId,
    subtitle: joined.subtitle,
    thumbnail: joined.thumbnail,
    chapter: joined.chapter,
    exportManifest: bundle.exportManifest || {},
    createdAt: bundle.createdAt,
    updatedAt: bundle.updatedAt,
    completedAt: bundle.completedAt,
  };
}

async function assembleBundle(renderId: string): Promise<{ bundle: typeof productionAssets.$inferSelect; joined: any } | null> {
  const [render] = await db.select().from(renderResults).where(eq(renderResults.id, renderId));
  if (!render) return null;

  let [bundle] = await db.select().from(productionAssets).where(eq(productionAssets.renderId, renderId));
  if (!bundle) {
    const id = randomUUID();
    await db.insert(productionAssets).values({
      id,
      renderId,
      status: "pending",
      exportManifest: {},
      createdAt: new Date(),
      updatedAt: new Date(),
    });
    [bundle] = await db.select().from(productionAssets).where(eq(productionAssets.id, id));
  }

  const [subtitleRows, thumbnailRows, chapterRows] = await Promise.all([
    db.select().from(subtitleResults).where(eq(subtitleResults.renderId, renderId)).orderBy(desc(subtitleResults.createdAt)),
    db.select().from(thumbnailResults).where(eq(thumbnailResults.renderId, renderId)).orderBy(desc(thumbnailResults.createdAt)),
    db.select().from(chapterResults).where(eq(chapterResults.renderId, renderId)).orderBy(desc(chapterResults.createdAt)),
  ]);
  const subtitle = subtitleRows[0] ?? null;
  const thumbnail = thumbnailRows[0] ?? null;
  const chapter = chapterRows[0] ?? null;

  const completedSubtitle = subtitle?.status === "completed" ? subtitle : null;
  const completedThumbnail = thumbnail?.status === "completed" ? thumbnail : null;
  const completedChapter = chapter?.status === "completed" ? chapter : null;
  const presentCount = [completedSubtitle, completedThumbnail, completedChapter].filter(Boolean).length;
  const status = presentCount === 3 ? "completed" : presentCount > 0 ? "partial" : "pending";

  const exportManifest = {
    srtPath: completedSubtitle?.srtPath ?? null,
    vttPath: completedSubtitle?.vttPath ?? null,
    assPath: completedSubtitle?.assPath ?? null,
    thumbnailPaths: completedThumbnail
      ? ((completedThumbnail.candidates as any[]) || [])
          .filter((c) => (completedThumbnail.selectedCandidateIds as string[])?.includes(c.candidateId))
          .map((c) => c.path)
      : [],
    youtubeChapters: completedChapter?.youtubeExport ?? null,
  };

  const [updated] = await db.update(productionAssets).set({
    status,
    subtitleId: subtitle?.id ?? null,
    thumbnailId: thumbnail?.id ?? null,
    chapterId: chapter?.id ?? null,
    exportManifest,
    updatedAt: new Date(),
    completedAt: status === "completed" ? new Date() : bundle!.completedAt,
  }).where(eq(productionAssets.id, bundle!.id)).returning();

  return { bundle: updated!, joined: { subtitle, thumbnail, chapter } };
}

// GET /production-assets
router.get("/", async (req: Request, res: Response) => {
  const limit = Math.min(Number(req.query.limit) || 50, 200);
  const offset = Number(req.query.offset) || 0;
  const rows = await db.select().from(renderResults).where(eq(renderResults.status, "completed")).orderBy(desc(renderResults.createdAt));
  const total = rows.length;
  const page = rows.slice(offset, offset + limit);
  const items = [];
  for (const r of page) {
    const result = await assembleBundle(r.id);
    if (result) items.push(toApi(result.bundle, result.joined));
  }
  res.json({ items, total });
});

// GET /production-assets/:renderId
router.get("/:renderId", async (req: Request, res: Response) => {
  const result = await assembleBundle(req.params["renderId"] as string);
  if (!result) { res.status(404).json({ error: "Render not found" }); return; }
  res.json(toApi(result.bundle, result.joined));
});

export default router;
