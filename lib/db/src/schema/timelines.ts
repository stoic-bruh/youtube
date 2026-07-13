import {
  pgTable,
  text,
  integer,
  timestamp,
  json,
} from "drizzle-orm/pg-core";

// ── Timeline Results ──────────────────────────────────────────────────────────

export const timelineResults = pgTable("timeline_results", {
  id: text("id").primaryKey(),
  storyboardId: text("storyboard_id").notNull(),
  scriptId: text("script_id"),

  topic: text("topic").notNull().default(""),
  title: text("title"),

  status: text("status").notNull().default("pending"),
  // enum: pending | running | completed | failed

  totalDurationMs: integer("total_duration_ms"),
  totalScenes: integer("total_scenes"),

  // JSON track/scene data — same pattern as storyboard scenes
  tracks: json("tracks").$type<object[]>().notNull().default([]),
  scenes: json("scenes").$type<object[]>().notNull().default([]),
  markers: json("markers").$type<object[]>().notNull().default([]),
  renderPlan: json("render_plan").$type<object>().notNull().default({}),
  metadata: json("metadata").$type<object>().notNull().default({}),
  validationErrors: json("validation_errors").$type<string[]>().notNull().default([]),

  logs: json("logs").$type<string[]>().notNull().default([]),
  errorMessage: text("error_message"),

  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});
