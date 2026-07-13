import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useListTimelines,
  useBuildTimeline,
  useGetTimeline,
  useDeleteTimeline,
  useListStoryboards,
  type TimelineResult,
  type TimelineTrack,
  type TimelineScene,
  type TimelineMarker,
  type TimelineRenderPlan,
  type TimelineMetadata,
  type StoryboardResult,
} from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import {
  Film,
  Play,
  Trash2,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  Video,
  Music,
  Type,
  Layers,
  BarChart3,
  ChevronRight,
  Flag,
  Clapperboard,
  Timer,
  HardDrive,
  Zap,
  Eye,
} from "lucide-react";

// ── Helpers ────────────────────────────────────────────────────────────────────

function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "--";
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const sec = s % 60;
  if (m === 0) return `${sec}s`;
  return `${m}m ${sec}s`;
}

function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "--";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function statusBadge(status: string) {
  const map: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; label: string; icon: React.ReactNode }> = {
    pending: { variant: "secondary", label: "Pending", icon: <Clock className="h-3 w-3" /> },
    running: { variant: "default", label: "Running", icon: <Loader2 className="h-3 w-3 animate-spin" /> },
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

function trackIcon(kind: string) {
  const icons: Record<string, React.ReactNode> = {
    video: <Video className="h-3.5 w-3.5" />,
    audio: <Music className="h-3.5 w-3.5" />,
    subtitle: <Type className="h-3.5 w-3.5" />,
    overlay: <Layers className="h-3.5 w-3.5" />,
  };
  return icons[kind] ?? <Layers className="h-3.5 w-3.5" />;
}

function trackColor(kind: string) {
  return {
    video: "bg-blue-500/20 border-blue-500/40 text-blue-400",
    audio: "bg-purple-500/20 border-purple-500/40 text-purple-400",
    subtitle: "bg-amber-500/20 border-amber-500/40 text-amber-400",
    overlay: "bg-emerald-500/20 border-emerald-500/40 text-emerald-400",
  }[kind] ?? "bg-muted border-border text-muted-foreground";
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
      <Film className="h-10 w-10 text-muted-foreground/40" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

/** Horizontal timeline ruler showing all scene blocks */
function SceneTimeline({ scenes, totalDurationMs }: { scenes: TimelineScene[]; totalDurationMs: number }) {
  if (!scenes.length || !totalDurationMs) return <EmptyState message="No scenes to display" />;
  return (
    <div className="space-y-4">
      <div className="relative h-12 bg-muted/30 rounded-md overflow-hidden border border-border">
        {scenes.map((scene, i) => {
          const left = (scene.startMs / totalDurationMs) * 100;
          const width = (scene.durationMs / totalDurationMs) * 100;
          const hasAsset = scene.hasVideoAsset;
          return (
            <div
              key={scene.sceneId}
              className={cn(
                "absolute top-1 bottom-1 rounded flex items-center justify-center text-[10px] font-mono overflow-hidden border transition-opacity",
                hasAsset
                  ? "bg-blue-500/30 border-blue-500/50 text-blue-300"
                  : "bg-muted border-border text-muted-foreground",
              )}
              style={{ left: `${left}%`, width: `calc(${width}% - 2px)` }}
              title={`${scene.title} (${formatMs(scene.durationMs)})`}
            >
              {width > 5 && <span className="truncate px-1">S{scene.sceneNumber}</span>}
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
        <span>0s</span>
        <span>{formatMs(totalDurationMs)}</span>
      </div>
    </div>
  );
}

/** Full track list with clip grid */
function TrackView({ tracks, totalDurationMs }: { tracks: TimelineTrack[]; totalDurationMs: number }) {
  if (!tracks.length) return <EmptyState message="No tracks in timeline" />;
  return (
    <div className="space-y-3">
      {tracks.map((track) => (
        <div key={track.trackId} className="space-y-1">
          <div className="flex items-center gap-2">
            <div className={cn("flex items-center gap-1.5 px-2 py-0.5 rounded text-xs border", trackColor(track.kind))}>
              {trackIcon(track.kind)}
              <span className="font-medium">{track.label}</span>
            </div>
            {track.isMuted && (
              <Badge variant="secondary" className="text-[10px] h-4">muted</Badge>
            )}
            <span className="text-[10px] text-muted-foreground font-mono ml-auto">
              {track.clips.length} clip{track.clips.length !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="relative h-8 bg-muted/20 rounded border border-border overflow-hidden">
            {totalDurationMs > 0 && track.clips.map((clip) => {
              const left = (clip.startMs / totalDurationMs) * 100;
              const width = (clip.durationMs / totalDurationMs) * 100;
              return (
                <div
                  key={clip.clipId}
                  className={cn(
                    "absolute top-0.5 bottom-0.5 rounded-sm border",
                    clip.assetId
                      ? trackColor(track.kind)
                      : "bg-muted/50 border-dashed border-border",
                  )}
                  style={{ left: `${left}%`, width: `calc(${width}% - 1px)` }}
                  title={`Clip at ${formatMs(clip.startMs)} — ${formatMs(clip.durationMs)}`}
                />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

/** Chapter markers list */
function MarkersView({ markers }: { markers: TimelineMarker[] }) {
  if (!markers.length) return <EmptyState message="No markers" />;
  return (
    <div className="space-y-2">
      {markers.map((m) => (
        <div key={m.markerId} className="flex items-center gap-3 py-2 border-b border-border last:border-0">
          <Flag className="h-3.5 w-3.5 text-amber-400 flex-shrink-0" />
          <span className="text-sm font-medium flex-1 truncate">{m.label}</span>
          <span className="text-xs font-mono text-muted-foreground">{formatMs(m.timestampMs)}</span>
          <Badge variant="outline" className="text-[10px]">{m.markerType}</Badge>
        </div>
      ))}
    </div>
  );
}

/** Scene inspector — list of all scenes with details */
function SceneInspector({ scenes }: { scenes: TimelineScene[] }) {
  if (!scenes.length) return <EmptyState message="No scenes" />;
  return (
    <div className="space-y-2">
      {scenes.map((scene) => (
        <div key={scene.sceneId} className="border border-border rounded-md p-3 space-y-2">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="font-mono text-[10px] w-8 justify-center flex-shrink-0">
              S{scene.sceneNumber}
            </Badge>
            <span className="text-sm font-medium flex-1 truncate">{scene.title}</span>
            <span className="text-xs font-mono text-muted-foreground">{formatMs(scene.durationMs)}</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {scene.hasVideoAsset
              ? <Badge variant="outline" className="text-[10px] text-blue-400 border-blue-500/30">✓ Asset</Badge>
              : <Badge variant="secondary" className="text-[10px]">No asset</Badge>
            }
            {scene.hasAudioPlaceholder && (
              <Badge variant="outline" className="text-[10px] text-purple-400 border-purple-500/30">Voice placeholder</Badge>
            )}
            {scene.transitionIn !== "cut" && (
              <Badge variant="outline" className="text-[10px]">↙ {scene.transitionIn}</Badge>
            )}
          </div>
          {scene.narration && (
            <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2 italic">
              {scene.narration}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

/** Render plan + statistics */
function RenderPreview({
  renderPlan,
  metadata,
}: {
  renderPlan: TimelineRenderPlan | null;
  metadata: TimelineMetadata | null;
}) {
  if (!renderPlan && !metadata) return <EmptyState message="No render plan available" />;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {renderPlan && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Clapperboard className="h-4 w-4" />
              Render Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {[
              ["Resolution", `${renderPlan.width}×${renderPlan.height}`],
              ["Frame Rate", `${renderPlan.fps} fps`],
              ["Format", (renderPlan.format ?? "mp4").toUpperCase()],
              ["Video Codec", renderPlan.codec],
              ["Audio Codec", renderPlan.audioCodec],
              ["Bitrate", `${renderPlan.bitrateKbps} kbps`],
              ["Est. Render Time", formatMs(renderPlan.estimatedRenderTimeMs)],
            ].map(([label, val]) => (
              <div key={label} className="flex justify-between border-b border-border pb-1 last:border-0">
                <span className="text-muted-foreground">{label}</span>
                <span className="font-mono text-xs">{val}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
      {metadata && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              Timeline Statistics
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {[
              ["Total Duration", formatMs(metadata.totalDurationMs)],
              ["Total Scenes", String(metadata.totalScenes)],
              ["Video Clips", String(metadata.videoClipCount)],
              ["Audio Clips", String(metadata.audioClipCount)],
              ["Asset Coverage", `${metadata.assetCoveragePct ?? 0}%`],
              ["Transitions", String(metadata.transitionCount)],
              ["Estimated Size", formatBytes(metadata.estimatedFileSizeBytes)],
            ].map(([label, val]) => (
              <div key={label} className="flex justify-between border-b border-border pb-1 last:border-0">
                <span className="text-muted-foreground">{label}</span>
                <span className="font-mono text-xs">{val}</span>
              </div>
            ))}
            {metadata.hasGaps && (
              <div className="flex items-center gap-1.5 text-amber-400 text-xs mt-1">
                <AlertTriangle className="h-3.5 w-3.5" />
                {metadata.gapCount} gap{metadata.gapCount !== 1 ? "s" : ""} detected
              </div>
            )}
            <div className="pt-1">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-muted-foreground">Asset Coverage</span>
                <span className={(metadata.assetCoveragePct ?? 0) >= 80 ? "text-emerald-400" : "text-amber-400"}>
                  {metadata.assetCoveragePct ?? 0}%
                </span>
              </div>
              <Progress value={metadata.assetCoveragePct ?? 0} className="h-1.5" />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/** Validation errors panel */
function ValidationPanel({ errors }: { errors: string[] }) {
  if (!errors.length) {
    return (
      <div className="flex items-center gap-2 text-emerald-400 text-sm py-4">
        <CheckCircle2 className="h-4 w-4" />
        No validation errors
      </div>
    );
  }
  return (
    <div className="space-y-2">
      {errors.map((err, i) => (
        <div key={i} className="flex items-start gap-2 p-2 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm">
          <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          {err}
        </div>
      ))}
    </div>
  );
}

/** Build log panel */
function BuildLogs({ logs }: { logs: string[] }) {
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

/** Detail view for a single timeline */
function TimelineDetail({ timeline }: { timeline: TimelineResult }) {
  const totalDurationMs = timeline.metadata?.totalDurationMs ?? timeline.totalDurationMs ?? 0;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold text-sm truncate">{timeline.title || timeline.topic}</h3>
          <p className="text-xs text-muted-foreground font-mono mt-0.5">{timeline.id}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {statusBadge(timeline.status)}
          {timeline.totalDurationMs && (
            <Badge variant="outline" className="text-xs gap-1">
              <Timer className="h-3 w-3" />
              {formatMs(timeline.totalDurationMs)}
            </Badge>
          )}
        </div>
      </div>

      {timeline.errorMessage && (
        <div className="flex items-start gap-2 p-3 rounded bg-destructive/10 border border-destructive/30 text-destructive text-sm">
          <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          {timeline.errorMessage}
        </div>
      )}

      <Tabs defaultValue="timeline">
        <TabsList className="h-8 text-xs">
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="tracks">Tracks</TabsTrigger>
          <TabsTrigger value="scenes">Scenes</TabsTrigger>
          <TabsTrigger value="render">Render</TabsTrigger>
          <TabsTrigger value="validation">Validation</TabsTrigger>
          <TabsTrigger value="logs">Logs</TabsTrigger>
        </TabsList>

        <TabsContent value="timeline" className="mt-4">
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Horizontal scene ruler — blue = has asset, grey = no asset
            </p>
            <SceneTimeline scenes={timeline.scenes} totalDurationMs={totalDurationMs} />
            {timeline.markers.length > 0 && (
              <div>
                <Separator className="my-3" />
                <p className="text-xs font-medium mb-2 flex items-center gap-1.5">
                  <Flag className="h-3.5 w-3.5 text-amber-400" />
                  Chapter Markers
                </p>
                <MarkersView markers={timeline.markers} />
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="tracks" className="mt-4">
          <TrackView tracks={timeline.tracks} totalDurationMs={totalDurationMs} />
        </TabsContent>

        <TabsContent value="scenes" className="mt-4">
          <ScrollArea className="h-[480px]">
            <SceneInspector scenes={timeline.scenes} />
          </ScrollArea>
        </TabsContent>

        <TabsContent value="render" className="mt-4">
          <RenderPreview renderPlan={timeline.renderPlan ?? null} metadata={timeline.metadata ?? null} />
        </TabsContent>

        <TabsContent value="validation" className="mt-4">
          <ValidationPanel errors={timeline.validationErrors} />
        </TabsContent>

        <TabsContent value="logs" className="mt-4">
          <BuildLogs logs={timeline.logs} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function TimelinesPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [storyboardFilter, setStoryboardFilter] = useState<string>("all");
  const [buildStoryboardId, setBuildStoryboardId] = useState<string>("");

  // List timelines
  const { data: timelinesData, isLoading: listLoading } = useListTimelines(
    storyboardFilter && storyboardFilter !== "all"
      ? { storyboardId: storyboardFilter, limit: 100 }
      : { limit: 100 },
  );

  // List storyboards for dropdown
  const { data: storyboardsData } = useListStoryboards({ limit: 100 });

  // Fetch selected timeline (cast needed: orval UseQueryOptions requires queryKey but it's auto-generated)
  const { data: selectedTimeline } = useGetTimeline(selectedId ?? "", {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    query: { enabled: !!selectedId } as any,
  });

  // Build mutation
  const buildMutation = useBuildTimeline({
    mutation: {
      onSuccess: (data) => {
        qc.invalidateQueries({ queryKey: ["timelines"] });
        setSelectedId((data as TimelineResult).id);
      },
    },
  });

  // Delete mutation
  const deleteMutation = useDeleteTimeline({
    mutation: {
      onSuccess: (_data, variables) => {
        qc.invalidateQueries({ queryKey: ["timelines"] });
        if (selectedId === (variables as { id: string }).id) setSelectedId(null);
      },
    },
  });

  const timelines: TimelineResult[] = (timelinesData?.items ?? []) as TimelineResult[];
  const storyboards: StoryboardResult[] = (storyboardsData?.items ?? []) as StoryboardResult[];
  const selected = selectedTimeline ?? timelines.find((t) => t.id === selectedId) ?? null;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-border px-6 py-4 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold font-mono flex items-center gap-2">
            <Clapperboard className="h-5 w-5 text-primary" />
            Media Timeline Engine
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Merge Storyboard + Assets + Voice (placeholder) → production timeline
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => qc.invalidateQueries({ queryKey: ["timelines"] })}
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Left panel — build + list */}
        <div className="w-80 border-r border-border flex flex-col flex-shrink-0">
          {/* Build form */}
          <div className="p-4 border-b border-border space-y-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Build New Timeline
            </p>
            <Select
              value={buildStoryboardId}
              onValueChange={setBuildStoryboardId}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder="Select storyboard…" />
              </SelectTrigger>
              <SelectContent>
                {storyboards
                  .filter((sb) => sb.status === "completed")
                  .map((sb) => (
                    <SelectItem key={sb.id} value={sb.id} className="text-xs">
                      {sb.topic.slice(0, 50)}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
            <Button
              size="sm"
              className="w-full text-xs"
              disabled={!buildStoryboardId || buildMutation.isPending}
              onClick={() => buildMutation.mutate({ data: { storyboardId: buildStoryboardId } })}
            >
              {buildMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <Zap className="h-3.5 w-3.5 mr-1.5" />
              )}
              Build Timeline
            </Button>
          </div>

          {/* Filter */}
          <div className="px-4 py-2 border-b border-border">
            <Select value={storyboardFilter} onValueChange={setStoryboardFilter}>
              <SelectTrigger className="h-7 text-xs">
                <SelectValue placeholder="Filter by storyboard" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all" className="text-xs">All timelines</SelectItem>
                {storyboards.map((sb) => (
                  <SelectItem key={sb.id} value={sb.id} className="text-xs">
                    {sb.topic.slice(0, 40)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Timeline list */}
          <ScrollArea className="flex-1">
            {listLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : timelines.length === 0 ? (
              <div className="py-12 px-4 text-center text-xs text-muted-foreground">
                No timelines yet. Build one to get started.
              </div>
            ) : (
              <div className="py-1">
                {timelines.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setSelectedId(t.id)}
                    className={cn(
                      "w-full text-left px-4 py-3 border-b border-border hover:bg-accent/40 transition-colors",
                      selectedId === t.id && "bg-accent",
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-medium truncate">
                          {t.title || t.topic}
                        </p>
                        {t.totalDurationMs != null && (
                          <p className="text-[10px] text-muted-foreground font-mono mt-0.5">
                            {t.totalScenes} scenes · {formatMs(t.totalDurationMs)}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        {statusBadge(t.status)}
                        <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </ScrollArea>
        </div>

        {/* Right panel — detail */}
        <div className="flex-1 min-w-0 flex flex-col">
          {!selected ? (
            <div className="flex flex-col items-center justify-center flex-1 gap-4 text-center px-8">
              <div className="relative">
                <Film className="h-16 w-16 text-muted-foreground/20" />
                <Play className="h-6 w-6 text-muted-foreground/40 absolute bottom-0 right-0" />
              </div>
              <div>
                <p className="font-medium text-sm">No Timeline Selected</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Select a timeline from the list or build a new one from a completed storyboard.
                </p>
              </div>
              {buildMutation.isError && (
                <div className="text-xs text-destructive max-w-sm">
                  Build failed: {String(buildMutation.error)}
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
                <TimelineDetail timeline={selected} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
