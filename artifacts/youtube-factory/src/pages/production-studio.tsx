import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useListRenders,
  useListSubtitles,
  useStartSubtitle,
  useDeleteSubtitle,
  getListSubtitlesQueryKey,
  getGetProductionAssetsQueryKey,
  useListThumbnails,
  useStartThumbnail,
  useDeleteThumbnail,
  getListThumbnailsQueryKey,
  useListChapters,
  useStartChapter,
  useDeleteChapter,
  getListChaptersQueryKey,
  useGetProductionAssets,
  type RenderResult,
  type SubtitleResult,
  type ThumbnailResult,
  type ChapterResult,
  type ProductionAssetResult,
} from "@workspace/api-client-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import {
  PackageOpen,
  Subtitles,
  Image,
  BookOpen,
  Download,
  Trash2,
  RefreshCw,
  CheckCircle2,
  Clock,
  Loader2,
  AlertTriangle,
  Copy,
  Play,
  ChevronRight,
  BarChart3,
  ListChecks,
  FileText,
  Zap,
} from "lucide-react";

// ── Config ─────────────────────────────────────────────────────────────────────

const API_BASE = (import.meta.env.BASE_URL || "/").replace(/\/$/, "") + "/api";

function subtitleFileUrl(id: string, format: "srt" | "vtt" | "ass"): string {
  return `${API_BASE}/subtitles/${id}/file/${format}`;
}

function thumbnailFileUrl(id: string, candidateId: string): string {
  return `${API_BASE}/thumbnails/${id}/file/${candidateId}`;
}

function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "--";
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

// ── Common helpers ────────────────────────────────────────────────────────────

function statusBadge(status: string) {
  const map: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; label: string; icon: React.ReactNode }> = {
    pending:   { variant: "secondary",    label: "Queued",     icon: <Clock className="h-3 w-3" /> },
    running:   { variant: "default",      label: "Processing", icon: <Loader2 className="h-3 w-3 animate-spin" /> },
    completed: { variant: "outline",      label: "Completed",  icon: <CheckCircle2 className="h-3 w-3 text-emerald-500" /> },
    failed:    { variant: "destructive",  label: "Failed",     icon: <AlertTriangle className="h-3 w-3" /> },
    partial:   { variant: "secondary",    label: "Partial",    icon: <Clock className="h-3 w-3 text-amber-400" /> },
  };
  const cfg = map[status] ?? { variant: "secondary" as const, label: status, icon: null };
  return (
    <Badge variant={cfg.variant} className="gap-1 text-xs">
      {cfg.icon}
      {cfg.label}
    </Badge>
  );
}

function EmptyState({ message, icon: Icon = PackageOpen }: { message: string; icon?: React.ComponentType<{ className?: string }> }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 gap-3 text-center">
      <Icon className="h-8 w-8 text-muted-foreground/40" />
      <p className="text-xs text-muted-foreground">{message}</p>
    </div>
  );
}

