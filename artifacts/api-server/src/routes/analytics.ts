import { Router } from "express";
import { db } from "@workspace/db";
import { projectsTable, pipelinesTable, jobsTable } from "@workspace/db";
import { sql, desc } from "drizzle-orm";

const router = Router();

// GET /analytics/dashboard
router.get("/dashboard", async (req, res) => {
  try {
    const [
      projectStats,
      jobStats,
      recentProjects,
    ] = await Promise.all([
      db
        .select({
          status: projectsTable.status,
          count: sql<number>`cast(count(*) as integer)`,
        })
        .from(projectsTable)
        .groupBy(projectsTable.status),
      db
        .select({
          status: jobsTable.status,
          count: sql<number>`cast(count(*) as integer)`,
        })
        .from(jobsTable)
        .groupBy(jobsTable.status),
      db
        .select()
        .from(projectsTable)
        .orderBy(desc(projectsTable.updatedAt))
        .limit(10),
    ]);

    const totalProjects = projectStats.reduce((sum, r) => sum + r.count, 0);
    const totalVideos = projectStats
      .filter((r) => r.status === "completed")
      .reduce((sum, r) => sum + r.count, 0);
    const activeJobs = jobStats
      .filter((r) => r.status === "running")
      .reduce((sum, r) => sum + r.count, 0);
    const queuedJobs = jobStats
      .filter((r) => r.status === "pending")
      .reduce((sum, r) => sum + r.count, 0);
    const failedJobs = jobStats
      .filter((r) => r.status === "failed")
      .reduce((sum, r) => sum + r.count, 0);
    const completedJobs = jobStats
      .filter((r) => r.status === "completed")
      .reduce((sum, r) => sum + r.count, 0);
    const totalJobsProcessed = completedJobs + failedJobs;
    const successRate =
      totalJobsProcessed > 0
        ? Math.round((completedJobs / totalJobsProcessed) * 100)
        : 0;

    const recentActivity = recentProjects.map((p) => ({
      id: p.id,
      type: "project",
      message: `Project "${p.title}" — ${p.status}`,
      projectId: p.id,
      status: p.status,
      timestamp: p.updatedAt.toISOString(),
    }));

    res.json({
      totalProjects,
      totalVideos,
      activeJobs,
      queuedJobs,
      failedJobs,
      successRate,
      totalRuntime: 0,
      projectsByStatus: projectStats,
      recentActivity,
    });
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// GET /analytics/pipeline-activity
router.get("/pipeline-activity", async (req, res) => {
  try {
    const { limit = "20" } = req.query as Record<string, string>;
    const pipelines = await db
      .select()
      .from(pipelinesTable)
      .orderBy(desc(pipelinesTable.startedAt))
      .limit(Number(limit));

    const items = pipelines.map((p) => ({
      id: p.id,
      type: "pipeline",
      message: `Pipeline ${p.status}${p.currentStage ? ` — stage: ${p.currentStage}` : ""}`,
      projectId: p.projectId,
      status: p.status,
      timestamp: p.startedAt.toISOString(),
    }));

    res.json({ items });
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// GET /analytics/stage-breakdown
router.get("/stage-breakdown", async (req, res) => {
  try {
    const stageNames = [
      "research", "script", "scene_planning", "image_generation",
      "voice_generation", "video_editing", "subtitle_generation",
      "thumbnail_generation", "seo_generation", "upload",
    ];
    const stages = stageNames.map((name) => ({
      name,
      completed: 0,
      failed: 0,
      avgDurationMs: 0,
    }));
    res.json({ stages });
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
