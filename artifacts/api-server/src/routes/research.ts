/**
 * Research routes — POST /research, GET /research, GET /research/:id, DELETE /research/:id
 *
 * The Node.js implementation runs the full research pipeline synchronously
 * (using a detached async job) so the Replit preview works without Redis/Celery.
 * Production Docker routes these to the Python FastAPI service.
 */
import { Router, type Request, type Response } from "express";
import { db } from "../db";
import { researchResults } from "@workspace/db/schema";
import { eq, desc, and, isNull } from "drizzle-orm";
import { z } from "zod";
import { randomUUID } from "crypto";

const router = Router();

// ── Validation ─────────────────────────────────────────────────────────────────

const ResearchInputSchema = z.object({
  topic: z.string().min(3).max(500),
  targetAudience: z.string().optional().default("general audience"),
  videoLengthMinutes: z.number().int().min(1).max(120).optional().default(10),
  language: z.string().optional().default("en"),
  style: z.enum(["educational", "entertaining", "documentary", "how-to"]).optional().default("educational"),
  tone: z.enum(["engaging", "authoritative", "casual", "inspirational"]).optional().default("engaging"),
  providers: z.array(z.string()).min(1).max(8).optional().default(["openai", "wikipedia", "duckduckgo"]),
});

// ── Helpers ────────────────────────────────────────────────────────────────────

function normalizeTopic(topic: string): string {
  return topic.toLowerCase().trim().replace(/[^\w\s]/g, "").replace(/\s+/g, " ");
}

function ts(): string {
  return `[${new Date().toTimeString().slice(0, 8)}]`;
}

function jaccard(a: string, b: string): number {
  const sa = new Set(a.toLowerCase().split(/\s+/));
  const sb = new Set(b.toLowerCase().split(/\s+/));
  if (sa.size === 0 || sb.size === 0) return 0;
  const intersection = new Set([...sa].filter(x => sb.has(x)));
  const union = new Set([...sa, ...sb]);
  return intersection.size / union.size;
}

function isNearDuplicate(text: string, seen: string[], threshold = 0.85): boolean {
  return seen.some(s => jaccard(text, s) > threshold);
}

// Seeded PRNG for deterministic mock data
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
  choice<T>(arr: T[]): T {
    return arr[Math.floor(this.next() * arr.length)];
  }
  shuffle<T>(arr: T[]): T[] {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(this.next() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }
  range(min: number, max: number): number {
    return Math.floor(min + this.next() * (max - min + 1));
  }
  float(min: number, max: number): number {
    return +(min + this.next() * (max - min)).toFixed(3);
  }
}

// ── Mock research generator (deterministic per topic+provider) ────────────────

interface MockRef {
  id: string; title: string; url: string; sourceType: string;
  author: string | null; publishedAt: string; snippet: string;
  credibilityScore: number; citationFormat: string; provider: string;
}
interface MockKw {
  term: string; relevance: number; searchVolume: number;
  difficulty: string; semanticTags: string[];
}
interface MockProviderResult {
  summary: string; keyPoints: string[]; facts: string[];
  concepts: string[]; timelineEvents: string[]; entities: string[];
  statistics: string[]; examples: string[]; analogies: string[];
  misconceptions: string[]; faqs: Array<{q: string; a: string}>;
  references: MockRef[]; keywords: MockKw[]; confidence: number;
}

const DOMAINS = [
  { d: "wikipedia.org", type: "wikipedia", cred: 0.88 },
  { d: "scholar.google.com", type: "academic", cred: 0.92 },
  { d: "nature.com", type: "academic", cred: 0.95 },
  { d: "medium.com", type: "web", cred: 0.55 },
  { d: "arxiv.org", type: "academic", cred: 0.87 },
  { d: "bbc.com", type: "news", cred: 0.82 },
  { d: "wired.com", type: "web", cred: 0.72 },
  { d: "reuters.com", type: "news", cred: 0.85 },
  { d: "nytimes.com", type: "news", cred: 0.84 },
  { d: "github.com", type: "web", cred: 0.78 },
];

