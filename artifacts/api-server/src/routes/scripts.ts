/**
 * Script routes — POST /scripts, GET /scripts, GET /scripts/:id, DELETE /scripts/:id
 *
 * Full mock pipeline runs asynchronously after the API response so the Replit
 * preview works without Redis/Celery. Production routes these to the Python
 * FastAPI service.
 */
import { Router, type Request, type Response } from "express";
import { db } from "@workspace/db";
import { scriptResults } from "@workspace/db";
import { eq, desc } from "drizzle-orm";
import { z } from "zod";
import { randomUUID } from "crypto";

const router = Router();

// ── Validation ─────────────────────────────────────────────────────────────────

const ScriptInputSchema = z.object({
  researchId: z.string().optional().nullable(),
  topic: z.string().min(3).max(500),
  style: z.enum(["educational", "documentary", "storytelling", "tutorial", "news", "long_form", "shorts"]).optional().default("educational"),
  tone: z.enum(["engaging", "authoritative", "casual", "inspirational", "conversational"]).optional().default("engaging"),
  language: z.string().optional().default("en"),
  targetAudience: z.string().optional().default("general audience"),
  targetDurationMinutes: z.number().int().min(1).max(120).optional().default(10),
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
    for (let i = 0; i < seedStr.length; i++) {
      h = ((h << 5) - h + seedStr.charCodeAt(i)) | 0;
    }
    this.seed = Math.abs(h) || 1;
  }
  next(): number {
    this.seed ^= this.seed << 13;
    this.seed ^= this.seed >> 17;
    this.seed ^= this.seed << 5;
    return (Math.abs(this.seed) % 10000) / 10000;
  }
  choice<T>(arr: T[]): T { return arr[Math.floor(this.next() * arr.length)]; }
  range(min: number, max: number): number { return Math.floor(min + this.next() * (max - min + 1)); }
  float(min: number, max: number): number { return +(min + this.next() * (max - min)).toFixed(3); }
  sample<T>(arr: T[], k: number): T[] {
    const a = [...arr];
    const result: T[] = [];
    for (let i = 0; i < Math.min(k, a.length); i++) {
      const j = Math.floor(this.next() * (a.length - i)) + i;
      [a[i], a[j]] = [a[j], a[i]];
      result.push(a[i]);
    }
    return result;
  }
}

