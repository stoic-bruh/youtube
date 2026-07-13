import { Router } from "express";
import { db } from "@workspace/db";
import { jobsTable } from "@workspace/db";
import { eq, desc, and, sql } from "drizzle-orm";

const router = Router();

// GET /jobs
router.get("/", async (req, res) => {
  try {
    const { status, type, limit = "50" } = req.query as Record<string, string>;
    const conditions = [];
    if (status) conditions.push(eq(jobsTable.status, status as never));
    if (type) conditions.push(eq(jobsTable.type, type));

    const [rows, [{ count }]] = await Promise.all([
      db
        .select()
        .from(jobsTable)
        .where(conditions.length ? and(...conditions) : undefined)
        .orderBy(desc(jobsTable.createdAt))
        .limit(Number(limit)),
      db
        .select({ count: sql<number>`cast(count(*) as integer)` })
        .from(jobsTable)
        .where(conditions.length ? and(...conditions) : undefined),
    ]);

    res.json({ items: rows, total: count });
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// GET /jobs/:id
router.get("/:id", async (req, res) => {
  try {
    const [job] = await db
      .select()
      .from(jobsTable)
      .where(eq(jobsTable.id, req.params.id));
    if (!job) { res.status(404).json({ error: "Not found" }); return; }
    res.json(job);
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// POST /jobs/:id/retry
router.post("/:id/retry", async (req, res) => {
  try {
    const [job] = await db
      .update(jobsTable)
      .set({ status: "retrying", error: null, startedAt: null, completedAt: null })
      .where(eq(jobsTable.id, req.params.id))
      .returning();
    if (!job) { res.status(404).json({ error: "Not found" }); return; }
    res.status(202).json(job);
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// POST /jobs/:id/cancel
router.post("/:id/cancel", async (req, res) => {
  try {
    const [job] = await db
      .update(jobsTable)
      .set({ status: "cancelled", completedAt: new Date() })
      .where(eq(jobsTable.id, req.params.id))
      .returning();
    if (!job) { res.status(404).json({ error: "Not found" }); return; }
    res.json(job);
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
