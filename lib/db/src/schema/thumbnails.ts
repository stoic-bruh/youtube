import { pgTable, text, timestamp, json } from "drizzle-orm/pg-core";

// ── Thumbnail Results ─────────────────────────────────────────────────────────
// Post-Processing Engine — Thumbnail Engine. Extracts real candidate frames
// from the rendered video via FFmpeg, scores them (sharpness/quality/brightness)
// with Pillow, and selects the best candidates.

export const thumbnailResults = pgTable("thumbnail_results", {
  id: text("id").primaryKey(),
  renderId: text("render_id").notNull(),

  status: text("status").notNull().default("pending"),
  // enum: pending | running | completed | failed

  // All extracted candidate frames with scoring + detection interface output
  candidates: json("candidates").$type<object[]>().notNull().default([]),
  // Subset of candidate ids selected as the best thumbnails (top N)
  selectedCandidateIds: json("selected_candidate_ids").$type<string[]>().notNull().default([]),

  templates: json("templates").$type<object[]>().notNull().default([]),
  titleOverlay: json("title_overlay").$type<object>().notNull().default({}),
  brandColors: json("brand_colors").$type<string[]>().notNull().default([]),

  logs: json("logs").$type<string[]>().notNull().default([]),
  errorMessage: text("error_message"),

  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});