function LogPanel({ logs }: { logs: string[] }) {
  return (
    <ScrollArea className="h-48 w-full">
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

// ── Processing Queue ──────────────────────────────────────────────────────────

function ProcessingQueue({
  subtitle, thumbnail, chapter,
}: {
  subtitle: SubtitleResult | null;
  thumbnail: ThumbnailResult | null;
  chapter: ChapterResult | null;
}) {
  const rows = [
    { label: "Subtitle Engine",   job: subtitle },
    { label: "Thumbnail Engine",  job: thumbnail },
    { label: "Chapter Engine",    job: chapter },
  ];
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <ListChecks className="h-4 w-4" />
          Processing Queue
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {rows.map(({ label, job }) => (
          <div key={label} className="flex items-center justify-between border border-border rounded-md px-3 py-2">
            <span className="text-xs font-medium">{label}</span>
            {job ? statusBadge(job.status) : <Badge variant="secondary" className="text-xs gap-1"><Clock className="h-3 w-3" />Not started</Badge>}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// ── Statistics Dashboard ──────────────────────────────────────────────────────

function StatsDashboard({
  subtitles, thumbnails, chapters,
}: {
  subtitles: SubtitleResult[];
  thumbnails: ThumbnailResult[];
  chapters: ChapterResult[];
}) {
  const countByStatus = (items: { status: string }[]) => ({
    completed: items.filter(x => x.status === "completed").length,
    failed:    items.filter(x => x.status === "failed").length,
    total:     items.length,
  });

  const sub  = countByStatus(subtitles);
  const thum = countByStatus(thumbnails);
  const chap = countByStatus(chapters);

  const StatCard = ({ label, stats }: { label: string; stats: { completed: number; failed: number; total: number } }) => {
    const rate = stats.total > 0 ? (stats.completed / stats.total) * 100 : 0;
    return (
      <div className="border border-border rounded-md p-3 space-y-2">
        <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
        <div className="flex items-end justify-between">
          <span className="text-xl font-mono font-bold">{stats.total}</span>
          <span className={cn("text-xs font-mono", rate >= 80 ? "text-emerald-400" : stats.failed > 0 ? "text-destructive" : "text-muted-foreground")}>
            {stats.completed}/{stats.total} ok
          </span>
        </div>
        {stats.total > 0 && <Progress value={rate} className="h-1" />}
      </div>
    );
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <BarChart3 className="h-4 w-4" />
          Statistics
        </CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-3 gap-3">
        <StatCard label="Subtitles"   stats={sub} />
        <StatCard label="Thumbnails"  stats={thum} />
        <StatCard label="Chapters"    stats={chap} />
      </CardContent>
    </Card>
  );
}

// ── Subtitle Manager ──────────────────────────────────────────────────────────

function SubtitleTab({
  renderId,
  subtitles,
  onStart,
  onDelete,
  starting,
}: {
  renderId: string;
  subtitles: SubtitleResult[];
  onStart: (renderId: string, language: string, providers: string[]) => void;
  onDelete: (id: string) => void;
  starting: boolean;
}) {
  const [language, setLanguage] = useState("en");
  const [selectedPreview, setSelectedPreview] = useState<"srt" | "vtt" | "ass">("srt");
  const [previewExpanded, setPreviewExpanded] = useState(false);

  const latest = subtitles[0] ?? null;
  const completed = latest?.status === "completed" ? latest : null;

  const style = (completed?.style ?? {}) as Record<string, string | number>;
  const presets = (completed?.captionPresets ?? []) as Array<{ id: string; label: string; burned?: boolean; fontSize?: number; position?: string; highlightColor?: string }>;

  const previewContent: Record<string, string | null | undefined> = {
    srt: completed?.srtContent,
    vtt: completed?.vttContent,
    ass: completed?.assContent,
  };

  return (
    <div className="space-y-4">
      {/* Subtitle Manager */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Subtitles className="h-4 w-4" />
            Subtitle Manager
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">Language</p>
              <Select value={language} onValueChange={setLanguage}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {["en", "es", "fr", "de", "pt", "ja", "zh", "ko"].map(l => (
                    <SelectItem key={l} value={l} className="text-xs">{l}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              size="sm"
              className="text-xs h-8"
              disabled={starting}
              onClick={() => onStart(renderId, language, ["whisper", "script-narration"])}
            >
              {starting ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Zap className="h-3.5 w-3.5 mr-1.5" />}
              Generate Subtitles
            </Button>
          </div>

          {subtitles.length === 0 && <EmptyState message="No subtitle jobs yet. Click Generate Subtitles to start." />}

          {subtitles.map(s => (
            <div key={s.id} className="border border-border rounded-md p-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs font-medium font-mono truncate">{s.id.slice(0, 20)}…</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    Lang: {s.language ?? "en"} · Provider: {s.usedProvider ?? "—"} · Words: {s.wordCount ?? "--"}
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {statusBadge(s.status)}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                    onClick={() => onDelete(s.id)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
              {s.status === "running" && (
                <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Transcribing audio…
                </div>
              )}
              {s.errorMessage && (
                <p className="text-[10px] text-destructive">{s.errorMessage}</p>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      {completed && (
        <>
          {/* Subtitle Preview */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  Subtitle Preview
                </CardTitle>
                <div className="flex items-center gap-2">
                  <div className="flex border border-border rounded-md overflow-hidden text-xs">
                    {(["srt", "vtt", "ass"] as const).map(fmt => (
                      <button
                        key={fmt}
                        onClick={() => setSelectedPreview(fmt)}
                        className={cn("px-2.5 py-1 uppercase", selectedPreview === fmt ? "bg-primary text-primary-foreground" : "hover:bg-accent")}
                      >
                        {fmt}
                      </button>
                    ))}
                  </div>
                  <a href={subtitleFileUrl(completed.id, selectedPreview)} download={`subtitles.${selectedPreview}`}>
                    <Button size="sm" variant="secondary" className="h-7 text-xs">
                      <Download className="h-3 w-3 mr-1.5" />
                      Download
                    </Button>
                  </a>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="relative">
                <ScrollArea className={previewExpanded ? "h-96" : "h-40"}>
                  <pre className="font-mono text-[11px] text-muted-foreground whitespace-pre-wrap break-all p-1">
                    {previewContent[selectedPreview] || "No content available."}
                  </pre>
                </ScrollArea>
                <button
                  className="text-[10px] text-muted-foreground hover:text-foreground mt-1 ml-1"
                  onClick={() => setPreviewExpanded(e => !e)}
                >
                  {previewExpanded ? "Show less ▲" : "Show more ▼"}
                </button>
              </div>
            </CardContent>
          </Card>

          {/* Caption Style Editor */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Caption Style</CardTitle>
            </CardHeader>
            <CardContent>
              {Object.keys(style).length === 0 ? (
                <p className="text-xs text-muted-foreground">No style data.</p>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(style).map(([key, val]) => (
                    <div key={key} className="border border-border rounded-md p-2">
                      <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{key}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        {String(val).startsWith("#") && (
                          <span className="w-3 h-3 rounded-sm border border-border inline-block flex-shrink-0" style={{ background: String(val) }} />
                        )}
                        <p className="text-xs font-mono truncate">{String(val)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Caption Presets */}
          {presets.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Caption Presets</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {presets.map(preset => (
                  <div key={preset.id} className="border border-border rounded-md p-2.5 flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-medium">{preset.label}</p>
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        {preset.fontSize}px · {preset.position}
                        {preset.burned ? " · burned-in" : ""}
                        {preset.highlightColor ? ` · highlight ${preset.highlightColor}` : ""}
                      </p>
                    </div>
                    <Badge variant="outline" className="text-[10px] font-mono">{preset.id}</Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Logs */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-muted-foreground">Subtitle Logs</CardTitle>
            </CardHeader>
            <CardContent><LogPanel logs={(completed.logs ?? []) as string[]} /></CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

// ── Thumbnail Browser + Frame Selector ────────────────────────────────────────

type CandidateObj = {
  candidateId: string;
  timestampMs: number;
  path?: string;
  width: number;
  height: number;
  sharpnessScore: number;
  qualityScore: number;
  brightness: number;
  dominantColor: string;
  safeTextRegions: unknown[];
};

type TemplateObj = {
  id: string;
  label: string;
  textRegion: string;
};

function ThumbnailTab({
  renderId,
  thumbnails,
  onStart,
  onDelete,
  starting,
}: {
  renderId: string;
  thumbnails: ThumbnailResult[];
  onStart: (renderId: string, count: number) => void;
  onDelete: (id: string) => void;
  starting: boolean;
}) {
  const [count, setCount] = useState(3);
  const [previewCandidate, setPreviewCandidate] = useState<CandidateObj | null>(null);

  const latest = thumbnails[0] ?? null;
  const completed = latest?.status === "completed" ? latest : null;

  const candidates = ((completed?.candidates ?? []) as CandidateObj[]);
  const selectedIds = ((completed?.selectedCandidateIds ?? []) as string[]);
  const templates = ((completed?.templates ?? []) as TemplateObj[]);
  const titleOverlay = (completed?.titleOverlay ?? {}) as Record<string, string | number | null>;
  const brandColors = ((completed?.brandColors ?? []) as string[]);

  return (
    <div className="space-y-4">
      {/* Thumbnail Manager */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Image className="h-4 w-4" />
            Thumbnail Browser
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">Candidates</p>
              <Select value={String(count)} onValueChange={v => setCount(Number(v))}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 5].map(n => (
                    <SelectItem key={n} value={String(n)} className="text-xs">{n} candidate{n > 1 ? "s" : ""}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              size="sm"
              className="text-xs h-8"
              disabled={starting}
              onClick={() => onStart(renderId, count)}
            >
              {starting ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Zap className="h-3.5 w-3.5 mr-1.5" />}
              Extract Frames
            </Button>
          </div>

          {thumbnails.length === 0 && <EmptyState message="No thumbnail jobs yet. Click Extract Frames to start." icon={Image} />}

          {thumbnails.map(t => (
            <div key={t.id} className="border border-border rounded-md p-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs font-medium font-mono truncate">{t.id.slice(0, 20)}…</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {((t.candidates ?? []) as unknown[]).length} candidate(s) extracted
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {statusBadge(t.status)}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                    onClick={() => onDelete(t.id)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
              {t.errorMessage && <p className="text-[10px] text-destructive">{t.errorMessage}</p>}
            </div>
          ))}
        </CardContent>
      </Card>

      {completed && candidates.length > 0 && (
        <>
          {/* Frame Selector / Thumbnail Preview */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Frame Selector</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-3 gap-2">
                {candidates.map(c => {
                  const isSelected = selectedIds.includes(c.candidateId);
                  return (
                    <div
                      key={c.candidateId}
                      className={cn(
                        "relative border-2 rounded-md overflow-hidden cursor-pointer transition-all",
                        isSelected ? "border-primary" : "border-border hover:border-muted-foreground",
                      )}
                      onClick={() => setPreviewCandidate(previewCandidate?.candidateId === c.candidateId ? null : c)}
                    >
                      <img
                        src={thumbnailFileUrl(completed.id, c.candidateId)}
                        alt={`Candidate ${c.candidateId}`}
                        className="w-full aspect-video object-cover bg-muted"
                        onError={e => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
                      />
                      <div className="absolute bottom-0 inset-x-0 bg-black/60 px-1.5 py-0.5">
                        <p className="text-[9px] font-mono text-white truncate">
                          Q:{c.qualityScore.toFixed(1)} · S:{c.sharpnessScore.toFixed(1)} · {formatMs(c.timestampMs)}
                        </p>
                      </div>
                      {isSelected && (
                        <div className="absolute top-1 right-1">
                          <CheckCircle2 className="h-4 w-4 text-primary bg-background rounded-full" />
                        </div>
                      )}
                      <a
                        href={thumbnailFileUrl(completed.id, c.candidateId)}
                        download={`thumbnail-${c.candidateId}.jpg`}
                        onClick={e => e.stopPropagation()}
                        className="absolute top-1 left-1"
                      >
                        <Button size="sm" variant="secondary" className="h-6 w-6 p-0 opacity-80">
                          <Download className="h-3 w-3" />
                        </Button>
                      </a>
                    </div>
                  );
                })}
              </div>

              {/* Thumbnail Preview */}
              {previewCandidate && (
                <div className="border border-border rounded-md overflow-hidden space-y-2 p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-medium">Thumbnail Preview</p>
                    <a href={thumbnailFileUrl(completed.id, previewCandidate.candidateId)} download={`thumbnail-${previewCandidate.candidateId}.jpg`}>
                      <Button size="sm" variant="secondary" className="h-7 text-xs">
                        <Download className="h-3 w-3 mr-1.5" />
                        Download
                      </Button>
                    </a>
                  </div>
                  <img
                    src={thumbnailFileUrl(completed.id, previewCandidate.candidateId)}
                    alt="Preview"
                    className="w-full rounded-md object-contain bg-muted"
                    style={{ maxHeight: 280 }}
                  />
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    {[
                      ["Resolution", `${previewCandidate.width}×${previewCandidate.height}`],
                      ["Sharpness", previewCandidate.sharpnessScore.toFixed(2)],
                      ["Quality",   previewCandidate.qualityScore.toFixed(2)],
                      ["Brightness", previewCandidate.brightness.toFixed(1)],
                      ["Timestamp", formatMs(previewCandidate.timestampMs)],
                      ["Dominant", previewCandidate.dominantColor],
                    ].map(([l, v]) => (
                      <div key={l} className="border border-border rounded-md p-2">
                        <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{l}</p>
                        <div className="flex items-center gap-1 mt-0.5">
                          {String(l) === "Dominant" && (
                            <span className="w-3 h-3 rounded-sm border border-border inline-block flex-shrink-0" style={{ background: String(v) }} />
                          )}
                          <p className="font-mono text-[11px] truncate">{v}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Templates */}
          {templates.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Thumbnail Templates</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-3 gap-2">
                {templates.map(t => (
                  <div key={t.id} className="border border-border rounded-md p-2.5">
                    <p className="text-xs font-medium">{t.label}</p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">{t.textRegion}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Brand Colors + Title Overlay */}
          <div className="grid grid-cols-2 gap-3">
            {brandColors.length > 0 && (
              <Card>
                <CardHeader className="pb-1">
                  <CardTitle className="text-xs text-muted-foreground">Brand Colors</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-2 flex-wrap">
                    {brandColors.map(color => (
                      <div key={color} className="flex items-center gap-1.5">
                        <span className="w-5 h-5 rounded border border-border" style={{ background: color }} />
                        <span className="font-mono text-[10px] text-muted-foreground">{color}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
            {titleOverlay.text && (
              <Card>
                <CardHeader className="pb-1">
                  <CardTitle className="text-xs text-muted-foreground">Title Overlay</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1">
                  {Object.entries(titleOverlay).filter(([, v]) => v != null).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs">
                      <span className="text-muted-foreground">{k}</span>
                      <span className="font-mono truncate max-w-[120px]">{String(v)}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Thumbnail Logs */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-muted-foreground">Thumbnail Logs</CardTitle>
            </CardHeader>
            <CardContent><LogPanel logs={(completed.logs ?? []) as string[]} /></CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

// ── Chapter Editor ────────────────────────────────────────────────────────────

type ChapterEntry = { title: string; startMs: number; endMs: number; description: string | null };

function formatYTTimestamp(ms: number): string {
  const totalSec = Math.max(ms, 0) / 1000 | 0;
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function ChapterTab({
  renderId,
  chapters,
  onStart,
  onDelete,
  starting,
}: {
  renderId: string;
  chapters: ChapterResult[];
  onStart: (renderId: string) => void;
  onDelete: (id: string) => void;
  starting: boolean;
}) {
  const [copied, setCopied] = useState(false);

  const latest = chapters[0] ?? null;
  const completed = latest?.status === "completed" ? latest : null;
  const chapterEntries = ((completed?.chapters ?? []) as ChapterEntry[]);
  const youtubeExport = completed?.youtubeExport ?? null;

  function copyExport() {
    if (youtubeExport) {
      navigator.clipboard.writeText(youtubeExport);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <div className="space-y-4">
      {/* Chapter Manager */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <BookOpen className="h-4 w-4" />
            Chapter Engine
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex justify-end">
            <Button
              size="sm"
              className="text-xs h-8"
              disabled={starting}
              onClick={() => onStart(renderId)}
            >
              {starting ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Zap className="h-3.5 w-3.5 mr-1.5" />}
              Generate Chapters
            </Button>
          </div>

          {chapters.length === 0 && <EmptyState message="No chapter jobs yet. Click Generate Chapters to start." icon={BookOpen} />}

          {chapters.map(c => (
            <div key={c.id} className="border border-border rounded-md p-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs font-medium font-mono truncate">{c.id.slice(0, 20)}…</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {((c.chapters ?? []) as unknown[]).length} chapter(s) generated
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {statusBadge(c.status)}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                    onClick={() => onDelete(c.id)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
              {c.errorMessage && <p className="text-[10px] text-destructive">{c.errorMessage}</p>}
            </div>
          ))}
        </CardContent>
      </Card>

      {completed && (
        <>
          {/* Chapter Editor */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Chapter Editor</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {chapterEntries.length === 0 && <EmptyState message="No chapters derived." />}
              {chapterEntries.map((entry, i) => (
                <div key={i} className="border border-border rounded-md p-2.5">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="font-mono text-[10px] flex-shrink-0">
                          {formatYTTimestamp(entry.startMs)}
                        </Badge>
                        <p className="text-xs font-medium truncate">{entry.title}</p>
                      </div>
                      {entry.description && (
                        <p className="text-[10px] text-muted-foreground mt-1 line-clamp-2">{entry.description}</p>
                      )}
                    </div>
                    <p className="text-[10px] font-mono text-muted-foreground flex-shrink-0">
                      {formatMs(entry.endMs - entry.startMs)}
                    </p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* YouTube Export */}
          {youtubeExport && (
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">YouTube Chapter Export</CardTitle>
                  <Button
                    size="sm"
                    variant="secondary"
                    className="h-7 text-xs"
                    onClick={copyExport}
                  >
                    {copied ? <CheckCircle2 className="h-3.5 w-3.5 mr-1.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5 mr-1.5" />}
                    {copied ? "Copied!" : "Copy"}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <pre className="font-mono text-xs text-muted-foreground whitespace-pre-wrap bg-muted/30 rounded-md p-3 border border-border">
                  {youtubeExport}
                </pre>
              </CardContent>
            </Card>
          )}

          {/* Chapter Logs */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-muted-foreground">Chapter Logs</CardTitle>
            </CardHeader>
            <CardContent><LogPanel logs={(completed.logs ?? []) as string[]} /></CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

// ── Export Manager ────────────────────────────────────────────────────────────

function ExportTab({
  bundle,
  subtitles,
  thumbnails,
}: {
  bundle: ProductionAssetResult | null | undefined;
  subtitles: SubtitleResult[];
  thumbnails: ThumbnailResult[];
}) {
  const manifest = (bundle?.exportManifest ?? {}) as {
    srtPath?: string | null;
    vttPath?: string | null;
    assPath?: string | null;
    thumbnailPaths?: string[];
    youtubeChapters?: string | null;
  };

  const completedSubtitle = subtitles.find(s => s.status === "completed") ?? null;
  const completedThumbnail = thumbnails.find(t => t.status === "completed") ?? null;
  const selectedCandidates = ((completedThumbnail?.candidates ?? []) as CandidateObj[]).filter(c =>
    ((completedThumbnail?.selectedCandidateIds ?? []) as string[]).includes(c.candidateId)
  );

  if (!bundle) {
    return <EmptyState message="Complete at least one post-processing job to see the export bundle." />;
  }

  return (
    <div className="space-y-4">
      {/* Production Asset Bundle */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm flex items-center gap-2">
              <PackageOpen className="h-4 w-4" />
              Production Asset Bundle
            </CardTitle>
            {statusBadge(bundle.status)}
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {[
            { label: "Subtitle",   id: bundle.subtitleId,  status: bundle.subtitle ? (bundle.subtitle as any).status : null },
            { label: "Thumbnail",  id: bundle.thumbnailId, status: bundle.thumbnail ? (bundle.thumbnail as any).status : null },
            { label: "Chapter",    id: bundle.chapterId,   status: bundle.chapter ? (bundle.chapter as any).status : null },
          ].map(row => (
            <div key={row.label} className="flex items-center justify-between border border-border rounded-md px-3 py-2">
              <div>
                <span className="text-xs font-medium">{row.label}</span>
                {row.id && (
                  <span className="text-[10px] text-muted-foreground ml-2 font-mono">{row.id.slice(0, 16)}…</span>
                )}
              </div>
              {row.status ? statusBadge(row.status) : <Badge variant="secondary" className="text-xs">—</Badge>}
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Subtitle Downloads */}
      {completedSubtitle && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Subtitle Files</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-3 gap-2">
            {(["srt", "vtt", "ass"] as const).map(fmt => (
              <a key={fmt} href={subtitleFileUrl(completedSubtitle.id, fmt)} download={`subtitles.${fmt}`}>
                <Button variant="outline" size="sm" className="w-full text-xs gap-1.5">
                  <Download className="h-3.5 w-3.5" />
                  .{fmt.toUpperCase()}
                </Button>
              </a>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Thumbnail Downloads */}
      {completedThumbnail && selectedCandidates.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Thumbnail Files ({selectedCandidates.length})</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-3 gap-2">
            {selectedCandidates.map((c, i) => (
              <a key={c.candidateId} href={thumbnailFileUrl(completedThumbnail.id, c.candidateId)} download={`thumbnail-${i + 1}.jpg`}>
                <Button variant="outline" size="sm" className="w-full text-xs gap-1.5">
                  <Download className="h-3.5 w-3.5" />
                  Thumb {i + 1}
                </Button>
              </a>
            ))}
          </CardContent>
        </Card>
      )}

      {/* YouTube Chapters */}
      {manifest.youtubeChapters && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">YouTube Chapters</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="font-mono text-xs text-muted-foreground whitespace-pre-wrap bg-muted/30 rounded-md p-3 border border-border">
              {manifest.youtubeChapters}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* Export Manifest */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-xs text-muted-foreground">Export Manifest</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="font-mono text-[10px] text-muted-foreground whitespace-pre-wrap break-all p-1">
            {JSON.stringify(manifest, null, 2)}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}

// ── Aggregate Logs ─────────────────────────────────────────────────────────────

function LogsTab({
  subtitle, thumbnail, chapter,
}: {
  subtitle: SubtitleResult | null;
  thumbnail: ThumbnailResult | null;
  chapter: ChapterResult | null;
}) {
  const sections = [
    { label: "Subtitle",  job: subtitle },
    { label: "Thumbnail", job: thumbnail },
    { label: "Chapter",   job: chapter },
  ];
  return (
    <div className="space-y-3">
      {sections.map(({ label, job }) => (
        <Card key={label}>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <CardTitle className="text-xs">{label} Logs</CardTitle>
              {job && statusBadge(job.status)}
            </div>
          </CardHeader>
          <CardContent>
            <LogPanel logs={(job?.logs ?? []) as string[]} />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function ProductionStudioPage() {
  const qc = useQueryClient();
  const [selectedRenderId, setSelectedRenderId] = useState<string | null>(null);

  // ── Data fetching ──
  const { data: rendersData } = useListRenders({ limit: 100 }, { query: { select: (d: { items?: RenderResult[]; total?: number }) => ({ ...d, items: (d.items ?? []).filter((r: RenderResult) => r.status === "completed") }) } });
  const completedRenders = (rendersData?.items ?? []) as RenderResult[];

  const subParams = selectedRenderId ? { renderId: selectedRenderId, limit: 20 } : undefined;
  const { data: subtitlesData, refetch: refetchSub } = useListSubtitles(subParams, {
    query: {
      enabled: !!selectedRenderId,
      refetchInterval: (q: any) => {
        const items = (q.state.data?.items ?? []) as SubtitleResult[];
        return items.some(s => s.status === "pending" || s.status === "running") ? 2000 : false;
      },
    },
  });

  const thumbParams = selectedRenderId ? { renderId: selectedRenderId, limit: 20 } : undefined;
  const { data: thumbnailsData, refetch: refetchThumb } = useListThumbnails(thumbParams, {
    query: {
      enabled: !!selectedRenderId,
      refetchInterval: (q: any) => {
        const items = (q.state.data?.items ?? []) as ThumbnailResult[];
        return items.some(t => t.status === "pending" || t.status === "running") ? 2000 : false;
      },
    },
  });

  const chapParams = selectedRenderId ? { renderId: selectedRenderId, limit: 20 } : undefined;
  const { data: chaptersData, refetch: refetchChap } = useListChapters(chapParams, {
    query: {
      enabled: !!selectedRenderId,
      refetchInterval: (q: any) => {
        const items = (q.state.data?.items ?? []) as ChapterResult[];
        return items.some(c => c.status === "pending" || c.status === "running") ? 2000 : false;
      },
    },
  });

  const { data: bundle } = useGetProductionAssets(selectedRenderId ?? "", {
    query: {
      enabled: !!selectedRenderId,
      refetchInterval: 5000,
    },
  });

  const subtitles = (subtitlesData?.items ?? []) as SubtitleResult[];
  const thumbnails = (thumbnailsData?.items ?? []) as ThumbnailResult[];
  const chapters   = (chaptersData?.items ?? []) as ChapterResult[];

  const latestSubtitle  = subtitles[0] ?? null;
  const latestThumbnail = thumbnails[0] ?? null;
  const latestChapter   = chapters[0] ?? null;

  // ── Mutations ──
  const startSubMutation = useStartSubtitle({
    mutation: {
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: getListSubtitlesQueryKey(subParams) });
        qc.invalidateQueries({ queryKey: getGetProductionAssetsQueryKey(selectedRenderId!) });
      },
    },
  });
  const deleteSubMutation = useDeleteSubtitle({
    mutation: { onSuccess: () => qc.invalidateQueries({ queryKey: getListSubtitlesQueryKey(subParams) }) },
  });

  const startThumbMutation = useStartThumbnail({
    mutation: {
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: getListThumbnailsQueryKey(thumbParams) });
        qc.invalidateQueries({ queryKey: getGetProductionAssetsQueryKey(selectedRenderId!) });
      },
    },
  });
  const deleteThumbMutation = useDeleteThumbnail({
    mutation: { onSuccess: () => qc.invalidateQueries({ queryKey: getListThumbnailsQueryKey(thumbParams) }) },
  });

  const startChapMutation = useStartChapter({
    mutation: {
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: getListChaptersQueryKey(chapParams) });
        qc.invalidateQueries({ queryKey: getGetProductionAssetsQueryKey(selectedRenderId!) });
      },
    },
  });
  const deleteChapMutation = useDeleteChapter({
    mutation: { onSuccess: () => qc.invalidateQueries({ queryKey: getListChaptersQueryKey(chapParams) }) },
  });

  // ── Handlers ──
  function handleStartSubtitle(renderId: string, language: string, providers: string[]) {
    startSubMutation.mutate({ data: { renderId, language, providers } as any });
  }
  function handleStartThumbnail(renderId: string, count: number) {
    startThumbMutation.mutate({ data: { renderId, count } as any });
  }
  function handleStartChapter(renderId: string) {
    startChapMutation.mutate({ data: { renderId } as any });
  }

  function handleRefresh() {
    refetchSub();
    refetchThumb();
    refetchChap();
    if (selectedRenderId) qc.invalidateQueries({ queryKey: getGetProductionAssetsQueryKey(selectedRenderId) });
  }

  const activeJobs = [...subtitles, ...thumbnails, ...chapters].filter(
    j => j.status === "pending" || j.status === "running"
  ).length;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-border px-6 py-4 flex items-center justify-between gap-4 flex-shrink-0">
        <div>
          <h1 className="text-lg font-bold font-mono flex items-center gap-2">
            <PackageOpen className="h-5 w-5 text-primary" />
            Production Studio
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Generate subtitles, thumbnails, and chapters from a completed render
          </p>
        </div>
        <div className="flex items-center gap-2">
          {activeJobs > 0 && (
            <Badge variant="secondary" className="gap-1.5 text-xs">
              <Loader2 className="h-3 w-3 animate-spin" />
              {activeJobs} processing
            </Badge>
          )}
          <Button variant="ghost" size="sm" onClick={handleRefresh}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Left panel — Render selector + queue */}
        <div className="w-72 border-r border-border flex flex-col flex-shrink-0">
          <div className="p-4 border-b border-border">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
              Select Render
            </p>
            {completedRenders.length === 0 ? (
              <p className="text-xs text-muted-foreground">No completed renders found.</p>
            ) : (
              <Select value={selectedRenderId ?? ""} onValueChange={v => setSelectedRenderId(v || null)}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue placeholder="Choose a render…" />
                </SelectTrigger>
                <SelectContent>
                  {completedRenders.map(r => (
                    <SelectItem key={r.id} value={r.id} className="text-xs">
                      {r.resolution} · {r.fps}fps · {r.id.slice(0, 12)}…
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {selectedRenderId && (
            <div className="p-4 space-y-4 overflow-auto flex-1">
              <ProcessingQueue
                subtitle={latestSubtitle}
                thumbnail={latestThumbnail}
                chapter={latestChapter}
              />
              <StatsDashboard
                subtitles={subtitles}
                thumbnails={thumbnails}
                chapters={chapters}
              />
            </div>
          )}
        </div>

        {/* Right panel */}
        <div className="flex-1 min-w-0 flex flex-col min-h-0">
          {!selectedRenderId ? (
            <div className="flex flex-col items-center justify-center flex-1 gap-4 text-center px-8">
              <PackageOpen className="h-16 w-16 text-muted-foreground/20" />
              <div>
                <p className="font-medium text-sm">No Render Selected</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Select a completed render from the left panel to start post-processing.
                </p>
              </div>
            </div>
          ) : (
            <Tabs defaultValue="subtitles" className="flex-1 flex flex-col min-h-0">
              <div className="border-b border-border px-4 pt-2 flex-shrink-0">
                <TabsList className="h-8 text-xs">
                  <TabsTrigger value="subtitles" className="gap-1.5">
                    <Subtitles className="h-3.5 w-3.5" />
                    Subtitles
                    {latestSubtitle && (
                      <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0",
                        latestSubtitle.status === "completed" ? "bg-emerald-500" :
                          latestSubtitle.status === "running"   ? "bg-primary animate-pulse" :
                            latestSubtitle.status === "failed"    ? "bg-destructive" : "bg-muted-foreground"
                      )} />
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="thumbnails" className="gap-1.5">
                    <Image className="h-3.5 w-3.5" />
                    Thumbnails
                    {latestThumbnail && (
                      <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0",
                        latestThumbnail.status === "completed" ? "bg-emerald-500" :
                          latestThumbnail.status === "running"   ? "bg-primary animate-pulse" :
                            latestThumbnail.status === "failed"    ? "bg-destructive" : "bg-muted-foreground"
                      )} />
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="chapters" className="gap-1.5">
                    <BookOpen className="h-3.5 w-3.5" />
                    Chapters
                    {latestChapter && (
                      <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0",
                        latestChapter.status === "completed" ? "bg-emerald-500" :
                          latestChapter.status === "running"   ? "bg-primary animate-pulse" :
                            latestChapter.status === "failed"    ? "bg-destructive" : "bg-muted-foreground"
                      )} />
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="export" className="gap-1.5">
                    <Download className="h-3.5 w-3.5" />
                    Export
                    {bundle?.status === "completed" && (
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="logs" className="gap-1.5">
                    <FileText className="h-3.5 w-3.5" />
                    Logs
                  </TabsTrigger>
                </TabsList>
              </div>

              <div className="flex-1 overflow-auto">
                <TabsContent value="subtitles" className="mt-0 p-4">
                  <div className="max-w-2xl mx-auto space-y-4">
                    <SubtitleTab
                      renderId={selectedRenderId}
                      subtitles={subtitles}
                      onStart={handleStartSubtitle}
                      onDelete={id => deleteSubMutation.mutate({ id })}
                      starting={startSubMutation.isPending}
                    />
                  </div>
                </TabsContent>

                <TabsContent value="thumbnails" className="mt-0 p-4">
                  <div className="max-w-2xl mx-auto space-y-4">
                    <ThumbnailTab
                      renderId={selectedRenderId}
                      thumbnails={thumbnails}
                      onStart={handleStartThumbnail}
                      onDelete={id => deleteThumbMutation.mutate({ id })}
                      starting={startThumbMutation.isPending}
                    />
                  </div>
                </TabsContent>

                <TabsContent value="chapters" className="mt-0 p-4">
                  <div className="max-w-2xl mx-auto space-y-4">
                    <ChapterTab
                      renderId={selectedRenderId}
                      chapters={chapters}
                      onStart={handleStartChapter}
                      onDelete={id => deleteChapMutation.mutate({ id })}
                      starting={startChapMutation.isPending}
                    />
                  </div>
                </TabsContent>

                <TabsContent value="export" className="mt-0 p-4">
                  <div className="max-w-2xl mx-auto space-y-4">
                    <ExportTab
                      bundle={bundle}
                      subtitles={subtitles}
                      thumbnails={thumbnails}
                    />
                  </div>
                </TabsContent>

                <TabsContent value="logs" className="mt-0 p-4">
                  <div className="max-w-2xl mx-auto space-y-4">
                    <LogsTab
                      subtitle={latestSubtitle}
                      thumbnail={latestThumbnail}
                      chapter={latestChapter}
                    />
                  </div>
                </TabsContent>
              </div>
            </Tabs>
          )}
        </div>
      </div>
    </div>
  );
}
