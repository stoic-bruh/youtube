import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useListVoices,
  useStartVoice,
  useGetVoice,
  useDeleteVoice,
  useGetVoiceProviderStats,
  useListScripts,
  getListVoicesQueryKey,
  getGetVoiceQueryKey,
  getGetVoiceProviderStatsQueryKey,
  type VoiceResult,
  type VoiceSectionAudio,
  type VoiceProviderStats,
  type ScriptResult,
} from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";
import {
  Mic,
  Play,
  Pause,
  Trash2,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  Volume2,
  ListMusic,
  BarChart3,
  ChevronRight,
  Waves,
  Gauge,
  Zap,
  ListTree,
  Info,
  FileAudio,
} from "lucide-react";

// ── Helpers ────────────────────────────────────────────────────────────────────

function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "--";
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function formatCost(usd: number | null | undefined): string {
  if (usd == null) return "--";
  return `$${usd.toFixed(4)}`;
}

const VOICE_OPTIONS = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"];
const PROVIDER_LABELS: Record<string, string> = {
  "openai-tts": "OpenAI TTS",
  elevenlabs: "ElevenLabs",
};

function statusBadge(status: string) {
  const map: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; label: string; icon: React.ReactNode }> = {
    pending: { variant: "secondary", label: "Pending", icon: <Clock className="h-3 w-3" /> },
    running: { variant: "default", label: "Generating", icon: <Loader2 className="h-3 w-3 animate-spin" /> },
    completed: { variant: "outline", label: "Completed", icon: <CheckCircle2 className="h-3 w-3 text-emerald-500" /> },
    cached: { variant: "outline", label: "Cached", icon: <CheckCircle2 className="h-3 w-3 text-blue-400" /> },
    failed: { variant: "destructive", label: "Failed", icon: <AlertTriangle className="h-3 w-3" /> },
  };
  const cfg = map[status] ?? { variant: "secondary" as const, label: status, icon: null };
  return (
    <Badge variant={cfg.variant} className="gap-1 text-xs">
      {cfg.icon}
      {cfg.label}
    </Badge>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function EmptyState({ message, icon: Icon = Mic }: { message: string; icon?: React.ComponentType<{ className?: string }> }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
      <Icon className="h-10 w-10 text-muted-foreground/40" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

/** Deterministic pseudo-waveform bars derived from section text — no real audio decoding needed for preview. */
function pseudoWaveform(seed: string, bars: number): number[] {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  const out: number[] = [];
  for (let i = 0; i < bars; i++) {
    h = (h * 1103515245 + 12345) >>> 0;
    out.push(0.15 + ((h >>> 8) % 100) / 100 * 0.85);
  }
  return out;
}

/** Waveform Viewer — visualizes narration amplitude across a section with a playhead. */
function WaveformViewer({
  section,
  playheadMs,
}: {
  section: VoiceSectionAudio;
  playheadMs: number;
}) {
  const bars = useMemo(() => pseudoWaveform(section.localPath + section.sectionIndex, 96), [section]);
  const progress = section.durationMs > 0 ? Math.min(1, Math.max(0, playheadMs / section.durationMs)) : 0;
  return (
    <div className="relative h-16 flex items-center gap-[2px] px-2 bg-muted/20 rounded-md border border-border overflow-hidden">
      {bars.map((h, i) => {
        const played = i / bars.length < progress;
        return (
          <div
            key={i}
            className={cn("flex-1 rounded-full transition-colors", played ? "bg-primary" : "bg-muted-foreground/30")}
            style={{ height: `${h * 100}%` }}
          />
        );
      })}
      <div
        className="absolute top-0 bottom-0 w-px bg-primary/80"
        style={{ left: `${progress * 100}%` }}
      />
    </div>
  );
}

/** Audio Player — simulated transport controls (no real decoded audio yet; providers are placeholders). */
function AudioPlayer({ sections }: { sections: VoiceSectionAudio[] }) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [playheadMs, setPlayheadMs] = useState(0);
  const active = sections[activeIndex] ?? null;

  if (!sections.length) return <EmptyState message="No narration audio available" icon={FileAudio} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button
          size="icon"
          variant="secondary"
          className="h-10 w-10 rounded-full flex-shrink-0"
          onClick={() => setPlaying((p) => !p)}
        >
          {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
        </Button>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{active?.sectionTitle ?? "—"}</p>
          <p className="text-xs text-muted-foreground font-mono">
            {formatMs(playheadMs)} / {formatMs(active?.durationMs)}
          </p>
        </div>
        <Volume2 className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        <Slider defaultValue={[100]} max={100} step={1} className="w-20" />
      </div>

      {active && (
        <>
          <WaveformViewer section={active} playheadMs={playheadMs} />
          <Slider
            value={[playheadMs]}
            max={Math.max(1, active.durationMs)}
            step={100}
            onValueChange={(v) => setPlayheadMs(v[0] ?? 0)}
          />
        </>
      )}

      <div className="flex gap-1.5 overflow-x-auto pb-1">
        {sections.map((s, i) => (
          <button
            key={s.sectionIndex}
            onClick={() => { setActiveIndex(i); setPlayheadMs(0); setPlaying(false); }}
            className={cn(
              "flex-shrink-0 px-2.5 py-1 rounded text-[11px] font-mono border transition-colors",
              i === activeIndex ? "bg-primary/15 border-primary/40 text-primary" : "border-border text-muted-foreground hover:bg-accent/40",
            )}
          >
            S{s.sectionIndex + 1} · {formatMs(s.durationMs)}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Segment Viewer — per-section transcript with timing + word count. */
function SegmentViewer({ sections }: { sections: VoiceSectionAudio[] }) {
  if (!sections.length) return <EmptyState message="No sections generated yet" icon={ListTree} />;
  return (
    <div className="space-y-2">
      {sections.map((s) => (
        <div key={s.sectionIndex} className="border border-border rounded-md p-3 space-y-1.5">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-[10px] w-8 justify-center flex-shrink-0">
              S{s.sectionIndex + 1}
            </Badge>
            <span className="text-sm font-medium flex-1 truncate">{s.sectionTitle}</span>
            <span className="text-xs font-mono text-muted-foreground">{formatMs(s.durationMs)}</span>
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2">{s.text}</p>
          <div className="flex items-center gap-3 text-[10px] text-muted-foreground font-mono">
            <span>{s.wordCount} words</span>
            <span>{formatMs(s.startMs)}–{formatMs(s.endMs)}</span>
            <span>{s.sampleRate} Hz</span>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Timeline Synchronization — how narration sections line up on a shared time axis (feeds the Media Timeline Engine). */
function TimelineSync({ sections, totalDurationMs }: { sections: VoiceSectionAudio[]; totalDurationMs: number }) {
  if (!sections.length || !totalDurationMs) return <EmptyState message="No timing data to synchronize" icon={Waves} />;
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Narration timing used by the Media Timeline Engine's audio track — each block maps 1:1 to a script section.
      </p>
      <div className="relative h-10 bg-muted/30 rounded-md overflow-hidden border border-border">
        {sections.map((s) => {
          const left = (s.startMs / totalDurationMs) * 100;
          const width = (s.durationMs / totalDurationMs) * 100;
          return (
            <div
              key={s.sectionIndex}
              className="absolute top-1 bottom-1 rounded flex items-center justify-center text-[10px] font-mono overflow-hidden border bg-purple-500/25 border-purple-500/40 text-purple-300"
              style={{ left: `${left}%`, width: `calc(${width}% - 2px)` }}
              title={`${s.sectionTitle} (${formatMs(s.durationMs)})`}
            >
              {width > 5 && <span className="truncate px-1">S{s.sectionIndex + 1}</span>}
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
        <span>0:00</span>
        <span>{formatMs(totalDurationMs)}</span>
      </div>
    </div>
  );
}

/** Voice Statistics — aggregate metrics for a single voice result. */
function VoiceStatistics({ voice }: { voice: VoiceResult }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      {[
        ["Total Duration", formatMs(voice.totalDurationMs)],
        ["Word Count", String(voice.wordCount ?? "--")],
        ["Sections", String(voice.sections.length)],
        ["Sample Rate", voice.sampleRate ? `${voice.sampleRate} Hz` : "--"],
        ["Audio Format", (voice.audioFormat ?? "--").toUpperCase()],
        ["Normalized", voice.normalized ? `Yes (${voice.targetLoudnessLufs} LUFS)` : "No"],
        ["Cost", formatCost(voice.costUsd)],
        ["Used Provider", voice.usedProvider ? (PROVIDER_LABELS[voice.usedProvider] ?? voice.usedProvider) : "--"],
      ].map(([label, val]) => (
        <div key={label} className="border border-border rounded-md p-2.5">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
          <p className="text-sm font-mono mt-0.5">{val}</p>
        </div>
      ))}
    </div>
  );
}

/** Provider Statistics — success rate / cost across all voice providers, with fallback ordering context. */
function ProviderStatistics({ stats, loading }: { stats: VoiceProviderStats[]; loading: boolean }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!stats.length) return <EmptyState message="No provider activity yet" icon={Gauge} />;
  return (
    <div className="space-y-3">
      {stats.map((p) => {
        const successRate = p.totalRequests > 0 ? (p.successfulRequests / p.totalRequests) * 100 : 0;
        return (
          <Card key={p.providerName}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Mic className="h-4 w-4" />
                  {PROVIDER_LABELS[p.providerName] ?? p.providerName}
                </span>
                <Badge variant={p.isEnabled ? "outline" : "secondary"} className="text-[10px]">
                  {p.isEnabled ? "enabled" : "disabled"}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-muted-foreground">Success rate</span>
                <span className={successRate >= 80 ? "text-emerald-400" : "text-amber-400"}>
                  {successRate.toFixed(0)}% ({p.successfulRequests}/{p.totalRequests})
                </span>
              </div>
              <Progress value={successRate} className="h-1.5" />
              <div className="grid grid-cols-2 gap-2 pt-1 text-xs">
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-muted-foreground">Total cost</span>
                  <span className="font-mono">{formatCost(p.totalCostUsd)}</span>
                </div>
                <div className="flex justify-between border-b border-border pb-1">
                  <span className="text-muted-foreground">Avg cost</span>
                  <span className="font-mono">{formatCost(p.avgCostUsd)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Audio generated</span>
                  <span className="font-mono">{formatMs(p.totalDurationMsGenerated)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Failed</span>
                  <span className="font-mono">{p.failedRequests}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

/** Audio Metadata — raw technical fields for the generated narration. */
function AudioMetadata({ voice }: { voice: VoiceResult }) {
  return (
    <div className="space-y-1.5 text-sm">
      {[
        ["Voice ID", voice.voiceId],
        ["Speed", `${voice.speed}×`],
        ["Language", (voice.language ?? "en").toUpperCase()],
        ["Target Loudness", `${voice.targetLoudnessLufs} LUFS`],
        ["Providers (fallback order)", voice.providers.map((p) => PROVIDER_LABELS[p] ?? p).join(" → ")],
        ["Job ID", voice.jobId ?? "--"],
        ["Created", new Date(voice.createdAt).toLocaleString()],
        ["Completed", voice.completedAt ? new Date(voice.completedAt).toLocaleString() : "--"],
      ].map(([label, val]) => (
        <div key={label} className="flex justify-between border-b border-border pb-1.5 last:border-0 gap-4">
          <span className="text-muted-foreground flex-shrink-0">{label}</span>
          <span className="font-mono text-xs text-right break-all">{val}</span>
        </div>
      ))}
    </div>
  );
}

/** Generation Queue / Logs panel */
function GenerationLogs({ logs }: { logs: string[] }) {
  return (
    <ScrollArea className="h-64 w-full">
      <div className="font-mono text-xs space-y-0.5 p-1">
        {logs.length === 0
          ? <span className="text-muted-foreground">No logs yet.</span>
          : logs.map((line, i) => (
            <div
              key={i}
              className={cn(
                "leading-relaxed",
                line.includes("ERROR") ? "text-destructive" :
                  line.includes("WARN") ? "text-amber-400" :
                    "text-muted-foreground",
              )}
            >
              {line}
            </div>
          ))
        }
      </div>
    </ScrollArea>
  );
}

/** Detail view — the "Voice Preview" panel for a single voice result. */
function VoiceDetail({ voice }: { voice: VoiceResult }) {
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold text-sm">Narration — {voice.voiceId}</h3>
          <p className="text-xs text-muted-foreground font-mono mt-0.5">{voice.id}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {statusBadge(voice.status)}
          {voice.totalDurationMs != null && (
            <Badge variant="outline" className="text-xs gap-1">
              <Clock className="h-3 w-3" />
              {formatMs(voice.totalDurationMs)}
            </Badge>
          )}
        </div>
      </div>

      {voice.errorMessage && (
        <div className="flex items-start gap-2 p-3 rounded bg-destructive/10 border border-destructive/30 text-destructive text-sm">
          <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          {voice.errorMessage}
        </div>
      )}

      <Tabs defaultValue="preview">
        <TabsList className="h-8 text-xs flex-wrap h-auto">
          <TabsTrigger value="preview">Preview</TabsTrigger>
          <TabsTrigger value="segments">Segments</TabsTrigger>
          <TabsTrigger value="sync">Timeline Sync</TabsTrigger>
          <TabsTrigger value="stats">Statistics</TabsTrigger>
          <TabsTrigger value="metadata">Metadata</TabsTrigger>
          <TabsTrigger value="logs">Logs</TabsTrigger>
        </TabsList>

        <TabsContent value="preview" className="mt-4">
          <AudioPlayer sections={voice.sections} />
        </TabsContent>

        <TabsContent value="segments" className="mt-4">
          <ScrollArea className="h-[420px]">
            <SegmentViewer sections={voice.sections} />
          </ScrollArea>
        </TabsContent>

        <TabsContent value="sync" className="mt-4">
          <TimelineSync sections={voice.sections} totalDurationMs={voice.totalDurationMs ?? 0} />
        </TabsContent>

        <TabsContent value="stats" className="mt-4">
          <VoiceStatistics voice={voice} />
        </TabsContent>

        <TabsContent value="metadata" className="mt-4">
          <AudioMetadata voice={voice} />
        </TabsContent>

        <TabsContent value="logs" className="mt-4">
          <GenerationLogs logs={voice.logs} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function VoicesPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [scriptFilter, setScriptFilter] = useState<string>("all");
  const [buildScriptId, setBuildScriptId] = useState<string>("");
  const [voiceId, setVoiceId] = useState<string>("alloy");
  const [speed, setSpeed] = useState<number>(1.0);
  const [providerOrder, setProviderOrder] = useState<string[]>(["openai-tts", "elevenlabs"]);
  const [statsTab, setStatsTab] = useState<"library" | "providers">("library");

  const listParams = scriptFilter && scriptFilter !== "all" ? { scriptId: scriptFilter, limit: 100 } : { limit: 100 };

  // Voice Library — list of all generated narrations. Polls while any job is
  // pending/running so async status transitions (pending -> running ->
  // completed/failed) surface without a manual refresh.
  const { data: voicesData, isLoading: listLoading } = useListVoices(listParams, {
    query: {
      refetchInterval: (query: { state: { data?: { items?: VoiceResult[] } } }) => {
        const items = query.state.data?.items ?? [];
        const hasActive = items.some((v) => v.status === "pending" || v.status === "running");
        return hasActive ? 1500 : false;
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any,
  });

  // Voice Browser filter source — completed scripts available for narration
  const { data: scriptsData } = useListScripts({ limit: 100 });

  // Provider Statistics
  const { data: providerStatsData, isLoading: providerStatsLoading } = useGetVoiceProviderStats();

  const selectedIsActive = useMemo(() => {
    const items = (voicesData?.items ?? []) as VoiceResult[];
    const v = items.find((x) => x.id === selectedId);
    return v ? v.status === "pending" || v.status === "running" : false;
  }, [voicesData, selectedId]);

  const { data: selectedVoice } = useGetVoice(selectedId ?? "", {
    query: {
      enabled: !!selectedId,
      refetchInterval: selectedIsActive ? 1500 : false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any,
  });

  const startMutation = useStartVoice({
    mutation: {
      onSuccess: (data) => {
        qc.invalidateQueries({ queryKey: getListVoicesQueryKey(listParams) });
        qc.invalidateQueries({ queryKey: getGetVoiceProviderStatsQueryKey() });
        setSelectedId((data as VoiceResult).id);
      },
    },
  });

  const deleteMutation = useDeleteVoice({
    mutation: {
      onSuccess: (_data, variables) => {
        qc.invalidateQueries({ queryKey: getListVoicesQueryKey(listParams) });
        qc.invalidateQueries({ queryKey: getGetVoiceProviderStatsQueryKey() });
        const deletedId = (variables as { id: string }).id;
        qc.removeQueries({ queryKey: getGetVoiceQueryKey(deletedId) });
        if (selectedId === deletedId) setSelectedId(null);
      },
    },
  });

  const voices: VoiceResult[] = (voicesData?.items ?? []) as VoiceResult[];
  const scripts: ScriptResult[] = (scriptsData?.items ?? []) as ScriptResult[];
  const providerStats: VoiceProviderStats[] = (providerStatsData?.items ?? []) as VoiceProviderStats[];
  const selected = selectedVoice ?? voices.find((v) => v.id === selectedId) ?? null;

  // Generation Queue — jobs currently pending/running, surfaced at the top of the library
  const activeJobs = voices.filter((v) => v.status === "pending" || v.status === "running");

  function toggleProvider(name: string) {
    setProviderOrder((prev) => (prev.includes(name) ? prev.filter((p) => p !== name) : [...prev, name]));
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-border px-6 py-4 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold font-mono flex items-center gap-2">
            <Mic className="h-5 w-5 text-primary" />
            Voice Studio
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Generate narration audio from scripts — providers tried in fallback order, first success wins
          </p>
        </div>
        <div className="flex items-center gap-2">
          {activeJobs.length > 0 && (
            <Badge variant="secondary" className="gap-1.5 text-xs">
              <Loader2 className="h-3 w-3 animate-spin" />
              {activeJobs.length} in queue
            </Badge>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              qc.invalidateQueries({ queryKey: getListVoicesQueryKey(listParams) });
              qc.invalidateQueries({ queryKey: getGetVoiceProviderStatsQueryKey() });
              if (selectedId) qc.invalidateQueries({ queryKey: getGetVoiceQueryKey(selectedId) });
            }}
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Left panel — Provider Selector + build form + Voice Browser/Library */}
        <div className="w-80 border-r border-border flex flex-col flex-shrink-0">
          <div className="p-4 border-b border-border space-y-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Generate Narration
            </p>
            <Select value={buildScriptId} onValueChange={setBuildScriptId}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder="Select script…" />
              </SelectTrigger>
              <SelectContent>
                {scripts
                  .filter((s) => s.status === "completed")
                  .map((s) => (
                    <SelectItem key={s.id} value={s.id} className="text-xs">
                      {(s.title || s.topic).slice(0, 50)}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>

            <div className="flex items-center gap-2">
              <Select value={voiceId} onValueChange={setVoiceId}>
                <SelectTrigger className="h-8 text-xs flex-1">
                  <SelectValue placeholder="Voice" />
                </SelectTrigger>
                <SelectContent>
                  {VOICE_OPTIONS.map((v) => (
                    <SelectItem key={v} value={v} className="text-xs capitalize">{v}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={String(speed)} onValueChange={(v) => setSpeed(Number(v))}>
                <SelectTrigger className="h-8 text-xs w-20">
                  <SelectValue placeholder="Speed" />
                </SelectTrigger>
                <SelectContent>
                  {[0.75, 1.0, 1.25, 1.5].map((s) => (
                    <SelectItem key={s} value={String(s)} className="text-xs">{s}×</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Provider Selector — click to toggle inclusion, order = fallback priority */}
            <div>
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">
                Providers (fallback order)
              </p>
              <div className="flex gap-1.5">
                {(["openai-tts", "elevenlabs"] as const).map((name) => (
                  <button
                    key={name}
                    onClick={() => toggleProvider(name)}
                    className={cn(
                      "flex-1 px-2 py-1.5 rounded text-[11px] font-medium border transition-colors",
                      providerOrder.includes(name)
                        ? "bg-primary/15 border-primary/40 text-primary"
                        : "border-border text-muted-foreground hover:bg-accent/40",
                    )}
                  >
                    {providerOrder.includes(name) && `${providerOrder.indexOf(name) + 1}. `}
                    {PROVIDER_LABELS[name]}
                  </button>
                ))}
              </div>
            </div>

            <Button
              size="sm"
              className="w-full text-xs"
              disabled={!buildScriptId || !providerOrder.length || startMutation.isPending}
              onClick={() =>
                startMutation.mutate({
                  data: { scriptId: buildScriptId, voiceId, speed, providers: providerOrder as ("openai-tts" | "elevenlabs")[] },
                })
              }
            >
              {startMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <Zap className="h-3.5 w-3.5 mr-1.5" />
              )}
              Generate Narration
            </Button>
          </div>

          <Tabs value={statsTab} onValueChange={(v) => setStatsTab(v as "library" | "providers")} className="flex-1 flex flex-col min-h-0">
            <TabsList className="h-8 text-xs mx-4 mt-2">
              <TabsTrigger value="library" className="gap-1"><ListMusic className="h-3 w-3" /> Library</TabsTrigger>
              <TabsTrigger value="providers" className="gap-1"><BarChart3 className="h-3 w-3" /> Providers</TabsTrigger>
            </TabsList>

            <TabsContent value="library" className="flex-1 min-h-0 flex flex-col mt-2">
              <div className="px-4 py-2 border-b border-border">
                <Select value={scriptFilter} onValueChange={setScriptFilter}>
                  <SelectTrigger className="h-7 text-xs">
                    <SelectValue placeholder="Filter by script" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all" className="text-xs">All narrations</SelectItem>
                    {scripts.map((s) => (
                      <SelectItem key={s.id} value={s.id} className="text-xs">
                        {(s.title || s.topic).slice(0, 40)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <ScrollArea className="flex-1">
                {listLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  </div>
                ) : voices.length === 0 ? (
                  <div className="py-12 px-4 text-center text-xs text-muted-foreground">
                    No narrations yet. Generate one to get started.
                  </div>
                ) : (
                  <div className="py-1">
                    {voices.map((v) => (
                      <button
                        key={v.id}
                        onClick={() => setSelectedId(v.id)}
                        className={cn(
                          "w-full text-left px-4 py-3 border-b border-border hover:bg-accent/40 transition-colors",
                          selectedId === v.id && "bg-accent",
                        )}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-medium truncate capitalize">{v.voiceId} · {v.language}</p>
                            {v.totalDurationMs != null && (
                              <p className="text-[10px] text-muted-foreground font-mono mt-0.5">
                                {v.sections.length} section{v.sections.length !== 1 ? "s" : ""} · {formatMs(v.totalDurationMs)}
                              </p>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 flex-shrink-0">
                            {statusBadge(v.status)}
                            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </TabsContent>

            <TabsContent value="providers" className="flex-1 min-h-0 mt-2">
              <ScrollArea className="h-full px-4 pb-4">
                <ProviderStatistics stats={providerStats} loading={providerStatsLoading} />
              </ScrollArea>
            </TabsContent>
          </Tabs>
        </div>

        {/* Right panel — Voice Preview detail */}
        <div className="flex-1 min-w-0 flex flex-col">
          {!selected ? (
            <div className="flex flex-col items-center justify-center flex-1 gap-4 text-center px-8">
              <div className="relative">
                <Mic className="h-16 w-16 text-muted-foreground/20" />
                <Waves className="h-6 w-6 text-muted-foreground/40 absolute bottom-0 right-0" />
              </div>
              <div>
                <p className="font-medium text-sm">No Narration Selected</p>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm flex items-center gap-1.5 justify-center">
                  <Info className="h-3.5 w-3.5" />
                  Select a narration from the library or generate one from a completed script.
                </p>
              </div>
              {startMutation.isError && (
                <div className="text-xs text-destructive max-w-sm">
                  Generation failed: {String(startMutation.error)}
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1 overflow-auto p-6">
              <div className="max-w-3xl mx-auto space-y-4">
                <div className="flex justify-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs text-destructive hover:text-destructive"
                    onClick={() => deleteMutation.mutate({ id: selected.id })}
                    disabled={deleteMutation.isPending}
                  >
                    <Trash2 className="h-3.5 w-3.5 mr-1.5" />
                    Delete
                  </Button>
                </div>
                <VoiceDetail voice={selected} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
