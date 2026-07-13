import { Router, type IRouter } from "express";
import healthRouter from "./health";
import researchRouter from "./research";
import scriptsRouter from "./scripts";
import storyboardsRouter from "./storyboards";
import assetsRouter from "./assets";
import projectsRouter from "./projects";
import pipelinesRouter from "./pipelines";
import jobsRouter from "./jobs";
import analyticsRouter from "./analytics";
import logsRouter from "./logs";
import settingsRouter from "./settings";
import timelinesRouter from "./timelines";
import voicesRouter from "./voices";

const router: IRouter = Router();

router.use(healthRouter);
router.use("/research", researchRouter);
router.use("/scripts", scriptsRouter);
router.use("/storyboards", storyboardsRouter);
router.use("/assets", assetsRouter);
router.use("/timelines", timelinesRouter);
router.use("/voices", voicesRouter);
router.use("/projects", projectsRouter);
router.use("/pipelines", pipelinesRouter);
router.use("/jobs", jobsRouter);
router.use("/analytics", analyticsRouter);
router.use("/logs", logsRouter);
router.use("/settings", settingsRouter);

export default router;
