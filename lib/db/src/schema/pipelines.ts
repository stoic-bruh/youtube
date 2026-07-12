import { pgTable, text, timestamp, jsonb, integer, index } from "drizzle-orm/pg-core";
import { createInsertSchema, createSelectSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const pipelinesTable = pgTable(
  "pipelines",
  {
    id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
    projectId: text("project_id").notNull(),
    status: text("status", {
      enum: ["queued", "running", "completed", "failed", "cancelled"],
    })
      .notNull()
      .default("queued"),
    currentStage: text("current_stage"),
    progress: integer("progress").notNull().default(0),
    stages: jsonb("stages")
      .$type<
        Array<{
          name: string;
          status: "pending" | "running" | "completed" | "failed" | "skipped";
          order: number;
          startedAt: string | null;
          completedAt: string | null;
          durationMs: number | null;
          error: string | null;
        }>
      >()
      .default([]),
    errorMessage: text("error_message"),
    startedAt: timestamp("started_at", { withTimezone: true }).notNull().defaultNow(),
    completedAt: timestamp("completed_at", { withTimezone: true }),
  },
  (t) => [
    index("pipelines_project_id_idx").on(t.projectId),
    index("pipelines_status_idx").on(t.status),
  ],
);

export const insertPipelineSchema = createInsertSchema(pipelinesTable).omit({
  id: true,
  startedAt: true,
});
export const selectPipelineSchema = createSelectSchema(pipelinesTable);
export type InsertPipeline = z.infer<typeof insertPipelineSchema>;
export type Pipeline = typeof pipelinesTable.$inferSelect;
