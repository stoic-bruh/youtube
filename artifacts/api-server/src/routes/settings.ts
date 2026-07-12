import { Router } from "express";
import { db } from "@workspace/db";
import { settingsTable } from "@workspace/db";
import { eq } from "drizzle-orm";

const SETTINGS_ID = "default";

const router = Router();

async function ensureSettings() {
  const [existing] = await db
    .select()
    .from(settingsTable)
    .where(eq(settingsTable.id, SETTINGS_ID));
  if (!existing) {
    const [created] = await db
      .insert(settingsTable)
      .values({ id: SETTINGS_ID })
      .returning();
    return created;
  }
  return existing;
}

// GET /settings
router.get("/", async (req, res) => {
  try {
    const settings = await ensureSettings();
    res.json(settings);
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

// PATCH /settings
router.patch("/", async (req, res) => {
  try {
    await ensureSettings();
    const [updated] = await db
      .update(settingsTable)
      .set({ ...req.body, updatedAt: new Date() })
      .where(eq(settingsTable.id, SETTINGS_ID))
      .returning();
    res.json(updated);
  } catch (err) {
    req.log.error(err);
    res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
