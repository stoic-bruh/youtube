import { Router } from "express";
import { db } from "@workspace/db";
import { logsTable } from "@workspace/db";
import { eq, desc, and, sql } from "drizzle-orm";

const router = Router();

// GET /logs
router.get("/", async (req, res) => {
  try {
    const { level, service, limit = "100" } = req.query as Record<string, string>;
    const conditions = [];
    if (level) conditions.push(eq(logsTable.level, level as never));
    if (service) conditions.push(eq(logsTable.service, service));

    const [rows, [{ count }]] = await Promise.all([
      db
        .select()
        .from(logsTable)
        .where(conditions.length ? and(...conditions) : undefined)
        .orderBy(desc(logsTable.timestamp))
        .limit(Number(limit)),
      db
        .select({ count: sql<number>`cast(count(*) as integer)` })
        .from(logsTable)
        .where(conditions.length ? and(...conditions) : undefined),
    ]);

    res.json({ items: rows, total: count });
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
