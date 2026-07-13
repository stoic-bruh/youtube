import React, { useState, useRef, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { format } from 'date-fns';
import { motion, AnimatePresence } from 'framer-motion';
import { useQueryClient } from '@tanstack/react-query';
import {
  useListStoryboards, getListStoryboardsQueryKey,
  useStartStoryboard, useDeleteStoryboard, useGetStoryboard, getGetStoryboardQueryKey,
  StoryboardResult, StoryboardScene, StoryboardSceneTimeline,
} from '@workspace/api-client-react';

import {
  Film, Play, RefreshCw, CheckCircle2, Clock, AlertCircle,
  Trash2, X, Image, Camera, Music, ChevronRight, ChevronDown,
  Layers, Eye, Zap, DollarSign, Timer, Clapperboard,
} from 'lucide-react';

import { cn } from "@/lib/utils";
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';

// ── Constants ──────────────────────────────────────────────────────────────────

const AVAILABLE_PROVIDERS = [
  { id: 'openai', label: 'OpenAI' },
  { id: 'gemini', label: 'Gemini' },
  { id: 'claude', label: 'Claude' },
  { id: 'openrouter', label: 'OpenRouter' },
];

const STYLES = [
  { value: 'educational', label: 'Educational' },
  { value: 'documentary', label: 'Documentary' },
  { value: 'storytelling', label: 'Storytelling' },
  { value: 'tutorial', label: 'Tutorial' },
  { value: 'news', label: 'News' },
  { value: 'long_form', label: 'Long Form' },
  { value: 'shorts', label: 'Shorts' },
];

const TONES = [
  { value: 'engaging', label: 'Engaging' },
  { value: 'authoritative', label: 'Authoritative' },
  { value: 'casual', label: 'Casual' },
  { value: 'inspirational', label: 'Inspirational' },
  { value: 'conversational', label: 'Conversational' },
];

const SHOT_COLORS: Record<string, string> = {
  wide: 'text-blue-400 border-blue-400/20',
  medium: 'text-emerald-400 border-emerald-400/20',
  close_up: 'text-amber-400 border-amber-400/20',
  extreme_close_up: 'text-red-400 border-red-400/20',
  establishing: 'text-purple-400 border-purple-400/20',
  aerial: 'text-cyan-400 border-cyan-400/20',
  over_the_shoulder: 'text-pink-400 border-pink-400/20',
};

const VISUAL_TYPE_COLORS: Record<string, string> = {
  b_roll: 'text-blue-400',
  talking_head: 'text-amber-400',
  animation: 'text-purple-400',
  text_overlay: 'text-emerald-400',
  screen_recording: 'text-cyan-400',
  illustration: 'text-pink-400',
  infographic: 'text-orange-400',
};

const TRANSITION_LABELS: Record<string, string> = {
  cut: 'CUT', dissolve: 'DISS', fade: 'FADE',
  wipe_left: 'WIPE←', wipe_right: 'WIPE→', zoom_transition: 'ZOOM',
  morph: 'MORPH', flash: 'FLASH',
};

// ── Form schema ─────────────────────────────────────────────────────────────────

const formSchema = z.object({
  topic: z.string().min(3, "Topic must be at least 3 characters"),
  scriptStyle: z.string().optional(),
  scriptTone: z.string().optional(),
  targetDurationMinutes: z.coerce.number().int().min(1).max(120).optional(),
  providers: z.array(z.string()).min(1, "Select at least one provider").default(['openai', 'claude']),
});

// ── Helpers ────────────────────────────────────────────────────────────────────

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return '—';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function formatMs(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return m > 0 ? `${m}:${String(rem).padStart(2, '0')}` : `0:${String(rem).padStart(2, '0')}`;
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; className: string; icon: any }> = {
    pending: { label: 'PENDING', className: 'bg-status-queued text-amber-500 border-amber-500/20', icon: Clock },
    running: { label: 'RUNNING', className: 'bg-status-running text-emerald-500 border-emerald-500/20 animate-pulse-running', icon: RefreshCw },
    completed: { label: 'COMPLETED', className: 'bg-status-completed text-blue-500 border-blue-500/20', icon: CheckCircle2 },
    failed: { label: 'FAILED', className: 'bg-status-failed text-red-500 border-red-500/20', icon: AlertCircle },
  };
  const c = config[status] ?? config.pending;
  const Icon = c.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${c.className}`}>
      <Icon className="w-3 h-3" /> {c.label}
    </span>
  );
}

function MetricChip({ icon: Icon, label, value, className = '' }: {
  icon: any; label: string; value: string | number | null | undefined; className?: string;
}) {
  if (value === null || value === undefined) return null;
  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-mono ${className}`}>
      <Icon className="w-3 h-3 opacity-60" />
      <span className="opacity-50">{label}</span>
      <span className="font-bold">{value}</span>
    </div>
  );
}

