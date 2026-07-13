import {
  pgTable,
  text,
  real,
  integer,
  boolean,
  timestamp,
  json,
  uniqueIndex,
} from "drizzle-orm/pg-core";

// ── Asset Results ─────────────────────────────────────────────────────────────

export const assetResults = pgTable("asset_results", {
  id: text("id").primaryKey(),
  storyboardId: text("storyboard_id").notNull(),
  sceneId: text("scene_id").notNull(),

  assetKind: text("asset_kind").notNull(), // image | video | svg | chart | map | icon
  provider: text("provider"),
  providerAssetId: text("provider_asset_id"),

  sourceUrl: text("source_url"),
  license: text("license").notNull().default("unknown"),

  prompt: text("prompt"),
  negativePrompt: text("negative_prompt"),
  generationParameters: json("generation_parameters").$type<object>().notNull().default({}),

  width: integer("width"),
  height: integer("height"),
  aspectRatio: text("aspect_ratio"),

  status: text("status").notNull().default("pending"),
  // enum: pending | searching | downloading | generating | ready | failed | cached
  costEstimateUsd: real("cost_estimate_usd"),
  generationTimeMs: integer("generation_time_ms"),

  fileSizeBytes: integer("file_size_bytes"),
  localCachePath: text("local_cache_path"),
  thumbnailPath: text("thumbnail_path"),

  tags: json("tags").$type<string[]>().notNull().default([]),
  qualityScore: real("quality_score"),
  relevanceScore: real("relevance_score"),

  logs: json("logs").$type<string[]>().notNull().default([]),
  errorMessage: text("error_message"),

  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});

// ── Asset Cache ───────────────────────────────────────────────────────────────

export const assetCache = pgTable(
  "asset_cache",
  {
    id: text("id").primaryKey(),
    cacheKey: text("cache_key").notNull(),
    assetKind: text("asset_kind").notNull(),
    provider: text("provider").notNull(),
    sourceUrl: text("source_url"),
    localPath: text("local_path"),
    thumbnailPath: text("thumbnail_path"),
    fileSizeBytes: integer("file_size_bytes"),
    width: integer("width"),
    height: integer("height"),
    license: text("license").notNull().default("unknown"),
    tags: json("tags").$type<string[]>().notNull().default([]),
    qualityScore: real("quality_score"),
    hitCount: integer("hit_count").notNull().default(0),
    isValid: boolean("is_valid").notNull().default(true),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    lastAccessedAt: timestamp("last_accessed_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [uniqueIndex("asset_cache_key_idx").on(table.cacheKey)],
);

// ── Asset Provider Metadata ───────────────────────────────────────────────────

export const assetProviderMetadata = pgTable("asset_provider_metadata", {
  id: text("id").primaryKey(),
  providerName: text("provider_name").notNull().unique(),
  providerType: text("provider_type").notNull(), // stock | generate | icon
  isEnabled: boolean("is_enabled").notNull().default(true),
  totalRequests: integer("total_requests").notNull().default(0),
  successfulRequests: integer("successful_requests").notNull().default(0),
  failedRequests: integer("failed_requests").notNull().default(0),
  avgLatencyMs: real("avg_latency_ms"),
  avgCostUsd: real("avg_cost_usd"),
  totalCostUsd: real("total_cost_usd").notNull().default(0),
  cacheHits: integer("cache_hits").notNull().default(0),
  supportedKinds: json("supported_kinds").$type<string[]>().notNull().default([]),
  config: json("config").$type<object>().notNull().default({}),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});
