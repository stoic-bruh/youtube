import { pgTable, text, real, integer, timestamp, json } from "drizzle-orm/pg-core";

export const storyboardResults = pgTable("storyboard_results", {
  id: text("id").primaryKey(),
  scriptId: text("script_id"),
  researchId: text("research_id"),
  topic: text("topic").notNull(),
  title: text("title"),
  status: text("status").notNull().default("pending"),
  // enum: pending | running | completed | failed | cached

  // Input parameters
  scriptStyle: text("script_style").notNull().default("educational"),
  scriptTone: text("script_tone").notNull().default("engaging"),
  targetDurationMinutes: integer("target_duration_minutes").notNull().default(10),
  targetAudience: text("target_audience"),
  language: text("language").notNull().default("en"),
  version: integer("version").notNull().default(1),

  // Core content — JSON
  scenes: json("scenes").$type<object[]>().notNull().default([]),
  sceneTimeline: json("scene_timeline").$type<object[]>().notNull().default([]),
  narrationTiming: json("narration_timing").$type<object[]>().notNull().default([]),
  visualCues: json("visual_cues").$type<object[]>().notNull().default([]),

  // Production metrics
  totalDurationSeconds: integer("total_duration_seconds"),
  sceneCount: integer("scene_count"),
  imageCount: integer("image_count"),
  editingComplexityScore: real("editing_complexity_score"),
  estimatedRenderTimeMinutes: integer("estimated_render_time_minutes"),
  estimatedCostUsd: real("estimated_cost_usd"),
  visualPacing: text("visual_pacing"),
  narrationPacing: text("narration_pacing"),

  // Pipeline
  providers: json("providers").$type<string[]>().notNull().default([]),
  usedProviders: json("used_providers").$type<string[]>().notNull().default([]),
  jobId: text("job_id"),
  logs: json("logs").$type<string[]>().notNull().default([]),
  errorMessage: text("error_message"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});
