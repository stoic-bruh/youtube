import { Router } from "express";
import { db } from "@workspace/db";
import { pipelinesTable, projectsTable } from "@workspace/db";
import { eq, desc, and, sql } from "drizzle-orm";

const router = Router();

// GET /pipelines
router.get("/", async (req, res) => {
  try {
    const { project_id, status, limit = "50" } = req.query as Record<string, string>;
    const conditions = [];
    if (project_id) conditions.push(eq(pipelinesTable.projectId, project_id));
    if (status) conditions.push(eq(pipelinesTable.status, status as never));

    const [rows, [{ count }]] = await Promise.all([
      db
        .select()
        .from(pipelinesTable)
        .where(conditions.length ? and(...conditions) : undefined)
        .orderBy(desc(pipelinesTable.startedAt))
        .limit(Number(limit)),
      db
        .select({ count: sql<number>`cast(count(*) as integer)` })
        .from(pipelinesTable)
        .where(conditions.length ? and(...conditions) : undefined),
    ]);

    res.json({ items: rows, total: count });
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// GET /pipelines/:id
router.get("/:id", async (req, res) => {
  try {
    const [pipeline] = await db
      .select()
      .from(pipelinesTable)
      .where(eq(pipelinesTable.id, req.params.id));
    if (!pipeline) { res.status(404).json({ error: "Not found" }); return; }
    res.json(pipeline);
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// POST /pipelines/:id/cancel
router.post("/:id/cancel", async (req, res) => {
  try {
    const [pipeline] = await db
      .update(pipelinesTable)
      .set({ status: "cancelled", completedAt: new Date() })
      .where(eq(pipelinesTable.id, req.params.id))
      .returning();
    if (!pipeline) { res.status(404).json({ error: "Not found" }); return; }

    // Reflect on project
    await db
      .update(projectsTable)
      .set({ status: "cancelled", updatedAt: new Date() })
      .where(eq(projectsTable.id, pipeline.projectId));

    res.json(pipeline);
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// POST /pipelines/:id/retry
router.post("/:id/retry", async (req, res) => {
  try {
    const existingRows = await db
      .select()
      .from(pipelinesTable)
      .where(eq(pipelinesTable.id, req.params.id));
    const existing = existingRows[0];
    if (!existing) { res.status(404).json({ error: "Not found" }); return; }

    type PipelineStage = {
      name: string;
      status: "pending" | "running" | "completed" | "failed" | "skipped";
      order: number;
      startedAt: string | null;
      completedAt: string | null;
      durationMs: number | null;
      error: string | null;
    };
    const resetStages = (existing.stages as PipelineStage[]).map((s): PipelineStage => ({
      ...s,
      status: s.status === "completed" ? "completed" : "pending",
      error: null,
    }));

    const [pipeline] = await db
      .update(pipelinesTable)
      .set({ status: "queued", errorMessage: null, stages: resetStages })
      .where(eq(pipelinesTable.id, req.params.id))
      .returning();

    await db
      .update(projectsTable)
      .set({ status: "queued", updatedAt: new Date() })
      .where(eq(projectsTable.id, pipeline!.projectId));

    res.status(202).json(pipeline);
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
