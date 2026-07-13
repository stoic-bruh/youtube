/**
 * Storyboard routes — POST /storyboards, GET /storyboards, GET /storyboards/:id, DELETE /storyboards/:id
 *
 * Full mock pipeline runs asynchronously (setImmediate) after the 202 response,
 * mirroring the research.ts / scripts.ts pattern exactly.
 */
import { Router, type Request, type Response } from "express";
import { db } from "@workspace/db";
import { storyboardResults } from "@workspace/db";
import { eq, desc } from "drizzle-orm";
import { z } from "zod";
import { randomUUID } from "crypto";

const router = Router();

// ── Validation ─────────────────────────────────────────────────────────────────

const StoryboardInputSchema = z.object({
  scriptId: z.string().optional().nullable(),
  researchId: z.string().optional().nullable(),
  topic: z.string().min(3).max(500),
  scriptStyle: z.enum(["educational", "documentary", "storytelling", "tutorial", "news", "long_form", "shorts"])
    .optional().default("educational"),
  scriptTone: z.enum(["engaging", "authoritative", "casual", "inspirational", "conversational"])
    .optional().default("engaging"),
  targetDurationMinutes: z.number().int().min(1).max(120).optional().default(10),
  targetAudience: z.string().optional().default("general audience"),
  language: z.string().optional().default("en"),
  providers: z.array(z.string()).min(1).max(4).optional().default(["openai", "claude"]),
});

// ── Helpers ────────────────────────────────────────────────────────────────────

function ts(): string {
  return `[${new Date().toTimeString().slice(0, 8)}]`;
}

class SeededRandom {
  private seed: number;
  constructor(seedStr: string) {
    let h = 0;
    for (let i = 0; i < seedStr.length; i++) h = ((h << 5) - h + seedStr.charCodeAt(i)) | 0;
    this.seed = Math.abs(h) || 1;
  }
  next(): number {
    this.seed ^= this.seed << 13;
    this.seed ^= this.seed >> 17;
    this.seed ^= this.seed << 5;
    return (Math.abs(this.seed) % 10_000) / 10_000;
  }
  int(lo: number, hi: number): number { return Math.floor(lo + this.next() * (hi - lo + 1)); }
  float(lo: number, hi: number): number { return +(lo + this.next() * (hi - lo)).toFixed(3); }
  choice<T>(arr: T[]): T { return arr[Math.floor(this.next() * arr.length)]; }
  sample<T>(arr: T[], k: number): T[] {
    const pool = [...arr]; const out: T[] = [];
    for (let i = 0; i < Math.min(k, pool.length); i++) {
      const j = Math.floor(this.next() * (pool.length - i)) + i;
      [pool[i], pool[j]] = [pool[j], pool[i]];
      out.push(pool[i]);
    }
    return out;
  }
}

// ── Lookup tables (mirrors Python mock_base.py) ────────────────────────────────

const SHOT_TYPES = ["wide", "medium", "close_up", "establishing", "over_the_shoulder", "aerial"];
const CAMERA_MOVEMENTS = ["static", "pan_left", "pan_right", "zoom_in", "zoom_out", "dolly_in", "tracking"];
const CAMERA_ANGLES = ["eye_level", "high_angle", "low_angle", "dutch_tilt", "overhead"];
const TRANSITIONS = ["cut", "dissolve", "fade", "wipe_left", "zoom_transition"];
const LIGHTING_STYLES: Record<string, string[]> = {
  educational: ["studio", "soft", "natural"],
  documentary: ["natural", "cinematic", "dramatic"],
  tutorial: ["high_key", "studio", "soft"],
  storytelling: ["dramatic", "low_key", "golden_hour"],
  news: ["studio", "high_key"],
  long_form: ["cinematic", "natural"],
  shorts: ["neon", "high_key"],
};
const EMOTIONS = ["curious", "excited", "pensive", "dramatic", "hopeful", "determined",
                  "surprised", "contemplative", "energetic", "calm", "intense", "inspiring"];
