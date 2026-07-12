import { pgTable, text, timestamp, jsonb, integer, index } from "drizzle-orm/pg-core";
import { createInsertSchema, createSelectSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const jobsTable = pgTable(
  "jobs",
  {
    id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
    type: text("type").notNull(),
    status: text("status", {
      enum: ["pending", "running", "completed", "failed", "cancelled", "retrying"],
    })
      .notNull()
      .default("pending"),
    projectId: text("project_id"),
    pipelineId: text("pipeline_id"),
    payload: jsonb("payload").$type<Record<string, unknown>>().default({}),
    result: jsonb("result").$type<Record<string, unknown>>(),
    error: text("error"),
    retryCount: integer("retry_count").notNull().default(0),
    maxRetries: integer("max_retries").notNull().default(3),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    startedAt: timestamp("started_at", { withTimezone: true }),
    completedAt: timestamp("completed_at", { withTimezone: true }),
  },
  (t) => [
    index("jobs_status_idx").on(t.status),
    index("jobs_project_id_idx").on(t.projectId),
    index("jobs_type_idx").on(t.type),
  ],
);

export const insertJobSchema = createInsertSchema(jobsTable).omit({
  id: true,
  createdAt: true,
});
export const selectJobSchema = createSelectSchema(jobsTable);
export type InsertJob = z.infer<typeof insertJobSchema>;
export type Job = typeof jobsTable.$inferSelect;
