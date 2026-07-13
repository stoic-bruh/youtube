import { pgTable, text, real, integer, boolean, timestamp, json } from "drizzle-orm/pg-core";

export const voiceResults = pgTable("voice_results", {
  id: text("id").primaryKey(),
  scriptId: text("script_id").notNull(),
  status: text("status").notNull().default("pending"),
  // enum: pending | running | completed | failed | cached
  voiceId: text("voice_id").notNull().default("alloy"),
  speed: real("speed").notNull().default(1.0),
  language: text("language").notNull().default("en"),
  // Structured JSON
  sections: json("sections").$type<object[]>().notNull().default([]),
  // Metrics
  totalDurationMs: integer("total_duration_ms"),
  wordCount: integer("word_count"),
  sampleRate: integer("sample_rate"),
  audioFormat: text("audio_format"),
  normalized: boolean("normalized").notNull().default(false),
  targetLoudnessLufs: real("target_loudness_lufs").notNull().default(-14.0),
  costUsd: real("cost_usd"),
  // Pipeline
  usedProvider: text("used_provider"),
  providers: json("providers").$type<string[]>().notNull().default([]),
  jobId: text("job_id"),
  logs: json("logs").$type<string[]>().notNull().default([]),
  errorMessage: text("error_message"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});