const MUSIC_MOODS = [
  "ambient electronic", "uplifting orchestral", "tense minimalist", "warm acoustic",
  "cinematic epic", "neutral documentary", "subtle tension", "bright and optimistic",
  "mysterious atmospheric", "energetic indie",
];
const SFX = ["subtle whoosh", "soft keyboard clicks", "ambient office noise", "gentle chime",
             "page turn", "digital beep", "subtle breath", "paper rustle"];
const PALETTES: Record<string, string[][]> = {
  educational: [["#1a1a2e", "#16213e", "#0f3460", "#e94560"], ["#2c3e50", "#3498db", "#ecf0f1", "#e74c3c"]],
  documentary: [["#1c1c1e", "#2c2c2e", "#8e8e93", "#ffffff"], ["#1a0a00", "#4a2000", "#d4782a", "#f5e6d3"]],
  tutorial:    [["#0a192f", "#172a45", "#64ffda", "#ccd6f6"], ["#1e1e2e", "#313244", "#89b4fa", "#cba6f7"]],
  storytelling:[["#1a0533", "#3d1066", "#9b59b6", "#f1c40f"]],
  news:        [["#000000", "#1a1a1a", "#cc0000", "#ffffff"]],
  long_form:   [["#0d0d0d", "#1a1a1a", "#333333", "#e0e0e0"]],
  shorts:      [["#ff0050", "#00f593", "#0044ff", "#ffffff"]],
};
const BROLL: Record<string, string[]> = {
  educational: ["Close-up of textbook pages turning", "Person writing on whiteboard", "Abstract data visualization"],
  documentary: ["Archival footage", "Sweeping aerial landscape", "Interview subject in natural setting"],
  tutorial: ["Screen recording with highlights", "Hands typing on keyboard", "Split-screen before/after"],
  storytelling: ["Emotional reaction close-up", "Symbolic object in dramatic lighting"],
  news: ["Location establishing shot", "Interview soundbite", "Data chart animation"],
  long_form: ["Deep-focus environment shot", "Expert interview setup"],
  shorts: ["Fast-cut reaction shot", "Dynamic text animation"],
};
const STOCK: Record<string, string[]> = {
  educational: ["Person studying with books", "Classroom lecture", "Digital circuit board"],
  documentary: ["Sunrise over mountains", "Urban timelapse", "Ocean waves"],
  tutorial: ["Developer at dual monitors", "Whiteboard session", "Organized workspace"],
  storytelling: ["Two people in conversation", "Silhouette at sunset"],
  news: ["Press conference exterior", "Business district street"],
  long_form: ["Library interior", "Mountain summit"],
  shorts: ["Smartphone screen recording", "Trendy cafe interior"],
};
const SCENE_TITLES: Record<string, string[]> = {
  educational: ["Opening Hook", "Context Setting", "Core Concept", "Deep Dive", "Visual Explanation",
                "Real-World Application", "Common Misconception", "Key Takeaway", "Summary", "Call to Engage"],
  documentary: ["Opening Sequence", "World Setting", "Subject Introduction", "The Problem",
                "Historical Context", "Turning Point", "Expert Perspective", "The Resolution"],
  tutorial: ["What You'll Build", "Prerequisites", "Step 1: Setup", "Step 2: Core Logic",
             "Step 3: Testing", "Common Errors", "Final Result", "Next Steps"],
  storytelling: ["The World Before", "The Inciting Incident", "Rising Tension", "The Dark Moment",
                 "The Revelation", "The Climax", "Resolution", "The Lesson"],
  news: ["Breaking Development", "Background Context", "Key Facts", "Expert Analysis", "Looking Ahead"],
  long_form: ["Cold Open", "Thesis", "Historical Background", "Core Argument 1", "Core Argument 2",
              "Evidence & Data", "Case Study", "Synthesis", "Future Outlook", "Conclusion"],
  shorts: ["Hook", "The Point", "The Proof", "The Call"],
};
const OBJECTS: Record<string, string[]> = {
  educational: ["textbook", "whiteboard", "laptop", "notebook", "calculator"],
  documentary: ["camera", "newspaper", "map", "microphone", "journal"],
  tutorial: ["keyboard", "mouse", "monitor", "diagram", "terminal"],
  storytelling: ["candle", "clock", "letter", "photograph", "door"],
  news: ["microphone", "notepad", "studio desk", "monitor"],
  long_form: ["books", "notepad", "chart", "coffee cup"],
  shorts: ["smartphone", "icon", "text graphic"],
};
const NEGATIVE_PROMPT =
  "blurry, low quality, watermark, text, logo, grain, overexposed, underexposed, " +
  "amateur, cartoon, anime, ugly, deformed, extra limbs, bad anatomy, duplicate, NSFW";