function countWords(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

// ── Mock script generator ──────────────────────────────────────────────────────

const HOOKS: Record<string, string[]> = {
  educational: [
    "What if everything you thought you knew about {topic} was only half the story? Today, we're going to go deeper — far deeper — than most videos dare to venture. By the time we're done, you'll have a crystal-clear understanding of {topic} that will completely change how you see this subject.",
    "Here's a question that trips up even experts: what actually makes {topic} work? Stick with me for the next few minutes and you'll walk away with an understanding that most people spend years trying to piece together.",
    "In the next ten minutes, I'm going to explain {topic} so clearly that you could teach it to someone else. No jargon, no hand-waving — just the real thing.",
  ],
  documentary: [
    "There is a moment — a precise, identifiable moment in history — when {topic} changed everything. This is the story of that moment, and what came after.",
    "The story of {topic} is not what you think it is. It's stranger, messier, and far more human than the textbook version.",
  ],
  storytelling: [
    "I want to tell you a story about {topic}. It starts, as most good stories do, with a problem nobody knew how to solve — and ends with something none of us saw coming.",
    "Three years ago, I didn't know the first thing about {topic}. Today, it shapes how I think about nearly everything. This is the story of that journey.",
  ],
  tutorial: [
    "By the end of this video, you're going to be able to work with {topic} confidently — even if you've never touched it before. Every step, in order, no assumptions.",
    "You've probably been putting off learning {topic} because it looks complicated. The hard parts aren't where you think they are. Let me show you.",
  ],
  news: [
    "Breaking developments in {topic} are forcing experts to reassess assumptions that have held for years. Here's what's happening, why it matters, and what comes next.",
    "Three separate developments involving {topic} converged this week into a story that's bigger than any of them individually. We're going to untangle it.",
  ],
  long_form: [
    "What you're about to watch is the most comprehensive breakdown of {topic} we've ever produced. We're covering everything — the history, the mechanics, the controversies, the future — in a single sitting.",
    "Over the next thirty minutes, we're going on a deep dive into {topic}. Real deep. From first principles all the way to cutting-edge applications.",
  ],
  shorts: [
    "Here's the one thing you need to know about {topic} right now — and most people get it completely wrong.",
    "Stop what you're doing. This will take 60 seconds and change how you think about {topic} forever.",
  ],
};

const SECTION_TITLES: Record<string, string[][]> = {
  educational: [
    ["What Is {topic}?", "How {topic} Works", "Why {topic} Matters", "Real-World Applications", "Common Mistakes"],
    ["The Core Mechanism", "The Key Principles", "Practical Implications", "Case Studies", "Pitfalls to Avoid"],
  ],
  documentary: [
    ["Origins", "The Turning Point", "Ripple Effects", "The Future of {topic}"],
    ["How It Began", "The Critical Years", "Present Day", "What Comes Next"],
  ],
  storytelling: [
    ["The Problem Nobody Could Solve", "The Journey of Discovery", "The Breakthrough", "Lessons Learned"],
  ],
  tutorial: [
    ["Step 1: Setup & Foundation", "Step 2: Core Implementation", "Step 3: Advanced Techniques", "Troubleshooting"],
    ["Getting Started", "Building the Core", "Polishing and Optimising", "Common Issues & Fixes"],
  ],
  news: [
    ["What Happened", "Key Context", "Expert Perspectives", "What It Means"],
  ],
  long_form: [
    ["First Principles", "The Core Mechanism", "Practical Applications", "The Controversies", "The Future", "Summary & Synthesis"],
  ],
  shorts: [
    ["The Key Insight"],
  ],
};

const SECTION_CONTENT_TEMPLATES = [
  "Let's talk about {aspect} — this is where most explanations fall short, and it's the piece that makes everything else click. {topic} works through a mechanism that, once you see it, becomes obvious in retrospect. The practical implication is that when you encounter {topic} in the real world, you'll be able to recognise exactly what's happening and why it matters. Practitioners who deeply understand this move faster and make fewer mistakes.",
  "Now let's get into {aspect}. This is the part that trips up most people, not because it's genuinely hard, but because it's usually explained in the wrong order. When we look at {topic} through this lens, several things that seemed complicated become straightforward. The critical insight here is that the same principles apply whether you're looking at a simple case or a complex one.",
  "Here's where {topic} gets really interesting: {aspect}. This dimension is what separates a surface-level understanding from a deep one. The practical payoff is significant — understanding {aspect} means you can make better decisions and anticipate outcomes that others miss entirely.",
  "We need to address {aspect} directly, because it's central to understanding {topic}. A lot of the confusion around {topic} stems from people skipping this part or treating it as an optional detail. When you understand {aspect} clearly, a lot of other puzzles about {topic} resolve themselves automatically.",
  "Let's zoom in on {aspect}. This is one of those concepts that sounds technical but is actually quite intuitive once you approach it the right way. The underlying structure of {topic} in this area follows a pattern we see repeated across many different fields — which means our intuitions from those fields carry over beautifully.",
];

const OUTROS: Record<string, string> = {
  educational: "So let's bring it all together. We started with the question of what {topic} actually is, moved through how it works, and explored why it matters. {topic} is learnable — completely, genuinely learnable by anyone. The path just requires taking it one layer at a time, which is exactly what we did today. Thanks for watching, and I'll see you in the next one.",
  documentary: "The story of {topic} is still being written. The decisions being made right now will determine how this chapter ends and what the next one looks like. The more people understand what's at stake, the better those decisions will be. Thanks for watching.",
  storytelling: "Every story about {topic} is really a story about what it means to pursue understanding. I hope this one gave you something to think about — and maybe, something to go try for yourself. Until next time.",
  tutorial: "You've got everything you need to start working with {topic}. The first time you apply this, it'll feel a little unfamiliar. The second time, easier. By the fifth time, it'll feel obvious. Be patient with yourself, and I'll see you in the next tutorial.",
  news: "This story will continue to evolve, and we'll be right here covering it. Stay engaged, stay informed, and we'll see you next time.",
  long_form: "We've covered an enormous amount of ground today. Take your time with it — revisit sections if you need to. Understanding {topic} at this level of depth is genuinely rare. Thank you, truly, for your time and attention.",
  shorts: "That's it. Simple, right? The more you understand about {topic}, the more these patterns make sense. See you tomorrow.",
};

const CTAS: Record<string, string> = {
  educational: "If this video helped you understand {topic} better, I'd genuinely appreciate a like — it tells me this kind of deep-dive content is worth making. Subscribe if you want more breakdowns like this. Drop a comment below with your biggest question about {topic} — I read every one.",
  documentary: "If you found this story as compelling as I did, hit subscribe — we have more documentary-style deep dives on the way. Leave a comment: what aspect of {topic} do you think deserves its own full episode?",
  storytelling: "Stories like this one don't get told enough. If this resonated, share it with someone who would appreciate it. And subscribe — there are more stories like this coming.",
  tutorial: "You made it — you now know how to work with {topic}. In the description, I've linked to the resources mentioned and a practice exercise. If you hit any snags, post your question in the comments.",
  news: "We'll be updating this story as developments continue. Subscribe and hit the bell so you don't miss the follow-up. Let me know in the comments what you think is the most significant implication.",
  long_form: "Thank you for spending this time on {topic} with me. There's a full transcript and chapter guide in the description. And I'm curious: after watching, what's the one question you still have?",
  shorts: "Follow for more {topic} insights like this — new one every day. Tell me in the comments: did this change how you think about it?",
};

function generateMockScript(
  provider: string,
  topic: string,
  style: string,
  tone: string,
  targetDurationMinutes: number,
): {
  title: string; hook: string; introduction: string; outro: string; callToAction: string;
  sections: object[]; wordCount: number; estimatedDurationSeconds: number;
  readingTimeSeconds: number; sceneCount: number; pacingWpm: number;
  narrationTiming: object[]; emphasisMarkers: object[]; pauses: object[];
  pronunciationHints: object[]; visualCues: object[]; confidence: number;
} {
  const rng = new SeededRandom(`${provider}:${topic.toLowerCase().trim()}:${style}`);
  const topicCap = topic.charAt(0).toUpperCase() + topic.slice(1);

  // Hook
  const hookOptions = HOOKS[style] ?? HOOKS["educational"];
  const hook = rng.choice(hookOptions).replace(/{topic}/g, topicCap);

  // Introduction
  const introduction = `Before we get into the details, let me give you a quick map of where we're going. `
    + `We'll start with the fundamentals of ${topic}, then go deeper into how it works at a mechanical level. `
    + `After that, we'll look at why it matters in the real world, and close with the key takeaways. `
    + `If you've ever felt like you almost-but-not-quite understood ${topic}, this is for you. Let's jump in.`;

  // Sections
  const sectionTitleOptions = SECTION_TITLES[style] ?? SECTION_TITLES["educational"];
  const sectionTitles = rng.choice(sectionTitleOptions)
    .map((t: string) => t.replace(/{topic}/g, topicCap));

  const adjectedCount = style === "shorts" ? 1
    : style === "long_form" ? sectionTitles.length
    : targetDurationMinutes <= 5 ? Math.min(2, sectionTitles.length)
    : Math.min(4, sectionTitles.length);

  const sections = sectionTitles.slice(0, adjectedCount).map((title: string, i: number) => {
    const template = rng.choice(SECTION_CONTENT_TEMPLATES);
    const aspects = ["the core mechanism", "the fundamental structure", "the underlying dynamics",
                     "the practical implications", "the key principles at work",
                     "how this applies in real-world scenarios"];
    const content = template.replace(/{topic}/g, topic).replace(/{aspect}/g, rng.choice(aspects));
    const wc = countWords(content);
    return {
      sectionType: i === 0 ? "main_point" : i % 3 === 1 ? "example" : "main_point",
      title,
      content,
      wordCount: wc,
      durationSeconds: Math.round((wc / 130) * 60),
      order: i,
      transitionIn: i > 0 ? rng.choice(["Now, with that in mind, let's move on.", "Building on that...", "This leads us naturally to..."]) : null,
      transitionOut: i < adjectedCount - 1 ? rng.choice(["Keep that in mind as we move to the next point.", "We'll return to this idea shortly."]) : null,
      storytellingNotes: i === 0 ? "Establish energy and pace here. Speak with confidence." : null,
      visualSuggestion: rng.choice([
        `Animated diagram for ${title}`,
        `B-roll showing ${topic} in action`,
        `Graphic: key statistics overlay`,
        `Screen recording or step-by-step visual`,
        `Title card: key term definition`,
      ]),
    };
  });

  // Outro & CTA
  const outroTemplate = OUTROS[style] ?? OUTROS["educational"];
  const outro = outroTemplate.replace(/{topic}/g, topicCap);
  const ctaTemplate = CTAS[style] ?? CTAS["educational"];
  const callToAction = ctaTemplate.replace(/{topic}/g, topicCap);

  // Title
  const titles = [
    `The Complete Guide to ${topicCap}`,
    `${topicCap}: Everything You Need to Know`,
    `Understanding ${topicCap} — From Zero to Expert`,
    `Why ${topicCap} Matters More Than You Think`,
    `${topicCap} Explained`,
  ];
  const title = rng.choice(titles);

  // Metrics
  const hookWc = countWords(hook);
  const introWc = countWords(introduction);
  const sectionWc = sections.reduce((s: number, sec: any) => s + (sec.wordCount as number), 0);
  const ctaWc = countWords(callToAction);
  const outroWc = countWords(outro);
  const wordCount = hookWc + introWc + sectionWc + ctaWc + outroWc;
  const pacingWpm = 130;
  const estimatedDurationSeconds = Math.round((wordCount / pacingWpm) * 60);
  const readingTimeSeconds = Math.round((wordCount / 200) * 60);
  const sceneCount = sections.length + 3;

  // Narration timing
  let elapsedMs = 0;
  const narrationTiming: object[] = [];
  const timingEntries: Array<{title: string; text: string; type: string}> = [
    { title: "Hook", text: hook, type: "hook" },
    { title: "Introduction", text: introduction, type: "introduction" },
    ...sections.map((s: any) => ({ title: s.title as string, text: s.content as string, type: "main_point" })),
    { title: "Call to Action", text: callToAction, type: "call_to_action" },
    { title: "Outro", text: outro, type: "outro" },
  ];
  const wpmByType: Record<string, number> = { hook: 120, introduction: 130, main_point: 135, call_to_action: 130, outro: 120 };
  for (const entry of timingEntries) {
    const wc = countWords(entry.text);
    const wpm = wpmByType[entry.type] ?? 130;
    const durMs = Math.round((wc / wpm) * 60000);
    narrationTiming.push({ sectionTitle: entry.title, startMs: elapsedMs, endMs: elapsedMs + durMs, wpm, wordCount: wc });
    elapsedMs += durMs;
  }

  // Emphasis markers
  const emphasisWords = [...new Set(topic.toLowerCase().split(/\s+/))].slice(0, 3);
  const emphasisTypes = ["strong", "raise_pitch", "pause_before"];
  const emphasisMarkers: object[] = emphasisWords.map((word: string, i: number) => ({
    text: word,
    position: hook.toLowerCase().indexOf(word),
    sectionIndex: 0,
    emphasisType: emphasisTypes[i % emphasisTypes.length],
  })).filter((e: any) => e.position >= 0);

  // Pauses
  const pauses: object[] = sections.slice(0, 3).map((_: any, i: number) => ({
    position: i * 200,
    durationMs: rng.range(500, 1500),
    pauseType: rng.choice(["medium", "dramatic", "short"]),
    context: `...pause before section ${i + 1}...`,
  }));

  // Pronunciation hints
  const techWords: Record<string, string> = {
    algorithm: "AL-guh-rith-um", neural: "NOOR-ul", quantum: "KWON-tum",
    cache: "KASH", schema: "SKEE-muh", heuristic: "hyoo-RIS-tik",
  };
  const pronunciationHints: object[] = Object.entries(techWords)
    .filter(([w]) => topic.toLowerCase().includes(w))
    .map(([word, phonetic]) => ({ word, phonetic, note: "Pronounce clearly" }))
    .slice(0, 3);

  // Visual cues
  const cueTypes = ["b_roll", "graphic", "title_card", "zoom", "lower_third"];
  const visualCues: object[] = narrationTiming.slice(0, 6).map((t: any, i: number) => ({
    timeMs: (t as any).startMs,
    description: rng.choice([
      `B-roll: ${topic} in real-world context`,
      `Animated graphic: key concept diagram`,
      `Title card: section header`,
      `Lower third: source citation`,
      `Zoom: emphasis on main point`,
      `B-roll: abstract visuals representing ${topic}`,
    ]),
    cueType: cueTypes[i % cueTypes.length],
    durationMs: rng.range(2000, 5000),
  }));

  const confidenceBase: Record<string, number> = { openai: 0.91, gemini: 0.88, claude: 0.93, openrouter: 0.85 };
  const confidence = +(((confidenceBase[provider] ?? 0.88) + rng.float(-0.03, 0.03))).toFixed(3);

  return {
    title, hook, introduction, outro, callToAction,
    sections, wordCount, estimatedDurationSeconds, readingTimeSeconds,
    sceneCount, pacingWpm, narrationTiming, emphasisMarkers, pauses,
    pronunciationHints, visualCues, confidence,
  };
}

// ── Async processor ────────────────────────────────────────────────────────────

async function processScript(id: string, input: z.infer<typeof ScriptInputSchema>): Promise<void> {
  const { topic, style, tone, providers, targetDurationMinutes } = input;

  const addLog = async (level: string, msg: string) => {
    const current = await db.select({ logs: scriptResults.logs }).from(scriptResults).where(eq(scriptResults.id, id));
    const logs: string[] = (current[0]?.logs as string[]) || [];
    logs.push(`${ts()} ${level.padEnd(5)} ${msg}`);
    await db.update(scriptResults).set({ logs, updatedAt: new Date() }).where(eq(scriptResults.id, id));
  };

  try {
    await db.update(scriptResults).set({ status: "running", updatedAt: new Date() }).where(eq(scriptResults.id, id));
    await addLog("INFO", `Starting script generation for topic: '${topic}'`);
    await addLog("INFO", `Style: ${style} | Tone: ${tone} | Duration: ${targetDurationMinutes}min`);
    await addLog("INFO", `Requested providers: ${providers.join(", ")}`);

    // Phase 1: provider generation
    await addLog("INFO", "Phase 1/4 — Fetching from script providers in parallel");
    const t0 = Date.now();
    await new Promise(r => setTimeout(r, 250));
    const providerResults = providers.map((p: string) =>
      generateMockScript(p, topic, style, tone, targetDurationMinutes)
    );
    await addLog("INFO", `Providers completed in ${Date.now() - t0}ms — ${providers.length} OK, 0 failed`);

    // Phase 2: select primary (highest confidence) and merge
    await addLog("INFO", "Phase 2/4 — Selecting primary provider and merging content");
    await new Promise(r => setTimeout(r, 100));
    const primary = providerResults.reduce((best: typeof providerResults[0], r: typeof providerResults[0]) =>
      r.confidence > best.confidence ? r : best, providerResults[0]);

    // Merge sections: keep primary's, add unique titles from others
    const seenTitles = new Set(primary.sections.map((s: any) => (s.title as string).toLowerCase()));
    const mergedSections = [...primary.sections];
    for (const r of providerResults) {
      if (r === primary) continue;
      for (const s of r.sections) {
        if (!seenTitles.has((s as any).title.toLowerCase())) {
          seenTitles.add((s as any).title.toLowerCase());
          mergedSections.push(s);
        }
      }
    }
    await addLog("INFO", `Merged ${mergedSections.length} sections from ${providers.length} provider(s)`);

    // Phase 3: metrics
    await addLog("INFO", "Phase 3/4 — Calculating word count, duration, and scene metrics");
    await new Promise(r => setTimeout(r, 50));
    await addLog("INFO", `Word count: ${primary.wordCount} | Duration: ${primary.estimatedDurationSeconds}s | Scenes: ${primary.sceneCount}`);

    // Phase 4: production metadata
    await addLog("INFO", "Phase 4/4 — Aggregating production metadata");
    await new Promise(r => setTimeout(r, 50));

    // Merge narration timing (use primary)
    const mergedTiming = [...primary.narrationTiming];
    const seenTimings = new Set(mergedTiming.map((t: any) => t.sectionTitle));
    for (const r of providerResults) {
      if (r === primary) continue;
      for (const t of r.narrationTiming) {
        if (!seenTimings.has((t as any).sectionTitle)) { seenTimings.add((t as any).sectionTitle); mergedTiming.push(t); }
      }
    }

    // Merge visual cues
    const seenCueTimes = new Set(primary.visualCues.map((v: any) => v.timeMs));
    const mergedCues = [...primary.visualCues];
    for (const r of providerResults) {
      if (r === primary) continue;
      for (const v of r.visualCues) {
        if (!seenCueTimes.has((v as any).timeMs)) { seenCueTimes.add((v as any).timeMs); mergedCues.push(v); }
      }
    }
    mergedCues.sort((a: any, b: any) => a.timeMs - b.timeMs);

    await addLog("INFO", `Timing entries: ${mergedTiming.length} | Emphasis markers: ${primary.emphasisMarkers.length} | Visual cues: ${mergedCues.length}`);
    await addLog("INFO", "Script generation complete — writing to database");

    const current = await db.select({ logs: scriptResults.logs }).from(scriptResults).where(eq(scriptResults.id, id));
    const finalLogs = (current[0]?.logs as string[]) || [];

    const topicCap = topic.charAt(0).toUpperCase() + topic.slice(1);
    await db.update(scriptResults).set({
      status: "completed",
      title: primary.title,
      hook: primary.hook,
      introduction: primary.introduction,
      outro: primary.outro,
      callToAction: primary.callToAction,
      sections: mergedSections as any,
      wordCount: primary.wordCount,
      estimatedDurationSeconds: primary.estimatedDurationSeconds,
      readingTimeSeconds: primary.readingTimeSeconds,
      sceneCount: primary.sceneCount,
      pacingWpm: primary.pacingWpm,
      narrationTiming: mergedTiming as any,
      emphasisMarkers: primary.emphasisMarkers as any,
      pauses: primary.pauses as any,
      pronunciationHints: primary.pronunciationHints as any,
      visualCues: mergedCues as any,
      usedProviders: providers,
      logs: finalLogs,
      completedAt: new Date(),
      updatedAt: new Date(),
    }).where(eq(scriptResults.id, id));

  } catch (err: any) {
    const errMsg = err?.message || String(err);
    const current = await db.select({ logs: scriptResults.logs }).from(scriptResults).where(eq(scriptResults.id, id));
    const logs = (current[0]?.logs as string[]) || [];
    logs.push(`${ts()} ERROR Script failed: ${errMsg}`);
    await db.update(scriptResults).set({ status: "failed", errorMessage: errMsg, logs, updatedAt: new Date() }).where(eq(scriptResults.id, id));
  }
}

// ── Routes ────────────────────────────────────────────────────────────────────

function toApi(r: typeof scriptResults.$inferSelect): object {
  return {
    id: r.id,
    researchId: r.researchId,
    topic: r.topic,
    title: r.title,
    status: r.status,
    style: r.style,
    tone: r.tone,
    language: r.language,
    targetAudience: r.targetAudience,
    targetDurationMinutes: r.targetDurationMinutes,
    version: r.version,
    hook: r.hook,
    introduction: r.introduction,
    outro: r.outro,
    callToAction: r.callToAction,
    sections: r.sections || [],
    wordCount: r.wordCount,
    estimatedDurationSeconds: r.estimatedDurationSeconds,
    readingTimeSeconds: r.readingTimeSeconds,
    sceneCount: r.sceneCount,
    pacingWpm: r.pacingWpm,
    narrationTiming: r.narrationTiming || [],
    emphasisMarkers: r.emphasisMarkers || [],
    pauses: r.pauses || [],
    pronunciationHints: r.pronunciationHints || [],
    visualCues: r.visualCues || [],
    versions: r.versions || [],
    providers: r.providers || [],
    usedProviders: r.usedProviders || [],
    jobId: r.jobId,
    logs: r.logs || [],
    errorMessage: r.errorMessage,
    createdAt: r.createdAt,
    updatedAt: r.updatedAt,
    completedAt: r.completedAt,
  };
}

// GET /scripts
router.get("/", async (req: Request, res: Response) => {
  const status = req.query.status as string | undefined;
  const limit = Math.min(Number(req.query.limit) || 50, 200);
  const offset = Number(req.query.offset) || 0;

  let rows = await db.select().from(scriptResults).orderBy(desc(scriptResults.createdAt)).limit(limit + 1).offset(offset);
  if (status) rows = rows.filter((r: typeof rows[number]) => r.status === status);
  res.json({ items: rows.slice(0, limit).map(toApi), total: rows.length });
});

// POST /scripts
router.post("/", async (req: Request, res: Response) => {
  const parse = ScriptInputSchema.safeParse(req.body);
  if (!parse.success) { res.status(400).json({ error: parse.error.flatten() }); return; }
  const input = parse.data;
  const id = randomUUID();

  await db.insert(scriptResults).values({
    id,
    researchId: input.researchId ?? null,
    topic: input.topic,
    status: "pending",
    style: input.style,
    tone: input.tone,
    language: input.language,
    targetAudience: input.targetAudience,
    targetDurationMinutes: input.targetDurationMinutes,
    version: 1,
    providers: input.providers,
    usedProviders: [],
    sections: [],
    narrationTiming: [],
    emphasisMarkers: [],
    pauses: [],
    pronunciationHints: [],
    visualCues: [],
    versions: [],
    logs: [`${ts()} INFO  Script job created — providers: ${input.providers.join(", ")}`],
    jobId: randomUUID(),
    createdAt: new Date(),
    updatedAt: new Date(),
  });

  const [created] = await db.select().from(scriptResults).where(eq(scriptResults.id, id));
  res.status(202).json(toApi(created));

  setImmediate(() => { processScript(id, input).catch(console.error); });
});

// GET /scripts/:id
router.get("/:id", async (req: Request, res: Response) => {
  const id = req.params["id"] as string;
  const [row] = await db.select().from(scriptResults).where(eq(scriptResults.id, id));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  res.json(toApi(row));
});

// DELETE /scripts/:id
router.delete("/:id", async (req: Request, res: Response) => {
  const id = req.params["id"] as string;
  const [row] = await db.select().from(scriptResults).where(eq(scriptResults.id, id));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  await db.delete(scriptResults).where(eq(scriptResults.id, id));
  res.status(204).send();
});

export default router;