function buildAPA(title: string, author: string | null, url: string, year: number): string {
  const a = author ? `${author}.` : "Anonymous.";
  return `${a} (${year}). ${title}. Retrieved from ${url}`;
}

function generateMockProviderResult(provider: string, topic: string, style: string, tone: string): MockProviderResult {
  const rng = new SeededRandom(`${provider}:${topic.toLowerCase().trim()}`);
  const audience = "general audience";

  const summary = `${topic.charAt(0).toUpperCase() + topic.slice(1)} is a compelling subject for YouTube. `
    + `This ${style} treatment explores the core mechanisms, real-world implications, and common misconceptions `
    + `surrounding ${topic}, offering ${tone} content suitable for both newcomers and practitioners.`;

  const keyPoints = rng.shuffle([
    `${topic.charAt(0).toUpperCase() + topic.slice(1)} has significantly evolved over the past decade.`,
    `The primary mechanism involves a multi-step process often misunderstood by beginners.`,
    `Leading experts have recently published findings that challenge conventional wisdom.`,
    `Practical applications span technology, healthcare, and finance.`,
    `Adoption has grown at over 40% year-over-year in enterprise environments.`,
    `Understanding requires familiarity with prerequisite concepts often overlooked.`,
  ]).slice(0, rng.range(3, 5));

  const facts = rng.shuffle([
    `The term was first formally defined in academic literature in the early 2000s.`,
    `Over 60% of practitioners report self-learning as their primary education path.`,
    `The global market exceeded $50B in 2023.`,
    `Research shows a 35% processing time reduction versus traditional approaches.`,
    `More than 500 peer-reviewed papers are published annually.`,
    `Leading countries: US, China, UK, Germany, and Canada.`,
  ]).slice(0, rng.range(3, 5));

  const concepts = rng.shuffle([
    `Core framework of ${topic}`,
    `Historical evolution of ${topic}`,
    `Key stakeholder ecosystems`,
    `Measurement and evaluation methods`,
    `Regulatory landscape`,
    `Open research problems`,
  ]).slice(0, 4);

  const timelineEvents = [
    `1990s — Early theoretical foundations established`,
    `2005 — First widely-adopted commercial application`,
    `2012 — Landmark study demonstrates effectiveness at scale`,
    `2017 — Open-source tooling democratizes access`,
    `2021 — Regulatory frameworks begin to emerge globally`,
    `2024 — State-of-the-art systems achieve benchmark performance`,
  ].slice(0, rng.range(3, 6));

  const entities = rng.shuffle(["Stanford AI Lab", "MIT Media Lab", "Google DeepMind", "OpenAI", "European Research Council", "IEEE Working Group", "Dr. Yann LeCun", "Dr. Fei-Fei Li"]).slice(0, 5);

  const statistics = rng.shuffle([
    `78% of practitioners consider ${topic} critical to their strategy`,
    `Average implementation cost: $250K–$2M for enterprise`,
    `Projected CAGR: 28.4% from 2024–2030`,
    `Time-to-competency: 6–18 months`,
    `Error rate reduction: median 41% across case studies`,
  ]).slice(0, rng.range(3, 4));

  const examples = rng.shuffle([
    `A company reduced operational costs by 30% using ${topic}`,
    `A hospital cut diagnostic errors by 22% in a 2-year pilot`,
    `A fintech startup achieved 10x growth by embedding ${topic}`,
    `An open-source project gained 40K stars within 6 months`,
  ]).slice(0, 3);

  const analogies = [
    `${topic.charAt(0).toUpperCase() + topic.slice(1)} is like building a skyscraper — foundations must be solid before adding floors`,
    `Think of ${topic} as a GPS: it shows the best route, but you still drive`,
    `Learning ${topic} is like learning a language — immersion beats memorizing rules`,
  ].slice(0, 2);

  const misconceptions = [
    `Misconception: ${topic} requires a PhD. Reality: fundamentals are accessible to motivated learners`,
    `Misconception: ${topic} always outperforms traditional methods. Reality: depends on data quality`,
    `Misconception: implementing ${topic} is a one-time project. Reality: continuous iteration required`,
  ].slice(0, 2);

  const faqs = [
    { q: `What is ${topic}?`, a: `${topic.charAt(0).toUpperCase() + topic.slice(1)} refers to techniques that address specific problem domains through a combination of theory and application.` },
    { q: `How long to learn ${topic}?`, a: `Foundational competency typically requires 3–6 months. Expert mastery: 2–5 years.` },
    { q: `Is ${topic} suitable for small businesses?`, a: `Yes — modern tooling has made it accessible, though ROI timelines vary.` },
    { q: `What are the main challenges with ${topic}?`, a: `Data quality, talent scarcity, legacy system integration, and stakeholder expectations.` },
  ].slice(0, rng.range(3, 4));

  const domainSample = Array.from({ length: 5 }, () => rng.choice(DOMAINS));
  const references: MockRef[] = domainSample.map((dom, i) => {
    const year = rng.range(2018, 2024);
    const title = `${i % 2 === 0 ? "Understanding" : "Advances in"} ${topic.charAt(0).toUpperCase() + topic.slice(1)}${i === 0 ? ": A Review" : ` Vol.${i}`}`;
    const author = rng.choice([null, "Smith, J.", "Zhang, L.", "Müller, K.", "Patel, R."]);
    const url = `https://${dom.d}/${topic.replace(/\s+/g, "-").toLowerCase()}/${year}`;
    return {
      id: randomUUID(),
      title,
      url,
      sourceType: dom.type,
      author,
      publishedAt: `${year}-${String(rng.range(1,12)).padStart(2,"0")}-01`,
      snippet: `Authoritative coverage of ${topic} with emphasis on ${rng.choice(["theoretical foundations","practical applications","empirical results","case studies"])}.`,
      credibilityScore: +(dom.cred + rng.float(-0.05, 0.05)).toFixed(3),
      citationFormat: buildAPA(title, author, url, year),
      provider,
    };
  });

  const baseTerms = [...new Set([
    ...topic.toLowerCase().split(/\s+/),
    "machine learning", "data", "automation", "optimization", "tutorial",
    "beginner guide", "best practices", "2024", `${topic.split(" ")[0]} tools`,
  ])].slice(0, 10);
  const keywords: MockKw[] = baseTerms.map((term, j) => ({
    term,
    relevance: j < 3 ? rng.float(0.7, 1.0) : rng.float(0.3, 0.7),
    searchVolume: rng.range(1000, 500000),
    difficulty: rng.choice(["low", "medium", "high"]),
    semanticTags: [topic.split(" ")[0], "youtube", rng.choice(["beginner", "advanced", "tutorial"])],
  }));

  const confidence = provider === "openai" ? rng.float(0.78, 0.92)
    : provider === "claude" ? rng.float(0.76, 0.90)
    : provider === "gemini" ? rng.float(0.74, 0.88)
    : provider === "wikipedia" ? rng.float(0.72, 0.84)
    : rng.float(0.60, 0.82);

  return { summary, keyPoints, facts, concepts, timelineEvents, entities, statistics, examples, analogies, misconceptions, faqs, references, keywords, confidence };
}

