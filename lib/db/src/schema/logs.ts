import { pgTable, text, timestamp, jsonb, index } from "drizzle-orm/pg-core";
import { createInsertSchema, createSelectSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const logsTable = pgTable(
  "logs",
  {
    id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
    level: text("level", { enum: ["debug", "info", "warn", "error"] })
      .notNull()
      .default("info"),
    message: text("message").notNull(),
    service: text("service").notNull(),
    projectId: text("project_id"),
    jobId: text("job_id"),
    meta: jsonb("meta").$type<Record<string, unknown>>(),
    timestamp: timestamp("timestamp", { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [
    index("logs_level_idx").on(t.level),
    index("logs_service_idx").on(t.service),
    index("logs_timestamp_idx").on(t.timestamp),
  ],
);

export const insertLogSchema = createInsertSchema(logsTable).omit({
  id: true,
  timestamp: true,
});
export const selectLogSchema = createSelectSchema(logsTable);
export type InsertLog = z.infer<typeof insertLogSchema>;
export type Log = typeof logsTable.$inferSelect;
