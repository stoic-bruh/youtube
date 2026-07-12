import { pgTable, text, timestamp, jsonb, index } from "drizzle-orm/pg-core";
import { createInsertSchema, createSelectSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const projectsTable = pgTable(
  "projects",
  {
    id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
    title: text("title").notNull(),
    topic: text("topic").notNull(),
    description: text("description"),
    status: text("status", {
      enum: ["draft", "queued", "running", "completed", "failed", "cancelled"],
    })
      .notNull()
      .default("draft"),
    thumbnailUrl: text("thumbnail_url"),
    videoUrl: text("video_url"),
    youtubeId: text("youtube_id"),
    youtubeUrl: text("youtube_url"),
    pipelineId: text("pipeline_id"),
    tags: jsonb("tags").$type<string[]>().default([]),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [index("projects_status_idx").on(t.status)],
);

export const insertProjectSchema = createInsertSchema(projectsTable).omit({
  id: true,
  createdAt: true,
  updatedAt: true,
});
export const selectProjectSchema = createSelectSchema(projectsTable);
export type InsertProject = z.infer<typeof insertProjectSchema>;
export type Project = typeof projectsTable.$inferSelect;