// ── Mock generator ────────────────────────────────────────────────────────────

interface SceneData {
  scene_number: number; scene_title: string;
  start_time_ms: number; end_time_ms: number; duration_ms: number;
  narration: string; visual_description: string; visual_type: string;
  prompts: { image_prompt: string; negative_prompt: string; video_prompt: string; style_preset: string };
  shot_type: string; camera_angle: string; camera_movement: string;
  zoom_instructions: string | null; pan_instructions: string | null;
  animation_suggestions: object[]; transition_type: string; transition_duration_ms: number;
  scene_emotion: string; color_palette: string[]; lighting_style: string;
  background_description: string; foreground_description: string;
  characters: string[]; objects: string[];
  text_overlay_suggestions: string[];
  subtitle_timing: { start_ms: number; end_ms: number; text: string; speaker: string };
  sound_effect_suggestions: string[]; background_music_mood: string;
  b_roll_suggestions: string[]; stock_footage_suggestions: string[];
  asset_requirements: object[]; importance_score: number;
  estimated_image_count: number; estimated_video_length_seconds: number;
}

function generateMockStoryboard(
  provider: string,
  topic: string,
  style: string,
  targetDurationMinutes: number,
  scriptSections: Array<{ title: string; content: string; duration_seconds?: number }>,
  hook: string,
  intro: string,
  cta: string,
  outro: string,
): {
  title: string;
  scenes: SceneData[];
  sceneCount: number;
  imageCount: number;
  totalDurationSeconds: number;
  editingComplexityScore: number;
  estimatedRenderTimeMinutes: number;
  estimatedCostUsd: number;
  visualPacing: string;
  narrationPacing: string;
  narrationTiming: object[];
  visualCues: object[];
  sceneTimeline: object[];
  confidence: number;
} {
  const rng = new SeededRandom(`${provider}:${topic.toLowerCase().trim()}:${style}`);
  const topicCap = topic.charAt(0).toUpperCase() + topic.slice(1);
  const paletteOptions = PALETTES[style] ?? PALETTES["educational"];
  const palette = rng.choice(paletteOptions);
  const brollPool = BROLL[style] ?? BROLL["educational"];
  const stockPool = STOCK[style] ?? STOCK["educational"];
  const objectPool = OBJECTS[style] ?? OBJECTS["educational"];
  const lightingOptions = LIGHTING_STYLES[style] ?? LIGHTING_STYLES["educational"];
  const titlePool = [...(SCENE_TITLES[style] ?? SCENE_TITLES["educational"])];

  // Build parts list
  type Part = { title: string; content: string; duration_seconds: number };
  const parts: Part[] = [];
  if (hook) parts.push({ title: "Hook", content: hook, duration_seconds: 15 });
  if (intro) parts.push({ title: "Introduction", content: intro, duration_seconds: 20 });
  for (const s of scriptSections) {
    parts.push({ title: s.title, content: s.content, duration_seconds: s.duration_seconds ?? 45 });
  }
  if (cta) parts.push({ title: "Call to Action", content: cta, duration_seconds: 15 });
  if (outro) parts.push({ title: "Outro", content: outro, duration_seconds: 10 });

  if (parts.length === 0) {
    // Fallback: synthesise from topic
    const titles = titlePool.slice(0, 5);
    for (const t of titles) {
      parts.push({ title: t, content: `Content for ${t} about ${topic}.`, duration_seconds: targetDurationMinutes * 60 / titles.length });
    }
  }

  const scenesPerMinute = { shorts: 8, news: 5, tutorial: 4, educational: 3.5, documentary: 3, storytelling: 3, long_form: 3 }[style] ?? 3.5;
  const targetSceneCount = Math.max(4, Math.min(80, Math.round(targetDurationMinutes * scenesPerMinute)));

  const totalPartDur = parts.reduce((s, p) => s + p.duration_seconds, 0) || 1;
  let remaining = targetSceneCount;
  const partCounts: number[] = parts.map((p, i) => {
    if (i === parts.length - 1) return remaining;
    const cnt = Math.max(1, Math.round((p.duration_seconds / totalPartDur) * targetSceneCount));
    remaining -= cnt;
    return cnt;
  });

  const scenes: SceneData[] = [];
  let sceneNum = 1;
  let elapsedMs = 0;

  for (let pi = 0; pi < parts.length; pi++) {
    const part = parts[pi];
    const nScenes = partCounts[pi];
    const partDurMs = Math.round(part.duration_seconds * 1000);
    const sceneDurMs = Math.max(2000, Math.floor(partDurMs / nScenes));
    const words = part.content.split(/\s+/);
    const wpScene = Math.max(1, Math.floor(words.length / nScenes));

    for (let si = 0; si < nScenes; si++) {
      const srng = new SeededRandom(`${provider}:${topic}:${style}:s${sceneNum}`);
      const durMs = sceneDurMs + srng.int(-500, 500);
      const startMs = elapsedMs;
      const endMs = startMs + durMs;
      elapsedMs = endMs;

      const narrationSnippet = words.slice(si * wpScene, (si + 1) * wpScene).join(" ") || part.content.slice(0, 120);
      const sceneTitle = titlePool.length > 0 ? titlePool.shift()! : part.title;
      const shotType = sceneNum === 1 ? "establishing" : srng.choice(SHOT_TYPES);
      const camAngle = srng.choice(CAMERA_ANGLES);
      const camMove = srng.choice(CAMERA_MOVEMENTS);
      const lighting = srng.choice(lightingOptions);
      const transition = (sceneNum === 1) ? "fade" : srng.choice(TRANSITIONS);
      const transDurMs = transition === "cut" ? 0 : srng.int(400, 800);
      const emotion = srng.choice(EMOTIONS);
      const broll = srng.sample(brollPool, srng.int(1, 2));
      const stock = srng.sample(stockPool, srng.int(1, 2));
      const sfx = srng.sample(SFX, srng.int(1, 2));
      const music = srng.choice(MUSIC_MOODS);
      const objs = srng.sample(objectPool, srng.int(1, 3));
      const importance = (sceneNum === 1 || part.title === "Call to Action") ? 0.95 : srng.float(0.4, 0.85);
      const imgCount = srng.int(1, 3);

      const visualDesc = `${shotType.replace("_", " ")} shot — ${sceneTitle.toLowerCase()} for "${topic}". ${lighting} lighting.`;
      const imagePrompt =
        `Cinematic ${style.replace("_", " ")} scene — ${sceneTitle.toLowerCase()} visual for '${topic}'. ` +
        `${lighting} lighting, ${palette[0]} and ${palette[1]} color palette. ` +
        `Shot on ARRI Alexa, anamorphic lens, shallow depth of field. Ultra-realistic 8K.`;
      const videoPrompt =
        `${camMove.replace("_", " ")} camera movement. ${lighting} atmosphere. ` +
        `${sceneTitle.toLowerCase()} — ${topic}. Cinematic grade. 24fps.`;

      const zoomInst = camMove.includes("zoom") ? `${camMove === "zoom_in" ? "Slow zoom in" : "Slow zoom out"} over ${Math.round(durMs / 1000)}s` : null;
      const panInst = camMove.includes("pan") ? `${camMove === "pan_left" ? "Left" : "Right"} pan at 5°/second` : null;

      const textOverlays: string[] = [];
      if (srng.float(0, 1) > 0.5) textOverlays.push(`KEY POINT: ${sceneTitle.toUpperCase()}`);
      if (pi === 0 && si === 0) textOverlays.push(`📌 ${topicCap}`);

      const animations: object[] = [];
      if (textOverlays.length > 0) {
        animations.push({ element: "text_overlay", animation_type: srng.choice(["fade_in", "slide_in", "typewriter"]), duration_ms: srng.int(300, 600), delay_ms: 0 });
      }
      if (srng.float(0, 1) > 0.5) {
        animations.push({ element: "scene_frame", animation_type: "fade_in", duration_ms: srng.int(200, 400), delay_ms: 0 });
      }

      const assets: object[] = [
        { asset_type: "image", description: `AI-generated image: ${sceneTitle} for '${topic}'`, is_required: true, source_type: "generate" },
      ];
      if (sfx.length > 0) {
        assets.push({ asset_type: "sound_effect", description: sfx[0], is_required: false, source_type: "stock", search_query: `${sfx[0]} sound effect` });
      }

      scenes.push({
        scene_number: sceneNum,
        scene_title: sceneTitle,
        start_time_ms: startMs,
        end_time_ms: endMs,
        duration_ms: durMs,
        narration: narrationSnippet,
        visual_description: visualDesc,
        visual_type: srng.choice(["b_roll", "illustration", "animation", "text_overlay"]),
        prompts: { image_prompt: imagePrompt, negative_prompt: NEGATIVE_PROMPT, video_prompt: videoPrompt, style_preset: "cinematic" },
        shot_type: shotType,
        camera_angle: camAngle,
        camera_movement: camMove,
        zoom_instructions: zoomInst,
        pan_instructions: panInst,
        animation_suggestions: animations,
        transition_type: transition,
        transition_duration_ms: transDurMs,
        scene_emotion: emotion,
        color_palette: palette,
        lighting_style: lighting,
        background_description: srng.choice([
          `Clean ${style.replace("_", " ")} background with subtle gradient`,
          `Blurred environment suggesting ${topic}`,
          `Abstract geometric pattern in matching tones`,
        ]),
        foreground_description: srng.choice([
          `Subject engaging with ${srng.choice(objs)}`,
          "Hands demonstrating concept",
          "Animated icon overlay",
        ]),
        characters: srng.float(0, 1) > 0.5 ? srng.choice([["presenter"], ["expert"], ["student", "teacher"]]) : [],
        objects: objs,
        text_overlay_suggestions: textOverlays,
        subtitle_timing: { start_ms: startMs, end_ms: endMs, text: narrationSnippet.slice(0, 120), speaker: "narrator" },
        sound_effect_suggestions: sfx,
        background_music_mood: music,
        b_roll_suggestions: broll,
        stock_footage_suggestions: stock,
        asset_requirements: assets,
        importance_score: +importance.toFixed(3),
        estimated_image_count: imgCount,
        estimated_video_length_seconds: +(durMs / 1000).toFixed(1),
      });

      sceneNum++;
    }
  }

  const totalDurS = Math.floor(elapsedMs / 1000);
  const imageCount = scenes.reduce((s, sc) => s + sc.estimated_image_count, 0);
  const sceneCount = scenes.length;
  const dissolveCount = scenes.filter(s => s.transition_type !== "cut").length;
  const animCount = scenes.reduce((s, sc) => s + sc.animation_suggestions.length, 0);
  const complexity = +Math.min(1.0, (
    0.3 * Math.min(1, sceneCount / 40) +
    0.3 * Math.min(1, animCount / (sceneCount * 2)) +
    0.2 * Math.min(1, dissolveCount / sceneCount) +
    0.2 * Math.min(1, imageCount / (sceneCount * 2))
  )).toFixed(3);
  const renderMin = Math.max(1, Math.round(imageCount * 0.15 + sceneCount * 0.05));
  const costUsd = +(imageCount * 0.04 + sceneCount * 0.01).toFixed(2);
  const visualPacing = style === "shorts" ? "fast" : style === "documentary" ? "very_slow" : "medium";
  const narrationPacing = "conversational";

  // Narration timing & visual cues
  const narrationTiming = scenes.map(s => ({
    scene_number: s.scene_number, scene_title: s.scene_title,
    start_ms: s.start_time_ms, end_ms: s.end_time_ms,
    wpm: 130, word_count: s.narration.split(/\s+/).length, speaker_note: "narrator",
  }));
  const visualCues: object[] = [];
  for (const s of scenes) {
    visualCues.push({ time_ms: s.start_time_ms, cue_type: s.transition_type === "cut" ? "cut" : "transition",
                      description: `Scene ${s.scene_number}: ${s.scene_title}`, scene_number: s.scene_number, duration_ms: s.transition_duration_ms });
    if (s.text_overlay_suggestions.length > 0) {
      visualCues.push({ time_ms: s.start_time_ms + 200, cue_type: "graphic",
                        description: s.text_overlay_suggestions[0], scene_number: s.scene_number, duration_ms: 3000 });
    }
  }
  const sceneTimeline = scenes.map(s => ({
    scene_number: s.scene_number, scene_title: s.scene_title,
    start_time_ms: s.start_time_ms, end_time_ms: s.end_time_ms, duration_ms: s.duration_ms,
    shot_type: s.shot_type, transition_type: s.transition_type,
    visual_type: s.visual_type, importance_score: s.importance_score,
  }));

  const titleOpts = [
    `${topicCap} — Full Production Storyboard`,
    `Storyboard: ${topicCap}`,
    `${topicCap} | Scene Plan v1`,
    `Production Storyboard — ${topicCap}`,
  ];
  const title = new SeededRandom(`title:${provider}:${topic}`).choice(titleOpts);
  const confidenceBase: Record<string, number> = { openai: 0.91, gemini: 0.88, claude: 0.93, openrouter: 0.85 };
  const confidence = +(confidenceBase[provider] ?? 0.88 + new SeededRandom(`conf:${provider}`).float(-0.03, 0.03)).toFixed(3);

  return { title, scenes, sceneCount, imageCount, totalDurationSeconds: totalDurS,
           editingComplexityScore: complexity, estimatedRenderTimeMinutes: renderMin,
           estimatedCostUsd: costUsd, visualPacing, narrationPacing,
           narrationTiming, visualCues, sceneTimeline, confidence };
}

