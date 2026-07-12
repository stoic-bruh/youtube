import { pgTable, text, timestamp, boolean, integer } from "drizzle-orm/pg-core";
import { createInsertSchema, createSelectSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const settingsTable = pgTable("settings", {
  id: text("id").primaryKey().default("default"),
  youtubeEnabled: boolean("youtube_enabled").notNull().default(false),
  autoUpload: boolean("auto_upload").notNull().default(false),
  defaultLanguage: text("default_language").notNull().default("en"),
  maxConcurrentJobs: integer("max_concurrent_jobs").notNull().default(3),
  openaiModel: text("openai_model").notNull().default("gpt-4o"),
  imageProvider: text("image_provider").notNull().default("dall-e-3"),
  voiceProvider: text("voice_provider").notNull().default("openai-tts"),
  defaultVideoQuality: text("default_video_quality").notNull().default("1080p"),
  notificationsEmail: text("notifications_email"),
  webhookUrl: text("webhook_url"),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const insertSettingsSchema = createInsertSchema(settingsTable);
export const selectSettingsSchema = createSelectSchema(settingsTable);
export type InsertSettings = z.infer<typeof insertSettingsSchema>;
export type Settings = typeof settingsTable.$inferSelect;
