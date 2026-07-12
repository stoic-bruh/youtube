import { pgTable, text, real, integer, timestamp, json } from "drizzle-orm/pg-core";

export const researchResults = pgTable("research_results", {
  id: text("id").primaryKey(),
  topic: text("topic").notNull(),
  topicNormalized: text("topic_normalized").notNull(),
  targetAudience: text("target_audience"),
  videoLengthMinutes: integer("video_length_minutes").notNull().default(10),
  language: text("language").notNull().default("en"),
  style: text("style").notNull().default("educational"),
  tone: text("tone").notNull().default("engaging"),
  status: text("status").notNull().default("pending"),
  // enum: pending | running | completed | failed | cached
  jobId: text("job_id"),
  summary: text("summary"),
  confidenceScore: real("confidence_score"),
  estimatedDifficulty: text("estimated_difficulty"),
  sections: json("sections").$type<object[]>().notNull().default([]),
  references: json("references").$type<object[]>().notNull().default([]),
  keywords: json("keywords").$type<object[]>().notNull().default([]),
  providers: json("providers").$type<string[]>().notNull().default([]),
  usedProviders: json("used_providers").$type<string[]>().notNull().default([]),
  logs: json("logs").$type<string[]>().notNull().default([]),
  errorMessage: text("error_message"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});