// ── Async processor ────────────────────────────────────────────────────────────

async function processStoryboard(id: string, input: z.infer<typeof StoryboardInputSchema>): Promise<void> {
  const { topic, scriptStyle, scriptTone, providers, targetDurationMinutes } = input;

  const addLog = async (level: string, msg: string) => {
    const current = await db.select({ logs: storyboardResults.logs }).from(storyboardResults).where(eq(storyboardResults.id, id));
    const logs: string[] = (current[0]?.logs as string[]) || [];
    logs.push(`${ts()} ${level.padEnd(5)} ${msg}`);
    await db.update(storyboardResults).set({ logs, updatedAt: new Date() }).where(eq(storyboardResults.id, id));
  };

  try {
    await db.update(storyboardResults).set({ status: "running", updatedAt: new Date() }).where(eq(storyboardResults.id, id));
    await addLog("INFO", `Starting storyboard generation for: '${topic}'`);
    await addLog("INFO", `Style: ${scriptStyle} | Tone: ${scriptTone} | Duration: ${targetDurationMinutes}min`);
    await addLog("INFO", `Providers: ${providers.join(", ")}`);

    // Phase 1: fetch from all providers
    await addLog("INFO", "Phase 1/4 — Generating scenes from providers in parallel");
    const t0 = Date.now();
    await new Promise(r => setTimeout(r, 300));
    const providerResults = providers.map(p =>
      generateMockStoryboard(p, topic, scriptStyle, targetDurationMinutes, [], "", "", "", "")
    );
    await addLog("INFO", `Providers completed in ${Date.now() - t0}ms — ${providers.length} OK, 0 failed`);

    // Phase 2: primary selection
    await addLog("INFO", "Phase 2/4 — Selecting primary provider and merging scenes");
    await new Promise(r => setTimeout(r, 100));
    const primary = providerResults.reduce((best, r) => r.confidence > best.confidence ? r : best, providerResults[0]);
    await addLog("INFO", `Primary: ${providers[providerResults.indexOf(primary)]} (confidence ${primary.confidence})`);

    // Merge unique scenes from secondary providers
    const seenTitles = new Set(primary.scenes.map(s => s.scene_title.toLowerCase()));
    const mergedScenes = [...primary.scenes];
    for (const r of providerResults) {
      if (r === primary) continue;
      for (const s of r.scenes) {
        if (!seenTitles.has(s.scene_title.toLowerCase()) && s.importance_score >= 0.8) {
          seenTitles.add(s.scene_title.toLowerCase());
          mergedScenes.push({ ...s, scene_number: mergedScenes.length + 1 });
        }
      }
    }
    await addLog("INFO", `Merged scene count: ${mergedScenes.length}`);

    // Phase 3: merge metadata
    await addLog("INFO", "Phase 3/4 — Merging narration timing and visual cues");
    await new Promise(r => setTimeout(r, 50));
    await addLog("INFO", `Timeline: ${primary.sceneTimeline.length} | Cues: ${primary.visualCues.length} | Timing: ${primary.narrationTiming.length}`);

    // Phase 4: metrics
    await addLog("INFO", "Phase 4/4 — Finalising production metrics");
    await new Promise(r => setTimeout(r, 50));
    await addLog("INFO",
      `Scenes: ${primary.sceneCount} | Images: ${primary.imageCount} | ` +
      `Duration: ${primary.totalDurationSeconds}s | ` +
      `Complexity: ${primary.editingComplexityScore} | ` +
      `Render: ${primary.estimatedRenderTimeMinutes}min | ` +
      `Cost: $${primary.estimatedCostUsd}`
    );
    await addLog("INFO", "Storyboard complete — writing to database");

    const current = await db.select({ logs: storyboardResults.logs }).from(storyboardResults).where(eq(storyboardResults.id, id));
    const finalLogs = (current[0]?.logs as string[]) || [];

    await db.update(storyboardResults).set({
      status: "completed",
      title: primary.title,
      scenes: mergedScenes as any,
      sceneTimeline: primary.sceneTimeline as any,
      narrationTiming: primary.narrationTiming as any,
      visualCues: primary.visualCues as any,
      totalDurationSeconds: primary.totalDurationSeconds,
      sceneCount: primary.sceneCount,
      imageCount: primary.imageCount,
      editingComplexityScore: primary.editingComplexityScore,
      estimatedRenderTimeMinutes: primary.estimatedRenderTimeMinutes,
      estimatedCostUsd: primary.estimatedCostUsd,
      visualPacing: primary.visualPacing,
      narrationPacing: primary.narrationPacing,
      usedProviders: providers,
      logs: finalLogs,
      completedAt: new Date(),
      updatedAt: new Date(),
    }).where(eq(storyboardResults.id, id));

  } catch (err: any) {
    const errMsg = err?.message || String(err);
    const current = await db.select({ logs: storyboardResults.logs }).from(storyboardResults).where(eq(storyboardResults.id, id));
    const logs = (current[0]?.logs as string[]) || [];
    logs.push(`${ts()} ERROR Storyboard failed: ${errMsg}`);
    await db.update(storyboardResults).set({ status: "failed", errorMessage: errMsg, logs, updatedAt: new Date() }).where(eq(storyboardResults.id, id));
  }
}

