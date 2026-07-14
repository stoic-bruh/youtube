import { pgTable, text, integer, real, timestamp, json } from "drizzle-orm/pg-core";

// ── Subtitle Results ──────────────────────────────────────────────────────────
// Post-Processing Engine — Subtitle Engine. Transcribes the real rendered
// video's audio track (Whisper, via faster-whisper), falling back to the
// known-correct narration script text (mapped onto real Voice section
// timestamps) when the audio track contains no detectable speech. Produces
// SRT/VTT/ASS files plus metadata for burned-in / animated / karaoke captions.

export const subtitleResults = pgTable("subtitle_results", {
  id: text("id").primaryKey(),
  renderId: text("render_id").notNull(),

  status: text("status").notNull().default("pending"),
  // enum: pending | running | completed | failed

  language: text("language").notNull().default("en"),
  usedProvider: text("used_provider"),
  // enum: whisper | script-narration
  providers: json("providers").$type<string[]>().notNull().default([]),

  // Structured timestamp tiers
  words: json("words").$type<object[]>().notNull().default([]),
  sentences: json("sentences").$type<object[]>().notNull().default([]),
  paragraphs: json("paragraphs").$type<object[]>().notNull().default([]),

  // Export formats — full file contents + on-disk paths
  srtContent: text("srt_content"),
  vttContent: text("vtt_content"),
  assContent: text("ass_content"),
  srtPath: text("srt_path"),
  vttPath: text("vtt_path"),
  assPath: text("ass_path"),

  // Presentation metadata
  burnedMetadata: json("burned_metadata").$type<object>().notNull().default({}),
  animatedCaptionMetadata: json("animated_caption_metadata").$type<object>().notNull().default({}),
  karaokeMetadata: json("karaoke_metadata").$type<object>().notNull().default({}),
  style: json("style").$type<object>().notNull().default({}),
  captionPresets: json("caption_presets").$type<object[]>().notNull().default([]),
  speakerMetadata: json("speaker_metadata").$type<object[]>().notNull().default([]),

  // Metrics
  avgConfidence: real("avg_confidence"),
  wordCount: integer("word_count"),
  durationMs: integer("duration_ms"),

  logs: json("logs").$type<string[]>().notNull().default([]),
  errorMessage: text("error_message"),

  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});
