import { pgTable, text, timestamp, json } from "drizzle-orm/pg-core";

// ── Production Assets ─────────────────────────────────────────────────────────
// Post-Processing Engine — aggregates the outputs of the Subtitle, Thumbnail,
// and Chapter engines for one RenderResult into a single exportable bundle.

export const productionAssets = pgTable("production_assets", {
  id: text("id").primaryKey(),
  renderId: text("render_id").notNull().unique(),

  status: text("status").notNull().default("pending"),
  // enum: pending | partial | completed

  subtitleId: text("subtitle_id"),
  thumbnailId: text("thumbnail_id"),
  chapterId: text("chapter_id"),

  exportManifest: json("export_manifest").$type<object>().notNull().default({}),

  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});