// ── Routes ────────────────────────────────────────────────────────────────────

function toApi(r: typeof storyboardResults.$inferSelect): object {
  return {
    id: r.id, scriptId: r.scriptId, researchId: r.researchId, topic: r.topic, title: r.title,
    status: r.status, scriptStyle: r.scriptStyle, scriptTone: r.scriptTone,
    targetDurationMinutes: r.targetDurationMinutes, targetAudience: r.targetAudience,
    language: r.language, version: r.version,
    scenes: r.scenes || [], sceneTimeline: r.sceneTimeline || [],
    narrationTiming: r.narrationTiming || [], visualCues: r.visualCues || [],
    totalDurationSeconds: r.totalDurationSeconds, sceneCount: r.sceneCount,
    imageCount: r.imageCount, editingComplexityScore: r.editingComplexityScore,
    estimatedRenderTimeMinutes: r.estimatedRenderTimeMinutes, estimatedCostUsd: r.estimatedCostUsd,
    visualPacing: r.visualPacing, narrationPacing: r.narrationPacing,
    providers: r.providers || [], usedProviders: r.usedProviders || [],
    jobId: r.jobId, logs: r.logs || [], errorMessage: r.errorMessage,
    createdAt: r.createdAt, updatedAt: r.updatedAt, completedAt: r.completedAt,
  };
}