// ── Research processor (async, runs after API response) ───────────────────────

async function processResearch(id: string, request: z.infer<typeof ResearchInputSchema>): Promise<void> {
  const { topic, style, tone, providers } = request;

  const addLog = async (level: string, msg: string) => {
    const current = await db.select({ logs: researchResults.logs }).from(researchResults).where(eq(researchResults.id, id));
    const logs: string[] = (current[0]?.logs as string[]) || [];
    logs.push(`${ts()} ${level.padEnd(5)} ${msg}`);
    await db.update(researchResults).set({ logs, updatedAt: new Date() }).where(eq(researchResults.id, id));
  };

  try {
    // Update status to running
    await db.update(researchResults)
      .set({ status: "running", updatedAt: new Date() })
      .where(eq(researchResults.id, id));

    await addLog("INFO", `Starting research for topic: '${topic}'`);
    await addLog("INFO", `Requested providers: ${providers.join(", ")}`);
    await addLog("INFO", "Phase 1/4 — Fetching from research providers");

    // Simulate parallel provider fetching
    const t0 = Date.now();
    await new Promise(r => setTimeout(r, 300));
    const providerResults = providers.map(p => generateMockProviderResult(p, topic, style, tone));
    const elapsed = Date.now() - t0;

    await addLog("INFO", `Providers completed in ${elapsed}ms — ${providers.length} OK, 0 failed`);
    await addLog("INFO", "Phase 2/4 — Merging and deduplicating provider outputs");

    // Merge results
    const seenFacts: string[] = [];
    const seenConcepts: string[] = [];
    const seenTimeline: string[] = [];
    const seenEntities: string[] = [];
    const seenStats: string[] = [];
    const seenExamples: string[] = [];
    const seenAnalogies: string[] = [];
    const seenMisconceptions: string[] = [];
    const seenFaqs: string[] = [];

    let bestSummary = "";
    for (const r of providerResults) {
      if (r.summary.length > bestSummary.length) bestSummary = r.summary;
      for (const item of r.facts) if (!isNearDuplicate(item, seenFacts)) seenFacts.push(item);
      for (const item of r.concepts) if (!isNearDuplicate(item, seenConcepts)) seenConcepts.push(item);
      for (const item of r.timelineEvents) if (!isNearDuplicate(item, seenTimeline)) seenTimeline.push(item);
      for (const item of r.entities) if (!isNearDuplicate(item, seenEntities)) seenEntities.push(item);
      for (const item of r.statistics) if (!isNearDuplicate(item, seenStats)) seenStats.push(item);
      for (const item of r.examples) if (!isNearDuplicate(item, seenExamples)) seenExamples.push(item);
      for (const item of r.analogies) if (!isNearDuplicate(item, seenAnalogies)) seenAnalogies.push(item);
      for (const item of r.misconceptions) if (!isNearDuplicate(item, seenMisconceptions)) seenMisconceptions.push(item);
      for (const faq of r.faqs) if (!isNearDuplicate(faq.q, seenFaqs)) { seenFaqs.push(faq.q); }
    }

    const avgConf = providerResults.reduce((s, r) => s + r.confidence, 0) / providerResults.length;

    const sections = [
      { sectionType: "summary", title: "Overview", content: bestSummary, confidence: +avgConf.toFixed(3), items: [], sourceIds: [] },
      ...(seenConcepts.length > 0 ? [{ sectionType: "concept", title: "Major Concepts", content: `${seenConcepts.length} concepts identified.`, confidence: +(avgConf + 0.05).toFixed(3), items: seenConcepts, sourceIds: [] }] : []),
      ...(seenFacts.length > 0 ? [{ sectionType: "fact", title: "Key Facts", content: `${seenFacts.length} facts compiled.`, confidence: +avgConf.toFixed(3), items: seenFacts, sourceIds: [] }] : []),
      ...(seenTimeline.length > 0 ? [{ sectionType: "timeline", title: "Timeline of Events", content: `${seenTimeline.length} events.`, confidence: +(avgConf + 0.02).toFixed(3), items: seenTimeline, sourceIds: [] }] : []),
      ...(seenEntities.length > 0 ? [{ sectionType: "entity", title: "Named Entities", content: `${seenEntities.length} entities found.`, confidence: +avgConf.toFixed(3), items: seenEntities, sourceIds: [] }] : []),
      ...(seenStats.length > 0 ? [{ sectionType: "statistic", title: "Statistics & Data", content: `${seenStats.length} statistics found.`, confidence: +(avgConf + 0.03).toFixed(3), items: seenStats, sourceIds: [] }] : []),
      ...(seenExamples.length > 0 ? [{ sectionType: "example", title: "Real-World Examples", content: `${seenExamples.length} examples.`, confidence: +(avgConf + 0.04).toFixed(3), items: seenExamples, sourceIds: [] }] : []),
      ...(seenAnalogies.length > 0 ? [{ sectionType: "analogy", title: "Analogies & Explanations", content: `${seenAnalogies.length} analogies.`, confidence: +(avgConf + 0.06).toFixed(3), items: seenAnalogies, sourceIds: [] }] : []),
      ...(seenMisconceptions.length > 0 ? [{ sectionType: "misconception", title: "Common Misconceptions", content: `${seenMisconceptions.length} misconceptions.`, confidence: +(avgConf + 0.05).toFixed(3), items: seenMisconceptions, sourceIds: [] }] : []),
      ...(seenFaqs.length > 0 ? [{
        sectionType: "faq", title: "Frequently Asked Questions", content: `${seenFaqs.length} FAQs.`, confidence: +avgConf.toFixed(3),
        items: providerResults.flatMap(r => r.faqs).filter((f,i,a) => a.findIndex(x => x.q === f.q) === i).map(f => `${f.q}\n${f.a}`),
        sourceIds: [],
      }] : []),
    ];

    await addLog("INFO", `Merged ${sections.length} sections from ${providers.length} providers`);

    // ── Phase 3: references & keywords ─────────────────────────────────────
    await addLog("INFO", "Phase 3/4 — Ranking references and deduplicating keywords");
    await new Promise(r => setTimeout(r, 100));

    const seenUrls = new Set<string>();
    const allRefs = providerResults.flatMap(r => r.references)
      .filter(r => { if (seenUrls.has(r.url)) return false; seenUrls.add(r.url); return true; })
      .sort((a, b) => b.credibilityScore - a.credibilityScore)
      .slice(0, 15);

    const kwMap = new Map<string, MockKw>();
    for (const kw of providerResults.flatMap(r => r.keywords)) {
      const key = kw.term.toLowerCase().trim();
      const ex = kwMap.get(key);
      if (!ex || kw.relevance > ex.relevance) {
        kwMap.set(key, { ...kw });
      } else {
        ex.semanticTags = [...new Set([...ex.semanticTags, ...kw.semanticTags])].slice(0, 5);
      }
    }
    const keywords = [...kwMap.values()].sort((a, b) => b.relevance - a.relevance).slice(0, 20);

    await addLog("INFO", `References: ${allRefs.length} unique  |  Keywords: ${keywords.length} unique`);

    // ── Phase 4: scoring ──────────────────────────────────────────────────
    await addLog("INFO", "Phase 4/4 — Calculating confidence score and difficulty");
    await new Promise(r => setTimeout(r, 50));

    const refQuality = allRefs.length > 0 ? allRefs.reduce((s, r) => s + r.credibilityScore, 0) / allRefs.length : 0.5;
    const richness = Math.min(1.0, sections.length / 9);
    const confidence = +(avgConf * 0.40 + 1.0 * 0.20 + refQuality * 0.20 + richness * 0.20).toFixed(3);

    const hardKws = new Set(["advanced", "research", "technical", "architecture", "algorithm", "theory", "mathematical", "optimization", "distributed", "quantum"]);
    const beginnerKws = new Set(["beginner", "intro", "basics", "getting started", "tutorial", "simple", "easy", "learn", "guide", "how to", "for beginners"]);
    const terms = new Set(keywords.map(k => k.term.toLowerCase()));
    const hardHits = [...terms].filter(t => hardKws.has(t)).length;
    const beginnerHits = [...terms].filter(t => beginnerKws.has(t)).length;
    const diffScore = hardHits * 2 - beginnerHits + Math.floor(sections.length / 3);
    const difficulty = diffScore >= 4 ? "advanced" : diffScore >= 1 ? "intermediate" : "beginner";

    await addLog("INFO", `Confidence score: ${(confidence * 100).toFixed(1)}%  |  Estimated difficulty: ${difficulty}`);
    await addLog("INFO", "Research complete — writing to database");

    const current = await db.select({ logs: researchResults.logs }).from(researchResults).where(eq(researchResults.id, id));
    const finalLogs = current[0]?.logs as string[] || [];

    await db.update(researchResults).set({
      status: "completed",
      summary: bestSummary,
      confidenceScore: confidence,
      estimatedDifficulty: difficulty,
      sections: sections as any,
      references: allRefs as any,
      keywords: keywords as any,
      usedProviders: providers,
      logs: finalLogs,
      completedAt: new Date(),
      updatedAt: new Date(),
    }).where(eq(researchResults.id, id));

  } catch (err: any) {
    const errMsg = err?.message || String(err);
    const current = await db.select({ logs: researchResults.logs }).from(researchResults).where(eq(researchResults.id, id));
    const logs = (current[0]?.logs as string[]) || [];
    logs.push(`${ts()} ERROR Research failed: ${errMsg}`);
    await db.update(researchResults).set({
      status: "failed",
      errorMessage: errMsg,
      logs,
      updatedAt: new Date(),
    }).where(eq(researchResults.id, id));
  }
}

