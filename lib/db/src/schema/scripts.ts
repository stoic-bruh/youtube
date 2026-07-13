import { pgTable, text, real, integer, timestamp, json } from "drizzle-orm/pg-core";

export const scriptResults = pgTable("script_results", {
  id: text("id").primaryKey(),
  researchId: text("research_id"),
  topic: text("topic").notNull(),
  title: text("title"),
  status: text("status").notNull().default("pending"),
  // enum: pending | running | completed | failed | cached
  style: text("style").notNull().default("educational"),
  tone: text("tone").notNull().default("engaging"),
  language: text("language").notNull().default("en"),
  targetAudience: text("target_audience"),
  targetDurationMinutes: integer("target_duration_minutes").notNull().default(10),
  version: integer("version").notNull().default(1),
  // Core content
  hook: text("hook"),
  introduction: text("introduction"),
  outro: text("outro"),
  callToAction: text("call_to_action"),
  // Structured JSON
  sections: json("sections").$type<object[]>().notNull().default([]),
  narrationTiming: json("narration_timing").$type<object[]>().notNull().default([]),
  emphasisMarkers: json("emphasis_markers").$type<object[]>().notNull().default([]),
  pauses: json("pauses").$type<object[]>().notNull().default([]),
  pronunciationHints: json("pronunciation_hints").$type<object[]>().notNull().default([]),
  visualCues: json("visual_cues").$type<object[]>().notNull().default([]),
  versions: json("versions").$type<object[]>().notNull().default([]),
  // Metrics
  wordCount: integer("word_count"),
  estimatedDurationSeconds: integer("estimated_duration_seconds"),
  readingTimeSeconds: integer("reading_time_seconds"),
  sceneCount: integer("scene_count"),
  pacingWpm: real("pacing_wpm"),
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
