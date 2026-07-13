import { pgTable, text, integer, boolean, timestamp, json } from "drizzle-orm/pg-core";

// ── Render Results ───────────────────────────────────────────────────────────
// MoviePy/FFmpeg Render Engine — merges Timeline + Voice + Assets into a final
// rendered MP4. See artifacts/api-server/src/routes/render.ts.

export const renderResults = pgTable("render_results", {
  id: text("id").primaryKey(),
  timelineId: text("timeline_id").notNull(),
  voiceId: text("voice_id"),

  status: text("status").notNull().default("pending"),
  // enum: pending | running | completed | failed
  progress: integer("progress").notNull().default(0),

  resolution: text("resolution").notNull().default("1080p"),
  // enum: 720p | 1080p | 4k
  width: integer("width").notNull().default(1920),
  height: integer("height").notNull().default(1080),
  fps: integer("fps").notNull().default(30),
  aspectRatio: text("aspect_ratio").notNull().default("16:9"),
  // enum: 16:9 | 9:16 | 1:1
  cropMode: text("crop_mode").notNull().default("safe_crop"),
  // enum: safe_crop | letterbox | blur_pad
  hardwareAcceleration: boolean("hardware_acceleration").notNull().default(false),

  renderPlan: json("render_plan").$type<object>().notNull().default({}),
  renderOutput: json("render_output").$type<object>().notNull().default({}),
  renderStats: json("render_stats").$type<object>().notNull().default({}),
  metadata: json("metadata").$type<object>().notNull().default({}),
  previewOutput: json("preview_output").$type<object>().notNull().default({}),

  logs: json("logs").$type<string[]>().notNull().default([]),
  errorMessage: text("error_message"),

  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});