// ── Routes ────────────────────────────────────────────────────────────────────

function toApi(r: typeof researchResults.$inferSelect): object {
  return {
    id: r.id,
    topic: r.topic,
    targetAudience: r.targetAudience,
    videoLengthMinutes: r.videoLengthMinutes,
    language: r.language,
    style: r.style,
    tone: r.tone,
    status: r.status,
    jobId: r.jobId,
    summary: r.summary,
    confidenceScore: r.confidenceScore,
    estimatedDifficulty: r.estimatedDifficulty,
    sections: r.sections || [],
    references: r.references || [],
    keywords: r.keywords || [],
    providers: r.providers || [],
    usedProviders: r.usedProviders || [],
    logs: r.logs || [],
    errorMessage: r.errorMessage,
    createdAt: r.createdAt,
    updatedAt: r.updatedAt,
    completedAt: r.completedAt,
  };
}

// GET /research
router.get("/", async (req: Request, res: Response) => {
  const status = req.query.status as string | undefined;
  const limit = Math.min(Number(req.query.limit) || 50, 200);
  const offset = Number(req.query.offset) || 0;

  let rows = await db.select().from(researchResults).orderBy(desc(researchResults.createdAt)).limit(limit + 1).offset(offset);
  if (status) rows = rows.filter(r => r.status === status);
  res.json({ items: rows.slice(0, limit).map(toApi), total: rows.length });
});

