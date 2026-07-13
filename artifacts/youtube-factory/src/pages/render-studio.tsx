import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useListRenders,
  useStartRender,
  useGetRender,
  useDeleteRender,
  useGetRenderProviderStats,
  useListTimelines,
  useListVoices,
  getListRendersQueryKey,
  getGetRenderQueryKey,
  getGetRenderProviderStatsQueryKey,
  type RenderResult,
  type TimelineResult,
  type VoiceResult,
} from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import {
  Clapperboard,
  Trash2,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  Download,
  Film,
  BarChart3,
  ListVideo,
  Zap,
  ChevronRight,
  Gauge,
  Layers,
} from "lucide-react";

// ── Config helpers ───────────────────────────────────────────────────────────

const API_BASE = (import.meta.env.BASE_URL || "/").replace(/\/$/, "") + "/api";

function fileUrl(renderId: string, variant: "full" | "preview" = "full"): string {
  return `${API_BASE}/renders/${renderId}/file${variant === "preview" ? "?variant=preview" : ""}`;
}

function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "--";
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "--";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatSeconds(s: number | null | undefined): string {
  if (s == null) return "--";
  return `${s.toFixed(1)}s`;
}

const RESOLUTIONS = ["720p", "1080p", "4k"] as const;
const ASPECT_RATIOS = ["16:9", "9:16", "1:1"] as const;
const CROP_MODES = ["safe_crop", "letterbox", "blur_pad"] as const;

