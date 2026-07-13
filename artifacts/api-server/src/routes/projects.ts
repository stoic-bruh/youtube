import { Router } from "express";
import { db } from "@workspace/db";
import { projectsTable, pipelinesTable, insertProjectSchema } from "@workspace/db";
import { eq, desc, and, sql } from "drizzle-orm";
import { z } from "zod/v4";

const router = Router();

const PIPELINE_STAGES = [
  "research",
  "script",
  "scene_planning",
  "image_generation",
  "voice_generation",
  "video_editing",
  "subtitle_generation",
  "thumbnail_generation",
  "seo_generation",
  "upload",
] as const;

function buildDefaultStages() {
  return PIPELINE_STAGES.map((name, i) => ({
    name,
    status: "pending" as const,
    order: i,
    startedAt: null,
    completedAt: null,
    durationMs: null,
    error: null,
  }));
}

// GET /projects
router.get("/", async (req, res) => {
  try {
    const { status, limit = "50", offset = "0" } = req.query as Record<string, string>;
    const conditions = [];
    if (status) conditions.push(eq(projectsTable.status, status as never));

    const [rows, [{ count }]] = await Promise.all([
      db
        .select()
        .from(projectsTable)
        .where(conditions.length ? and(...conditions) : undefined)
        .orderBy(desc(projectsTable.createdAt))
        .limit(Number(limit))
        .offset(Number(offset)),
      db
        .select({ count: sql<number>`cast(count(*) as integer)` })
        .from(projectsTable)
        .where(conditions.length ? and(...conditions) : undefined),
    ]);

    res.json({ items: rows, total: count });
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// POST /projects
router.post("/", async (req, res) => {
  try {
    const parsed = insertProjectSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: "Invalid request", details: parsed.error }); return;
    }
    const [project] = await db
      .insert(projectsTable)
      .values(parsed.data)
      .returning();
    res.status(201).json(project);
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// GET /projects/:id
router.get("/:id", async (req, res) => {
  try {
    const [project] = await db
      .select()
      .from(projectsTable)
      .where(eq(projectsTable.id, req.params.id));
    if (!project) { res.status(404).json({ error: "Not found" }); return; }
    res.json(project);
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// PATCH /projects/:id
router.patch("/:id", async (req, res) => {
  try {
    const updateSchema = insertProjectSchema.partial();
    const parsed = updateSchema.safeParse(req.body);
    if (!parsed.success) {
      res.status(400).json({ error: "Invalid request", details: parsed.error }); return;
    }
    const [project] = await db
      .update(projectsTable)
      .set({ ...parsed.data, updatedAt: new Date() })
      .where(eq(projectsTable.id, req.params.id))
      .returning();
    if (!project) { res.status(404).json({ error: "Not found" }); return; }
    res.json(project);
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// DELETE /projects/:id
router.delete("/:id", async (req, res) => {
  try {
    const [deleted] = await db
      .delete(projectsTable)
      .where(eq(projectsTable.id, req.params.id))
      .returning();
    if (!deleted) { res.status(404).json({ error: "Not found" }); return; }
    res.status(204).send();
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// POST /projects/:id/run — start the full pipeline
router.post("/:id/run", async (req, res) => {
  try {
    const [project] = await db
      .select()
      .from(projectsTable)
      .where(eq(projectsTable.id, req.params.id));
    if (!project) { res.status(404).json({ error: "Not found" }); return; }

    // Create pipeline
    const [pipeline] = await db
      .insert(pipelinesTable)
      .values({
        projectId: project.id,
        status: "queued",
        stages: buildDefaultStages(),
      })
      .returning();

    // Update project status
    await db
      .update(projectsTable)
      .set({ status: "queued", pipelineId: pipeline.id, updatedAt: new Date() })
      .where(eq(projectsTable.id, project.id));

    res.status(202).json(pipeline);
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