// POST /research
router.post("/", async (req: Request, res: Response) => {
  const parse = ResearchInputSchema.safeParse(req.body);
  if (!parse.success) {
    res.status(400).json({ error: parse.error.flatten() });
    return;
  }
  const input = parse.data;
  const id = randomUUID();
  const topicNormalized = normalizeTopic(input.topic);

  // Cache check — look for completed research for same topic in last 7 days
  const cutoff = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const [cached] = await db.select().from(researchResults)
    .where(and(eq(researchResults.topicNormalized, topicNormalized), eq(researchResults.status, "completed")))
    .orderBy(desc(researchResults.completedAt))
    .limit(1);

  if (cached && cached.completedAt && cached.completedAt > cutoff) {
    // Return cached result
    res.status(202).json(toApi({ ...cached, status: "cached" }));
    return;
  }

  await db.insert(researchResults).values({
    id,
    topic: input.topic,
    topicNormalized,
    targetAudience: input.targetAudience,
    videoLengthMinutes: input.videoLengthMinutes,
    language: input.language,
    style: input.style,
    tone: input.tone,
    status: "pending",
    jobId: randomUUID(),
    providers: input.providers,
    usedProviders: [],
    sections: [],
    references: [],
    keywords: [],
    logs: [`${ts()} INFO  Research job created — providers: ${input.providers.join(", ")}`],
    createdAt: new Date(),
    updatedAt: new Date(),
  });

  const [created] = await db.select().from(researchResults).where(eq(researchResults.id, id));
  res.status(202).json(toApi(created));

  // Fire-and-forget async processing
  setImmediate(() => { processResearch(id, input).catch(console.error); });
});

// GET /research/:id
router.get("/:id", async (req: Request, res: Response) => {
  const [row] = await db.select().from(researchResults).where(eq(researchResults.id, req.params.id));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  res.json(toApi(row));
});

// DELETE /research/:id
router.delete("/:id", async (req: Request, res: Response) => {
  const [row] = await db.select().from(researchResults).where(eq(researchResults.id, req.params.id));
  if (!row) { res.status(404).json({ error: "Not found" }); return; }
  await db.delete(researchResults).where(eq(researchResults.id, req.params.id));
  res.status(204).send();
});

export default router;