function statusBadge(status: string) {
  const map: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; label: string; icon: React.ReactNode }> = {
    pending: { variant: "secondary", label: "Queued", icon: <Clock className="h-3 w-3" /> },
    running: { variant: "default", label: "Rendering", icon: <Loader2 className="h-3 w-3 animate-spin" /> },
    completed: { variant: "outline", label: "Completed", icon: <CheckCircle2 className="h-3 w-3 text-emerald-500" /> },
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

function EmptyState({ message, icon: Icon = Film }: { message: string; icon?: React.ComponentType<{ className?: string }> }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
      <Icon className="h-10 w-10 text-muted-foreground/40" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────────

/** Output Player — real <video> playback of the rendered MP4 served from disk. */
function OutputPlayer({ render }: { render: RenderResult }) {
  const output = render.renderOutput as { localPath?: string; durationSeconds?: number; width?: number; height?: number } | null;
  if (render.status === "pending" || render.status === "running") {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-center h-56 rounded-md border border-dashed border-border bg-muted/20">
          <div className="text-center space-y-2">
            <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
            <p className="text-xs text-muted-foreground">Compositing with MoviePy/FFmpeg…</p>
          </div>
        </div>
        <Progress value={render.progress} className="h-1.5" />
        <p className="text-[11px] text-muted-foreground text-right font-mono">{render.progress}%</p>
      </div>
    );
  }
  if (render.status === "failed") {
    return <EmptyState message={render.errorMessage || "Render failed"} icon={AlertTriangle} />;
  }
  if (!output?.localPath) return <EmptyState message="No output file available" />;

  return (
    <div className="space-y-3">
      <video
        key={render.id}
        controls
        className="w-full rounded-md border border-border bg-black"
        style={{ aspectRatio: `${output.width || 16} / ${output.height || 9}` }}
        src={fileUrl(render.id)}
      />
      <div className="flex items-center justify-between">
        <p className="text-[11px] text-muted-foreground font-mono">
          {output.width}×{output.height} · {formatSeconds(output.durationSeconds)}
        </p>
        <a href={fileUrl(render.id)} download={`render-${render.id}.mp4`}>
          <Button size="sm" variant="secondary" className="text-xs h-7">
            <Download className="h-3.5 w-3.5 mr-1.5" />
            Download MP4
          </Button>
        </a>
      </div>
    </div>
  );
}

/** Timeline Preview — scene-by-scene breakdown of the resolved RenderPlan. */
function TimelinePreview({ renderPlan }: { renderPlan: Record<string, unknown> | null }) {
  const scenes = (renderPlan?.["scenes"] as any[]) || [];
  const totalMs = Number(renderPlan?.["total_duration_ms"] || 0);
  if (!scenes.length) return <EmptyState message="No render plan available yet" icon={Layers} />;
  return (
    <div className="space-y-3">
      <div className="relative h-10 bg-muted/30 rounded-md overflow-hidden border border-border">
        {scenes.map((s) => {
          const left = totalMs ? (s.start_ms / totalMs) * 100 : 0;
          const width = totalMs ? (s.duration_ms / totalMs) * 100 : 0;
          const placeholder = s.clips?.[0]?.kind === "placeholder";
          return (
            <div
              key={s.scene_index}
              className={cn(
                "absolute top-1 bottom-1 rounded flex items-center justify-center text-[10px] font-mono overflow-hidden border",
                placeholder ? "bg-amber-500/20 border-amber-500/40 text-amber-300" : "bg-primary/20 border-primary/40 text-primary",
              )}
              style={{ left: `${left}%`, width: `calc(${width}% - 2px)` }}
              title={`${s.title} (${formatMs(s.duration_ms)})`}
            >
              {width > 4 && <span className="truncate px-1">{s.scene_index + 1}</span>}
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
        <span>0:00</span>
        <span>{formatMs(totalMs)}</span>
      </div>
      <div className="space-y-1.5">
        {scenes.map((s) => (
          <div key={s.scene_index} className="border border-border rounded-md p-2.5 flex items-center gap-3">
            <Badge variant="outline" className="font-mono text-[10px] w-8 justify-center flex-shrink-0">
              S{s.scene_index + 1}
            </Badge>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium truncate">{s.title}</p>
              <p className="text-[11px] text-muted-foreground truncate">{s.narration || "—"}</p>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-[10px] font-mono text-muted-foreground">{formatMs(s.duration_ms)}</p>
              <p className="text-[10px] text-muted-foreground">
                {s.clips?.[0]?.kind === "placeholder" ? "placeholder" : s.clips?.[0]?.pan_direction ?? "—"}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Render Statistics — encode performance for a single completed render. */
function RenderStatistics({ render }: { render: RenderResult }) {
  const stats = render.renderStats as any;
  const output = render.renderOutput as any;
  const metadata = render.renderMetadata as any;
  return (
    <div className="grid grid-cols-2 gap-3">
      {[
        ["File Size", formatBytes(output?.fileSizeBytes)],
        ["Duration", formatSeconds(output?.durationSeconds)],
        ["Resolution", output?.width ? `${output.width}×${output.height}` : "--"],
        ["Codec", output?.codec ? `${output.codec} / ${output.audioCodec}` : "--"],
        ["Render Time", formatSeconds(stats?.renderTimeSeconds)],
        ["Encode Speed", stats?.encodeFps ? `${stats.encodeFps} fps` : "--"],
        ["Realtime Factor", stats?.realtimeFactor ? `${stats.realtimeFactor}×` : "--"],
        ["Frames Encoded", stats?.framesEncoded ?? "--"],
        ["Scenes", metadata?.sceneCount ?? "--"],
        ["Placeholder Clips", metadata?.placeholderClipCount ?? "--"],
      ].map(([label, val]) => (
        <div key={label} className="border border-border rounded-md p-2.5">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
          <p className="text-sm font-mono mt-0.5">{val}</p>
        </div>
      ))}
    </div>
  );
}

/** Generation Queue / Logs panel */
function RenderLogs({ logs }: { logs: string[] }) {
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

/** Provider Statistics — single-backend (MoviePy) aggregate stats. */
function ProviderStatistics({ stats, loading }: { stats: { backend?: string; totalRenders?: number; completed?: number; failed?: number; avgRenderTimeSeconds?: number; avgRealtimeFactor?: number; totalOutputSeconds?: number } | undefined; loading: boolean }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!stats || !stats.totalRenders) return <EmptyState message="No render activity yet" icon={Gauge} />;
  const successRate = stats.totalRenders > 0 ? ((stats.completed ?? 0) / stats.totalRenders) * 100 : 0;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          <span className="flex items-center gap-2">
            <Film className="h-4 w-4" />
            MoviePy / FFmpeg
          </span>
          <Badge variant="outline" className="text-[10px]">single backend</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-muted-foreground">Success rate</span>
          <span className={successRate >= 80 ? "text-emerald-400" : "text-amber-400"}>
            {successRate.toFixed(0)}% ({stats.completed}/{stats.totalRenders})
          </span>
        </div>
        <Progress value={successRate} className="h-1.5" />
        <div className="grid grid-cols-2 gap-2 pt-1 text-xs">
          <div className="flex justify-between border-b border-border pb-1">
            <span className="text-muted-foreground">Avg render time</span>
            <span className="font-mono">{formatSeconds(stats.avgRenderTimeSeconds)}</span>
          </div>
          <div className="flex justify-between border-b border-border pb-1">
            <span className="text-muted-foreground">Avg realtime factor</span>
            <span className="font-mono">{stats.avgRealtimeFactor?.toFixed(2) ?? "--"}×</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Total output</span>
            <span className="font-mono">{formatMs((stats.totalOutputSeconds ?? 0) * 1000)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Failed</span>
            <span className="font-mono">{stats.failed ?? 0}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/** Detail view for a single render job. */
function RenderDetail({ render }: { render: RenderResult }) {
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold text-sm">Render — {render.resolution} @ {render.fps}fps</h3>
          <p className="text-xs text-muted-foreground font-mono mt-0.5">{render.id}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {statusBadge(render.status)}
        </div>
      </div>

      {render.errorMessage && (
        <div className="flex items-start gap-2 p-3 rounded bg-destructive/10 border border-destructive/30 text-destructive text-sm">
          <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          {render.errorMessage}
        </div>
      )}

      <Tabs defaultValue="preview">
        <TabsList className="h-8 text-xs flex-wrap h-auto">
          <TabsTrigger value="preview">Output</TabsTrigger>
          <TabsTrigger value="timeline">Timeline Preview</TabsTrigger>
          <TabsTrigger value="stats">Statistics</TabsTrigger>
          <TabsTrigger value="logs">Logs</TabsTrigger>
        </TabsList>

        <TabsContent value="preview" className="mt-4">
          <OutputPlayer render={render} />
        </TabsContent>

        <TabsContent value="timeline" className="mt-4">
          <ScrollArea className="h-[420px]">
            <TimelinePreview renderPlan={render.renderPlan as Record<string, unknown> | null} />
          </ScrollArea>
        </TabsContent>

        <TabsContent value="stats" className="mt-4">
          <RenderStatistics render={render} />
        </TabsContent>

        <TabsContent value="logs" className="mt-4">
          <RenderLogs logs={render.logs} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function RenderStudioPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [timelineFilter, setTimelineFilter] = useState<string>("all");
  const [buildTimelineId, setBuildTimelineId] = useState<string>("");
  const [resolution, setResolution] = useState<typeof RESOLUTIONS[number]>("1080p");
  const [aspectRatio, setAspectRatio] = useState<typeof ASPECT_RATIOS[number]>("16:9");
  const [cropMode, setCropMode] = useState<typeof CROP_MODES[number]>("safe_crop");
  const [fps, setFps] = useState<number>(30);
  const [statsTab, setStatsTab] = useState<"queue" | "providers">("queue");

  const listParams = timelineFilter && timelineFilter !== "all" ? { timelineId: timelineFilter, limit: 100 } : { limit: 100 };

  // Render Queue — polls while any job is pending/running.
  const { data: rendersData, isLoading: listLoading } = useListRenders(listParams, {
    query: {
      refetchInterval: (query: { state: { data?: { items?: RenderResult[] } } }) => {
        const items = query.state.data?.items ?? [];
        const hasActive = items.some((r) => r.status === "pending" || r.status === "running");
        return hasActive ? 2000 : false;
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any,
  });

  const { data: timelinesData } = useListTimelines({ limit: 100 });
  const { data: voicesData } = useListVoices({ limit: 100 });
  const { data: providerStats, isLoading: providerStatsLoading } = useGetRenderProviderStats();

  const selectedIsActive = useMemo(() => {
    const items = (rendersData?.items ?? []) as RenderResult[];
    const r = items.find((x) => x.id === selectedId);
    return r ? r.status === "pending" || r.status === "running" : false;
  }, [rendersData, selectedId]);

  const { data: selectedRender } = useGetRender(selectedId ?? "", {
    query: {
      enabled: !!selectedId,
      refetchInterval: selectedIsActive ? 2000 : false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any,
  });

  const startMutation = useStartRender({
    mutation: {
      onSuccess: (data) => {
        qc.invalidateQueries({ queryKey: getListRendersQueryKey(listParams) });
        qc.invalidateQueries({ queryKey: getGetRenderProviderStatsQueryKey() });
        setSelectedId((data as RenderResult).id);
      },
    },
  });

  const deleteMutation = useDeleteRender({
    mutation: {
      onSuccess: (_data, variables) => {
        qc.invalidateQueries({ queryKey: getListRendersQueryKey(listParams) });
        qc.invalidateQueries({ queryKey: getGetRenderProviderStatsQueryKey() });
        const deletedId = (variables as { id: string }).id;
        qc.removeQueries({ queryKey: getGetRenderQueryKey(deletedId) });
        if (selectedId === deletedId) setSelectedId(null);
      },
    },
  });

  const renders: RenderResult[] = (rendersData?.items ?? []) as RenderResult[];
  const timelines: TimelineResult[] = (timelinesData?.items ?? []) as TimelineResult[];
  const voices: VoiceResult[] = (voicesData?.items ?? []) as VoiceResult[];
  const selected = selectedRender ?? renders.find((r) => r.id === selectedId) ?? null;
  const activeJobs = renders.filter((r) => r.status === "pending" || r.status === "running");
  const readyTimelines = timelines.filter((t) => t.status === "completed");
  const buildTimeline = readyTimelines.find((t) => t.id === buildTimelineId);
  const matchingVoice = buildTimeline?.scriptId
    ? voices.find((v) => v.scriptId === buildTimeline.scriptId && v.status === "completed")
    : undefined;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-border px-6 py-4 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold font-mono flex items-center gap-2">
            <Clapperboard className="h-5 w-5 text-primary" />
            Render Studio
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Composite Timeline + Voice + Assets into a real MP4 via MoviePy/FFmpeg
          </p>
        </div>
        <div className="flex items-center gap-2">
          {activeJobs.length > 0 && (
            <Badge variant="secondary" className="gap-1.5 text-xs">
              <Loader2 className="h-3 w-3 animate-spin" />
              {activeJobs.length} rendering
            </Badge>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              qc.invalidateQueries({ queryKey: getListRendersQueryKey(listParams) });
              qc.invalidateQueries({ queryKey: getGetRenderProviderStatsQueryKey() });
              if (selectedId) qc.invalidateQueries({ queryKey: getGetRenderQueryKey(selectedId) });
            }}
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Left panel — build form + queue/library */}
        <div className="w-80 border-r border-border flex flex-col flex-shrink-0">
          <div className="p-4 border-b border-border space-y-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Start a Render
            </p>
            <Select value={buildTimelineId} onValueChange={setBuildTimelineId}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder="Select timeline…" />
              </SelectTrigger>
              <SelectContent>
                {readyTimelines.map((t) => (
                  <SelectItem key={t.id} value={t.id} className="text-xs">
                    {(t.title || t.topic).slice(0, 50)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {buildTimelineId && (
              <p className="text-[10px] text-muted-foreground">
                Narration: {matchingVoice ? "auto-detected ✓" : "none found — video will render silent"}
              </p>
            )}

            <div className="grid grid-cols-2 gap-2">
              <Select value={resolution} onValueChange={(v) => setResolution(v as typeof RESOLUTIONS[number])}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Resolution" />
                </SelectTrigger>
                <SelectContent>
                  {RESOLUTIONS.map((r) => (
                    <SelectItem key={r} value={r} className="text-xs">{r}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={String(fps)} onValueChange={(v) => setFps(Number(v))}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="FPS" />
                </SelectTrigger>
                <SelectContent>
                  {[24, 30, 60].map((f) => (
                    <SelectItem key={f} value={String(f)} className="text-xs">{f} fps</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={aspectRatio} onValueChange={(v) => setAspectRatio(v as typeof ASPECT_RATIOS[number])}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Aspect" />
                </SelectTrigger>
                <SelectContent>
                  {ASPECT_RATIOS.map((a) => (
                    <SelectItem key={a} value={a} className="text-xs">{a}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={cropMode} onValueChange={(v) => setCropMode(v as typeof CROP_MODES[number])}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Crop" />
                </SelectTrigger>
                <SelectContent>
                  {CROP_MODES.map((c) => (
                    <SelectItem key={c} value={c} className="text-xs">{c.replace("_", " ")}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button
              size="sm"
              className="w-full text-xs"
              disabled={!buildTimelineId || startMutation.isPending}
              onClick={() =>
                startMutation.mutate({
                  data: {
                    timelineId: buildTimelineId,
                    voiceId: matchingVoice?.id,
                    resolution, fps, aspectRatio, cropMode,
                    generatePreview: false,
                  },
                })
              }
            >
              {startMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <Zap className="h-3.5 w-3.5 mr-1.5" />
              )}
              Render Video
            </Button>
          </div>

          <Tabs value={statsTab} onValueChange={(v) => setStatsTab(v as "queue" | "providers")} className="flex-1 flex flex-col min-h-0">
            <TabsList className="h-8 text-xs mx-4 mt-2">
              <TabsTrigger value="queue" className="gap-1"><ListVideo className="h-3 w-3" /> Queue</TabsTrigger>
              <TabsTrigger value="providers" className="gap-1"><BarChart3 className="h-3 w-3" /> Stats</TabsTrigger>
            </TabsList>

            <TabsContent value="queue" className="flex-1 min-h-0 flex flex-col mt-2">
              <div className="px-4 py-2 border-b border-border">
                <Select value={timelineFilter} onValueChange={setTimelineFilter}>
                  <SelectTrigger className="h-7 text-xs">
                    <SelectValue placeholder="Filter by timeline" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all" className="text-xs">All renders</SelectItem>
                    {timelines.map((t) => (
                      <SelectItem key={t.id} value={t.id} className="text-xs">
                        {(t.title || t.topic).slice(0, 40)}
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
                ) : renders.length === 0 ? (
                  <div className="py-12 px-4 text-center text-xs text-muted-foreground">
                    No renders yet. Start one from a completed timeline.
                  </div>
                ) : (
                  <div className="py-1">
                    {renders.map((r) => (
                      <button
                        key={r.id}
                        onClick={() => setSelectedId(r.id)}
                        className={cn(
                          "w-full text-left px-4 py-3 border-b border-border hover:bg-accent/40 transition-colors",
                          selectedId === r.id && "bg-accent",
                        )}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-medium truncate">
                              {r.resolution} · {r.fps}fps · {r.aspectRatio}
                            </p>
                            <p className="text-[10px] text-muted-foreground font-mono mt-0.5">
                              {(r.renderOutput as any)?.durationSeconds
                                ? formatSeconds((r.renderOutput as any).durationSeconds)
                                : r.status === "running" ? `${r.progress}%` : "--"}
                            </p>
                          </div>
                          <div className="flex items-center gap-1.5 flex-shrink-0">
                            {statusBadge(r.status)}
                            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </TabsContent>

            <TabsContent value="providers" className="flex-1 min-h-0 mt-2 px-4 pb-4 overflow-auto">
              <ProviderStatistics stats={providerStats} loading={providerStatsLoading} />
            </TabsContent>
          </Tabs>
        </div>

        {/* Right panel — detail */}
        <div className="flex-1 min-w-0 flex flex-col">
          {!selected ? (
            <div className="flex flex-col items-center justify-center flex-1 gap-4 text-center px-8">
              <div className="relative">
                <Film className="h-16 w-16 text-muted-foreground/20" />
              </div>
              <div>
                <p className="font-medium text-sm">No Render Selected</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Select a render from the queue, or start a new one from a completed timeline.
                </p>
              </div>
              {startMutation.isError && (
                <div className="text-xs text-destructive max-w-sm">
                  Failed to start render: {String(startMutation.error)}
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
                <RenderDetail render={selected} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