// GET /storyboards
router.get("/", async (req: Request, res: Response) => {
  const status = req.query.status as string | undefined;
  const limit = Math.min(Number(req.query.limit) || 50, 200);
  const offset = Number(req.query.offset) || 0;
  let rows = await db.select().from(storyboardResults).orderBy(desc(storyboardResults.createdAt)).limit(limit + 1).offset(offset);
  if (status) rows = rows.filter((r: typeof rows[number]) => r.status === status);
  res.json({ items: rows.slice(0, limit).map(toApi), total: rows.length });
});

// POST /storyboards
router.post("/", async (req: Request, res: Response) => {
  const parse = StoryboardInputSchema.safeParse(req.body);
  if (!parse.success) { res.status(400).json({ error: parse.error.flatten() }); return; }
  const input = parse.data;
  const id = randomUUID();

  await db.insert(storyboardResults).values({
    id,
    scriptId: input.scriptId ?? null,
    researchId: input.researchId ?? null,
    topic: input.topic,
    status: "pending",
    scriptStyle: input.scriptStyle,
    scriptTone: input.scriptTone,
    targetDurationMinutes: input.targetDurationMinutes,
    targetAudience: input.targetAudience,
    language: input.language,
    version: 1,
    providers: input.providers,
    usedProviders: [],
    scenes: [],
    sceneTimeline: [],
    narrationTiming: [],
    visualCues: [],
    logs: [`${ts()} INFO  Storyboard job created — providers: ${input.providers.join(", ")}`],
    jobId: randomUUID(),
    createdAt: new Date(),
    updatedAt: new Date(),
  });

  const [created] = await db.select().from(storyboardResults).where(eq(storyboardResults.id, id));
  res.status(202).json(toApi(created));

  setImmediate(() => { processStoryboard(id, input).catch(console.error); });
});

// GET /storyboards/:id
router.get("/:id", async (req: Request, res: Response) => {
  const id = req.params["id"] as string;
  const [row] = await db.select().from(storyboardResults).where(eq(storyboardResults.id, id));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  res.json(toApi(row));
});

// DELETE /storyboards/:id
router.delete("/:id", async (req: Request, res: Response) => {
  const id = req.params["id"] as string;
  const [row] = await db.select().from(storyboardResults).where(eq(storyboardResults.id, id));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  await db.delete(storyboardResults).where(eq(storyboardResults.id, id));
  res.status(204).send();
});

export default router;