function LogsTerminal({ logs }: { logs: string[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [logs]);
  if (!logs?.length) {
    return <div className="p-4 text-xs font-mono text-muted-foreground flex items-center justify-center h-full">AWAITING TELEMETRY...</div>;
  }
  return (
    <div className="bg-black text-gray-300 font-mono text-xs rounded-md overflow-hidden flex flex-col h-full border border-gray-800">
      <div className="bg-gray-900 px-3 py-2 flex items-center gap-2 border-b border-gray-800 shrink-0">
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500/80" />
          <div className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
        </div>
        <span className="text-gray-500 text-[10px] ml-2 tracking-widest">STORYBOARD_PROCESS_TTY</span>
      </div>
      <div ref={ref} className="p-4 overflow-y-auto flex-1 space-y-1">
        {logs.map((log, i) => {
          const colorClass = log.includes("ERROR") ? "text-red-400" :
                             log.includes("WARN") ? "text-amber-400" :
                             log.includes("INFO") ? "text-emerald-400" : "text-gray-300";
          return (
            <div key={i} className={colorClass}>
              <span className="opacity-40 mr-3 select-none">{String(i + 1).padStart(4, '0')}</span>
              <span className="whitespace-pre-wrap">{log}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Scene card ─────────────────────────────────────────────────────────────────

function SceneCard({ scene, index }: { scene: StoryboardScene; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const shotClass = SHOT_COLORS[scene.shot_type ?? 'medium'] ?? 'text-muted-foreground border-border';
  const vtClass = VISUAL_TYPE_COLORS[scene.visual_type ?? 'b_roll'] ?? 'text-muted-foreground';
  const transLabel = TRANSITION_LABELS[scene.transition_type ?? 'cut'] ?? 'CUT';

  return (
    <div className="border border-border rounded-md overflow-hidden">
      {/* Scene header */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-start gap-3 p-3 text-left hover:bg-accent/30 transition-colors"
      >
        {/* Scene number */}
        <div className="shrink-0 w-10 h-10 rounded bg-primary/10 border border-primary/20 flex items-center justify-center">
          <span className="text-xs font-mono font-bold text-primary">{String(scene.scene_number).padStart(2, '0')}</span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-sm font-medium text-foreground truncate">{scene.scene_title}</span>
          </div>
          <div className="flex items-center gap-2 flex-wrap text-[10px] font-mono text-muted-foreground">
            <span className={`px-1 py-0.5 rounded border text-[9px] font-bold uppercase ${shotClass}`}>
              {scene.shot_type?.replace(/_/g, ' ')}
            </span>
            <span className={`font-bold ${vtClass}`}>{scene.visual_type?.replace(/_/g, ' ')}</span>
            <span>{formatMs(scene.start_time_ms)} – {formatMs(scene.end_time_ms)}</span>
            {scene.scene_emotion && <span className="opacity-60">/ {scene.scene_emotion}</span>}
          </div>
        </div>

        {/* Importance bar */}
        <div className="shrink-0 flex flex-col items-end gap-1">
          <div className="text-[9px] font-mono text-muted-foreground">IMP</div>
          <div className="w-16 h-1.5 rounded-full bg-border overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${((scene.importance_score ?? 0.5) * 100).toFixed(0)}%` }}
            />
          </div>
        </div>

        <ChevronRight className={`w-4 h-4 text-muted-foreground shrink-0 mt-2 transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </button>

      {/* Expanded detail */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="border-t border-border bg-card/20 p-4 space-y-4">
              {/* Narration */}
              <div>
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Narration</div>
                <p className="text-sm text-card-foreground leading-relaxed italic">{scene.narration}</p>
              </div>

              {/* Visual description */}
              <div>
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Visual</div>
                <p className="text-sm text-muted-foreground leading-relaxed">{scene.visual_description}</p>
              </div>

              {/* Image prompt */}
              {scene.prompts?.image_prompt && (
                <div>
                  <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5 flex items-center gap-1.5">
                    <Image className="w-3 h-3" /> Image Prompt
                  </div>
                  <p className="text-xs font-mono text-primary/80 bg-primary/5 border border-primary/20 rounded p-3 leading-relaxed">
                    {scene.prompts.image_prompt}
                  </p>
                </div>
              )}

              {/* Video prompt */}
              {scene.prompts?.video_prompt && (
                <div>
                  <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5 flex items-center gap-1.5">
                    <Film className="w-3 h-3" /> Video Prompt
                  </div>
                  <p className="text-xs font-mono text-purple-400/80 bg-purple-400/5 border border-purple-400/20 rounded p-3 leading-relaxed">
                    {scene.prompts.video_prompt}
                  </p>
                </div>
              )}

              {/* Camera & Lighting */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2 flex items-center gap-1.5">
                    <Camera className="w-3 h-3" /> Camera
                  </div>
                  <div className="space-y-1 text-xs font-mono text-muted-foreground">
                    <div><span className="opacity-50">Angle:</span> {scene.camera_angle?.replace(/_/g, ' ')}</div>
                    <div><span className="opacity-50">Move:</span> {scene.camera_movement?.replace(/_/g, ' ')}</div>
                    {scene.zoom_instructions && <div><span className="opacity-50">Zoom:</span> {scene.zoom_instructions}</div>}
                    {scene.pan_instructions && <div><span className="opacity-50">Pan:</span> {scene.pan_instructions}</div>}
                    <div><span className="opacity-50">Transition:</span> {transLabel}</div>
                  </div>
                </div>
                <div>
                  <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Lighting & Mood</div>
                  <div className="space-y-1 text-xs font-mono text-muted-foreground">
                    <div><span className="opacity-50">Style:</span> {scene.lighting_style?.replace(/_/g, ' ')}</div>
                    <div><span className="opacity-50">Emotion:</span> {scene.scene_emotion}</div>
                    <div className="flex items-center gap-1">
                      <span className="opacity-50">Palette:</span>
                      {(scene.color_palette ?? []).slice(0, 4).map((c, i) => (
                        <div key={i} className="w-3 h-3 rounded-sm border border-border/50" style={{ backgroundColor: c }} title={c} />
                      ))}
                    </div>
                    <div><span className="opacity-50">Music:</span> {scene.background_music_mood}</div>
                  </div>
                </div>
              </div>

              {/* Text overlays, SFX, B-roll */}
              <div className="grid grid-cols-3 gap-3">
                {(scene.text_overlay_suggestions ?? []).length > 0 && (
                  <div>
                    <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Text Overlays</div>
                    {(scene.text_overlay_suggestions ?? []).map((t, i) => (
                      <div key={i} className="text-xs text-muted-foreground truncate">{t}</div>
                    ))}
                  </div>
                )}
                {(scene.sound_effect_suggestions ?? []).length > 0 && (
                  <div>
                    <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5 flex items-center gap-1">
                      <Music className="w-2.5 h-2.5" /> SFX
                    </div>
                    {(scene.sound_effect_suggestions ?? []).map((s, i) => (
                      <div key={i} className="text-xs text-muted-foreground truncate">{s}</div>
                    ))}
                  </div>
                )}
                {(scene.b_roll_suggestions ?? []).length > 0 && (
                  <div>
                    <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">B-Roll</div>
                    {(scene.b_roll_suggestions ?? []).map((b, i) => (
                      <div key={i} className="text-xs text-muted-foreground truncate">{b}</div>
                    ))}
                  </div>
                )}
              </div>

              {/* Objects & Characters */}
              {((scene.objects ?? []).length > 0 || (scene.characters ?? []).length > 0) && (
                <div className="flex flex-wrap gap-1.5">
                  {(scene.characters ?? []).map((c, i) => (
                    <span key={`c${i}`} className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-amber-400/20 text-amber-400 bg-amber-400/5">{c}</span>
                  ))}
                  {(scene.objects ?? []).map((o, i) => (
                    <span key={`o${i}`} className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-border text-muted-foreground">{o}</span>
                  ))}
                </div>
              )}

              {/* Asset requirements */}
              {(scene.asset_requirements ?? []).length > 0 && (
                <div>
                  <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Asset Requirements</div>
                  <div className="space-y-1">
                    {(scene.asset_requirements ?? []).slice(0, 3).map((a: any, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <span className={`text-[9px] font-mono font-bold uppercase px-1 rounded border ${a.is_required ? 'text-red-400 border-red-400/20' : 'text-muted-foreground border-border'}`}>
                          {a.asset_type}
                        </span>
                        <span className="text-muted-foreground truncate">{a.description}</span>
                        <span className="text-[9px] text-muted-foreground/60 shrink-0">{a.source_type}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Timeline view ─────────────────────────────────────────────────────────────

function TimelineView({ timeline, totalDurationMs }: { timeline: StoryboardSceneTimeline[]; totalDurationMs: number }) {
  if (!timeline?.length) return (
    <div className="text-xs text-muted-foreground text-center py-12">No timeline data yet</div>
  );
  const totalMs = totalDurationMs || timeline[timeline.length - 1]?.end_time_ms || 1;

  return (
    <div className="space-y-4">
      {/* Visual timeline bar */}
      <div className="relative h-12 bg-card/50 border border-border rounded-md overflow-hidden">
        {timeline.map((t, i) => {
          const left = (t.start_time_ms / totalMs) * 100;
          const width = Math.max(0.3, (t.duration_ms / totalMs) * 100);
          const hue = (i * 31) % 360;
          return (
            <div
              key={i}
              className="absolute top-0 bottom-0 border-r border-background/20"
              style={{ left: `${left}%`, width: `${width}%`, backgroundColor: `hsl(${hue}, 60%, 30%)` }}
              title={`${t.scene_title} (${formatMs(t.start_time_ms)} – ${formatMs(t.end_time_ms)})`}
            />
          );
        })}
        {/* Time markers */}
        {[0, 25, 50, 75, 100].map(pct => (
          <div key={pct} className="absolute top-0 bottom-0 flex items-end pb-0.5" style={{ left: `${pct}%` }}>
            <span className="text-[8px] font-mono text-white/60 ml-0.5">{formatMs(Math.round(totalMs * pct / 100))}</span>
          </div>
        ))}
      </div>

      {/* Scene table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="border-b border-border">
              {["#", "Title", "Start", "End", "Dur", "Shot", "Type", "Trans", "Imp"].map(h => (
                <th key={h} className="text-left text-muted-foreground font-normal pb-2 pr-4 last:pr-0">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {timeline.map((t, i) => (
              <tr key={i} className="border-b border-border/50 hover:bg-accent/20 transition-colors">
                <td className="py-2 pr-4 text-muted-foreground">{String(t.scene_number).padStart(2, '0')}</td>
                <td className="py-2 pr-4 text-foreground truncate max-w-[140px]">{t.scene_title}</td>
                <td className="py-2 pr-4 text-muted-foreground">{formatMs(t.start_time_ms)}</td>
                <td className="py-2 pr-4 text-muted-foreground">{formatMs(t.end_time_ms)}</td>
                <td className="py-2 pr-4 text-muted-foreground">{(t.duration_ms / 1000).toFixed(1)}s</td>
                <td className={`py-2 pr-4 ${SHOT_COLORS[t.shot_type] ?? 'text-muted-foreground'}`}>
                  {t.shot_type?.replace(/_/g, ' ')}
                </td>
                <td className={`py-2 pr-4 ${VISUAL_TYPE_COLORS[t.visual_type] ?? 'text-muted-foreground'}`}>
                  {t.visual_type?.replace(/_/g, ' ')}
                </td>
                <td className="py-2 pr-4 text-muted-foreground">
                  {TRANSITION_LABELS[t.transition_type ?? 'cut'] ?? 'CUT'}
                </td>
                <td className="py-2">
                  <div className="flex items-center gap-1.5">
                    <div className="w-12 h-1 rounded-full bg-border overflow-hidden">
                      <div className="h-full rounded-full bg-primary" style={{ width: `${((t.importance_score ?? 0.5) * 100).toFixed(0)}%` }} />
                    </div>
                    <span className="text-muted-foreground">{((t.importance_score ?? 0.5) * 100).toFixed(0)}%</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Production panel ──────────────────────────────────────────────────────────

function ProductionPanel({ sb }: { sb: StoryboardResult }) {
  if (sb.status !== 'completed') {
    return <div className="text-xs text-muted-foreground text-center py-12">Production metrics available after storyboard completes.</div>;
  }

  const visualCues = (sb.visualCues ?? []) as any[];
  const narrationTiming = (sb.narrationTiming ?? []) as any[];

  return (
    <div className="space-y-8">
      {/* Metrics overview */}
      <div className="grid grid-cols-2 gap-4">
        {[
          { label: "Scene Count", value: sb.sceneCount?.toLocaleString() ?? '—', sub: "total scenes" },
          { label: "Image Count", value: sb.imageCount?.toLocaleString() ?? '—', sub: "assets to generate" },
          { label: "Render Time", value: sb.estimatedRenderTimeMinutes ? `${sb.estimatedRenderTimeMinutes}min` : '—', sub: "estimated" },
          { label: "Est. Cost", value: sb.estimatedCostUsd != null ? `$${sb.estimatedCostUsd.toFixed(2)}` : '—', sub: "image generation" },
          { label: "Complexity", value: sb.editingComplexityScore != null ? `${(sb.editingComplexityScore * 100).toFixed(0)}%` : '—', sub: "editing difficulty" },
          { label: "Visual Pacing", value: sb.visualPacing?.replace(/_/g, ' ') ?? '—', sub: "pacing style" },
        ].map(({ label, value, sub }) => (
          <div key={label} className="p-3 rounded-md border border-border bg-card/30">
            <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">{label}</div>
            <div className="text-lg font-bold font-mono text-foreground">{value}</div>
            <div className="text-[10px] text-muted-foreground/60">{sub}</div>
          </div>
        ))}
      </div>

      {/* Complexity bar */}
      {sb.editingComplexityScore != null && (
        <div>
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Editing Complexity</div>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 rounded-full bg-border overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  sb.editingComplexityScore > 0.7 ? 'bg-red-500' :
                  sb.editingComplexityScore > 0.4 ? 'bg-amber-500' : 'bg-emerald-500'
                }`}
                style={{ width: `${(sb.editingComplexityScore * 100).toFixed(0)}%` }}
              />
            </div>
            <span className="text-xs font-mono text-muted-foreground w-12 text-right">
              {(sb.editingComplexityScore * 100).toFixed(0)}%
            </span>
          </div>
          <div className="flex justify-between text-[9px] font-mono text-muted-foreground mt-1">
            <span>Simple</span><span>Complex</span>
          </div>
        </div>
      )}

      {/* Visual cues */}
      {visualCues.length > 0 && (
        <div>
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-3">
            Visual Cues ({visualCues.length})
          </div>
          <div className="space-y-1 max-h-56 overflow-y-auto pr-1">
            {visualCues.slice(0, 50).map((c: any, i: number) => (
              <div key={i} className="flex items-center gap-3 text-xs font-mono py-1 border-b border-border/30">
                <span className="text-muted-foreground/50 w-14 shrink-0 text-right">{formatMs(c.time_ms)}</span>
                <span className={`text-[9px] font-bold uppercase px-1 rounded ${
                  c.cue_type === 'cut' ? 'text-red-400' :
                  c.cue_type === 'transition' ? 'text-amber-400' :
                  c.cue_type === 'graphic' ? 'text-purple-400' : 'text-muted-foreground'
                }`}>{c.cue_type}</span>
                <span className="text-muted-foreground truncate flex-1">{c.description}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Narration timing */}
      {narrationTiming.length > 0 && (
        <div>
          <div className="text-[10px] font-mono uppercase text-muted-foreground mb-3">
            Narration Timing ({narrationTiming.length} scenes)
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-border">
                  {["#", "Scene", "Start", "End", "WPM", "Words"].map(h => (
                    <th key={h} className="text-left text-muted-foreground font-normal pb-2 pr-4">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {narrationTiming.slice(0, 20).map((t: any, i: number) => (
                  <tr key={i} className="border-b border-border/50 hover:bg-accent/20">
                    <td className="py-1.5 pr-4 text-muted-foreground">{t.scene_number}</td>
                    <td className="py-1.5 pr-4 text-foreground truncate max-w-[120px]">{t.scene_title}</td>
                    <td className="py-1.5 pr-4 text-muted-foreground">{formatMs(t.start_ms)}</td>
                    <td className="py-1.5 pr-4 text-muted-foreground">{formatMs(t.end_ms)}</td>
                    <td className="py-1.5 pr-4 text-primary">{t.wpm}</td>
                    <td className="py-1.5 text-muted-foreground">{t.word_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Detail panel ──────────────────────────────────────────────────────────────

function StoryboardDetailPanel({ selectedId, onClose }: { selectedId: string; onClose: () => void }) {
  const { data: sb, isLoading } = useGetStoryboard(selectedId, {
    query: {
      enabled: !!selectedId,
      queryKey: getGetStoryboardQueryKey(selectedId),
      refetchInterval: (query: any) => {
        const d = query?.state?.data;
        return (d?.status === 'running' || d?.status === 'pending') ? 2000 : false;
      },
    },
  });

  const scenes = (sb?.scenes ?? []) as StoryboardScene[];
  const timeline = (sb?.sceneTimeline ?? []) as StoryboardSceneTimeline[];
  const isActive = sb?.status === 'pending' || sb?.status === 'running';
  const totalDurationMs = (sb?.totalDurationSeconds ?? 0) * 1000;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 p-6 border-b border-border shrink-0">
        <div className="flex-1 min-w-0">
          {isLoading ? <Skeleton className="h-5 w-3/4 mb-2" /> : (
            <>
              <h2 className="text-sm font-bold text-foreground leading-tight mb-2 line-clamp-2">
                {sb?.title ?? sb?.topic}
              </h2>
              <div className="flex items-center gap-2 flex-wrap">
                {sb?.status && <StatusBadge status={sb.status} />}
                {sb?.scriptStyle && (
                  <span className="text-[9px] font-mono font-bold uppercase px-1.5 py-0.5 rounded border border-border text-muted-foreground">
                    {sb.scriptStyle.replace('_', ' ')}
                  </span>
                )}
              </div>
            </>
          )}
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-foreground shrink-0">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Metrics bar */}
      {sb?.status === 'completed' && (
        <div className="flex items-center gap-2 flex-wrap px-6 py-3 border-b border-border bg-card/30 shrink-0">
          <MetricChip icon={Layers} label="SCENES" value={sb.sceneCount} className="border-border text-foreground" />
          <MetricChip icon={Image} label="IMAGES" value={sb.imageCount} className="border-border text-foreground" />
          <MetricChip icon={Timer} label="DUR" value={formatDuration(sb.totalDurationSeconds)} className="border-border text-foreground" />
          <MetricChip icon={DollarSign} label="COST" value={sb.estimatedCostUsd != null ? `$${sb.estimatedCostUsd.toFixed(2)}` : null} className="border-border text-foreground" />
          <MetricChip icon={Zap} label="COMPLEXITY" value={sb.editingComplexityScore != null ? `${(sb.editingComplexityScore * 100).toFixed(0)}%` : null} className="border-border text-foreground" />
        </div>
      )}

      {/* Running indicator */}
      {isActive && (
        <div className="flex items-center gap-3 px-6 py-3 border-b border-border bg-emerald-500/5 shrink-0">
          <RefreshCw className="w-3.5 h-3.5 text-emerald-500 animate-spin" />
          <span className="text-xs font-mono text-emerald-500">
            {sb?.status === 'pending' ? 'Job queued...' : 'Generating storyboard...'}
          </span>
        </div>
      )}

      {/* Content */}
      {!isLoading && sb && (
        <Tabs defaultValue="scenes" className="flex-1 flex flex-col min-h-0">
          <TabsList className="mx-6 mt-4 mb-0 shrink-0 justify-start bg-transparent border-b border-border rounded-none h-auto gap-0 p-0">
            {[
              { value: 'scenes', label: 'Scenes', icon: Clapperboard },
              { value: 'timeline', label: 'Timeline', icon: Layers },
              { value: 'production', label: 'Production', icon: Zap },
              { value: 'logs', label: 'Logs', icon: Eye },
            ].map(({ value, label, icon: Icon }) => (
              <TabsTrigger
                key={value}
                value={value}
                className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-4 pb-3 pt-0 text-xs font-mono font-medium gap-1.5"
              >
                <Icon className="w-3 h-3" /> {label}
              </TabsTrigger>
            ))}
          </TabsList>

          {/* Scenes tab */}
          <TabsContent value="scenes" className="flex-1 min-h-0 mt-0">
            <ScrollArea className="h-full">
              <div className="p-6 space-y-2">
                {(sb.status === 'pending' || sb.status === 'running') ? (
                  <div className="space-y-3">
                    {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
                  </div>
                ) : sb.status === 'failed' ? (
                  <div className="p-4 rounded-md border border-red-500/20 bg-red-500/5">
                    <p className="text-sm font-mono text-red-400">Storyboard generation failed.</p>
                    {sb.errorMessage && <p className="text-xs text-red-400/70 mt-1">{sb.errorMessage}</p>}
                  </div>
                ) : scenes.length === 0 ? (
                  <div className="text-center text-xs text-muted-foreground py-12">No scenes generated.</div>
                ) : (
                  scenes.map((scene, i) => <SceneCard key={scene.scene_number ?? i} scene={scene} index={i} />)
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          {/* Timeline tab */}
          <TabsContent value="timeline" className="flex-1 min-h-0 mt-0">
            <ScrollArea className="h-full">
              <div className="p-6">
                <TimelineView timeline={timeline} totalDurationMs={totalDurationMs} />
              </div>
            </ScrollArea>
          </TabsContent>

          {/* Production tab */}
          <TabsContent value="production" className="flex-1 min-h-0 mt-0">
            <ScrollArea className="h-full">
              <div className="p-6">
                <ProductionPanel sb={sb} />
              </div>
            </ScrollArea>
          </TabsContent>

          {/* Logs tab */}
          <TabsContent value="logs" className="flex-1 min-h-0 mt-0">
            <div className="p-6 h-full">
              <LogsTerminal logs={sb.logs ?? []} />
            </div>
          </TabsContent>
        </Tabs>
      )}

      {isLoading && (
        <div className="flex-1 p-6 space-y-4">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}
        </div>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function StoryboardsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: sbList, isLoading: listLoading, refetch } = useListStoryboards(
    {},
    { query: { queryKey: getListStoryboardsQueryKey({}), refetchInterval: 5000 } }
  );

  const startMutation = useStartStoryboard({
    mutation: {
      onSuccess: (data) => {
        queryClient.invalidateQueries({ queryKey: getListStoryboardsQueryKey() });
        setSelectedId(data.id);
        toast({ title: "Storyboard job started", description: `Generating storyboard for "${data.topic}"` });
      },
      onError: () => toast({ title: "Failed to start storyboard", variant: "destructive" }),
    },
  });

  const deleteMutation = useDeleteStoryboard({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListStoryboardsQueryKey() });
        setSelectedId(null);
        toast({ title: "Storyboard deleted" });
      },
    },
  });

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      topic: '',
      scriptStyle: 'educational',
      scriptTone: 'engaging',
      targetDurationMinutes: 10,
      providers: ['openai', 'claude'],
    },
  });

  const onSubmit = (values: z.infer<typeof formSchema>) => {
    startMutation.mutate({
      data: {
        topic: values.topic,
        scriptStyle: values.scriptStyle,
        scriptTone: values.scriptTone,
        targetDurationMinutes: values.targetDurationMinutes,
        providers: values.providers,
      },
    });
  };

  const storyboards: StoryboardResult[] = (sbList?.items ?? []) as StoryboardResult[];

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left column: form + list */}
      <div className="flex flex-col w-full md:w-[420px] shrink-0 border-r border-border overflow-hidden">
        {/* Form */}
        <div className="p-6 border-b border-border shrink-0">
          <h1 className="text-sm font-bold font-mono text-primary mb-4 flex items-center gap-2">
            <Film className="w-4 h-4" /> STORYBOARD_GENERATOR
          </h1>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3">
              <FormField control={form.control} name="topic" render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-[10px] font-mono uppercase text-muted-foreground">Topic</FormLabel>
                  <FormControl>
                    <Input placeholder="e.g. quantum computing, machine learning..." {...field} className="font-mono text-sm" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )} />

              <div className="grid grid-cols-2 gap-3">
                <FormField control={form.control} name="scriptStyle" render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-[10px] font-mono uppercase text-muted-foreground">Style</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl><SelectTrigger className="font-mono text-xs"><SelectValue /></SelectTrigger></FormControl>
                      <SelectContent>{STYLES.map(s => <SelectItem key={s.value} value={s.value} className="font-mono text-xs">{s.label}</SelectItem>)}</SelectContent>
                    </Select>
                  </FormItem>
                )} />

                <FormField control={form.control} name="scriptTone" render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-[10px] font-mono uppercase text-muted-foreground">Tone</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl><SelectTrigger className="font-mono text-xs"><SelectValue /></SelectTrigger></FormControl>
                      <SelectContent>{TONES.map(t => <SelectItem key={t.value} value={t.value} className="font-mono text-xs">{t.label}</SelectItem>)}</SelectContent>
                    </Select>
                  </FormItem>
                )} />
              </div>

              <FormField control={form.control} name="targetDurationMinutes" render={({ field }) => (
                <FormItem>
                  <FormLabel className="text-[10px] font-mono uppercase text-muted-foreground">Target Duration (minutes)</FormLabel>
                  <FormControl><Input type="number" min={1} max={120} {...field} className="font-mono text-sm" /></FormControl>
                  <FormMessage />
                </FormItem>
              )} />

              <FormField control={form.control} name="providers" render={() => (
                <FormItem>
                  <FormLabel className="text-[10px] font-mono uppercase text-muted-foreground">Providers</FormLabel>
                  <div className="grid grid-cols-2 gap-2">
                    {AVAILABLE_PROVIDERS.map(p => (
                      <FormField key={p.id} control={form.control} name="providers" render={({ field }) => (
                        <FormItem className="flex flex-row items-center space-x-2 space-y-0">
                          <FormControl>
                            <Checkbox
                              checked={field.value?.includes(p.id)}
                              onCheckedChange={(checked) => {
                                const cur = field.value ?? [];
                                field.onChange(checked ? [...cur, p.id] : cur.filter((v: string) => v !== p.id));
                              }}
                            />
                          </FormControl>
                          <FormLabel className="text-xs font-mono font-normal cursor-pointer">{p.label}</FormLabel>
                        </FormItem>
                      )} />
                    ))}
                  </div>
                  <FormMessage />
                </FormItem>
              )} />

              <Button type="submit" disabled={startMutation.isPending} className="w-full font-mono text-xs">
                {startMutation.isPending ? (
                  <><RefreshCw className="w-3 h-3 mr-2 animate-spin" /> Starting...</>
                ) : (
                  <><Play className="w-3 h-3 mr-2" /> Generate Storyboard</>
                )}
              </Button>
            </form>
          </Form>
        </div>

        {/* List */}
        <div className="flex-1 overflow-hidden flex flex-col">
          <div className="px-6 py-3 border-b border-border flex items-center justify-between shrink-0">
            <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">
              Storyboards ({storyboards.length})
            </span>
            <button onClick={() => refetch()} className="text-muted-foreground hover:text-foreground transition-colors">
              <RefreshCw className="w-3 h-3" />
            </button>
          </div>

          <ScrollArea className="flex-1">
            {listLoading ? (
              <div className="p-4 space-y-3">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}</div>
            ) : storyboards.length === 0 ? (
              <div className="p-8 text-center text-xs text-muted-foreground font-mono">
                No storyboards yet. Generate your first one above.
              </div>
            ) : (
              <div className="divide-y divide-border">
                {storyboards.map(sb => (
                  <button
                    key={sb.id}
                    onClick={() => setSelectedId(sb.id === selectedId ? null : sb.id)}
                    className={cn(
                      "w-full text-left px-6 py-4 flex items-start gap-3 hover:bg-accent/30 transition-colors",
                      selectedId === sb.id && "bg-accent/50"
                    )}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <StatusBadge status={sb.status} />
                        {sb.scriptStyle && (
                          <span className="text-[9px] font-mono font-bold uppercase px-1 py-0.5 rounded border border-border text-muted-foreground">
                            {sb.scriptStyle.replace('_', ' ')}
                          </span>
                        )}
                      </div>
                      <div className="text-xs font-medium text-foreground truncate mb-1">{sb.topic}</div>
                      <div className="text-[10px] font-mono text-muted-foreground flex items-center gap-2">
                        <span>{format(new Date(sb.createdAt), 'MMM d, HH:mm')}</span>
                        {sb.sceneCount && <span>· {sb.sceneCount} scenes</span>}
                        {sb.totalDurationSeconds && <span>· {formatDuration(sb.totalDurationSeconds)}</span>}
                      </div>
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteMutation.mutate({ id: sb.id }); }}
                      className="p-1 rounded hover:bg-destructive/20 hover:text-destructive transition-colors text-muted-foreground shrink-0"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </button>
                ))}
              </div>
            )}
          </ScrollArea>
        </div>
      </div>

      {/* Right detail panel */}
      <AnimatePresence mode="wait">
        {selectedId ? (
          <motion.div
            key={selectedId}
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 24 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="flex-1 overflow-hidden hidden md:flex flex-col bg-background"
          >
            <StoryboardDetailPanel selectedId={selectedId} onClose={() => setSelectedId(null)} />
          </motion.div>
        ) : (
          <motion.div
            key="empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex-1 hidden md:flex flex-col items-center justify-center text-center gap-4 p-12"
          >
            <div className="w-14 h-14 rounded-full border border-border flex items-center justify-center">
              <Film className="w-7 h-7 text-muted-foreground/40" />
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Select a storyboard to view scenes</p>
              <p className="text-xs text-muted-foreground/60 mt-1 font-mono">Or generate a new storyboard using the form</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
