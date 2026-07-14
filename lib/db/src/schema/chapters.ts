import { pgTable, text, timestamp, json } from "drizzle-orm/pg-core";

// ── Chapter Results ───────────────────────────────────────────────────────────
// Post-Processing Engine — Chapter Engine. Derives YouTube chapters purely from
// existing structured data (Timeline scenes, Script section titles, Voice
// section timestamps) — no media analysis required.

export const chapterResults = pgTable("chapter_results", {
  id: text("id").primaryKey(),
  renderId: text("render_id").notNull(),

  status: text("status").notNull().default("pending"),
  // enum: pending | running | completed | failed

  chapters: json("chapters").$type<object[]>().notNull().default([]),
  youtubeExport: text("youtube_export"),
  sources: json("sources").$type<object>().notNull().default({}),

  logs: json("logs").$type<string[]>().notNull().default([]),
  errorMessage: text("error_message"),

  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});
