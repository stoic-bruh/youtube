import React, { useState, useEffect, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { format } from 'date-fns';
import { motion, AnimatePresence } from 'framer-motion';
import { useQueryClient } from '@tanstack/react-query';
import {
  useListScripts, getListScriptsQueryKey,
  useStartScript, useDeleteScript, useGetScript, getGetScriptQueryKey,
  ScriptResult, ScriptSection,
} from '@workspace/api-client-react';

import {
  ScrollText, Play, RefreshCw, CheckCircle2, Clock, AlertCircle,
  Trash2, X, FileText, Mic, Eye, ChevronRight, BookOpen, Zap,
  Timer, Film, Type, Volume2,
} from 'lucide-react';

import { cn } from "@/lib/utils";
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/hooks/use-toast';
import { Skeleton } from '@/components/ui/skeleton';

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

const STYLE_COLORS: Record<string, string> = {
  educational: 'text-blue-400 border-blue-400/20 bg-blue-400/5',
  documentary: 'text-amber-400 border-amber-400/20 bg-amber-400/5',
  storytelling: 'text-purple-400 border-purple-400/20 bg-purple-400/5',
  tutorial: 'text-emerald-400 border-emerald-400/20 bg-emerald-400/5',
  news: 'text-red-400 border-red-400/20 bg-red-400/5',
  long_form: 'text-indigo-400 border-indigo-400/20 bg-indigo-400/5',
  shorts: 'text-pink-400 border-pink-400/20 bg-pink-400/5',
};

// ── Form schema ─────────────────────────────────────────────────────────────────

const formSchema = z.object({
  topic: z.string().min(3, "Topic must be at least 3 characters"),
  style: z.string().optional(),
  tone: z.string().optional(),
  targetDurationMinutes: z.coerce.number().int().min(1).max(120).optional(),
  providers: z.array(z.string()).min(1, "Select at least one provider").default(['openai', 'claude']),
});

// ── Helper components ──────────────────────────────────────────────────────────

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

function MetricBadge({ icon: Icon, label, value, className = "" }: {
  icon: any; label: string; value: string | number | undefined | null; className?: string;
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

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return '—';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function LogsTerminal({ logs, ttyLabel }: { logs: string[]; ttyLabel?: string }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [logs]);

  if (!logs || logs.length === 0) {
    return (
      <div className="p-4 text-xs font-mono text-muted-foreground h-full flex items-center justify-center">
        AWAITING TELEMETRY...
      </div>
    );
  }

  return (
    <div className="bg-black text-gray-300 font-mono text-xs rounded-md overflow-hidden flex flex-col h-full border border-gray-800">
      <div className="bg-gray-900 px-3 py-2 flex items-center gap-2 border-b border-gray-800 shrink-0">
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500/80" />
          <div className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
        </div>
        <span className="text-gray-500 text-[10px] ml-2 tracking-widest">{ttyLabel ?? 'SCRIPT_PROCESS_TTY'}</span>
      </div>
      <div ref={scrollRef} className="p-4 overflow-y-auto flex-1 space-y-1">
        {logs.map((log, i) => {
          let colorClass = "text-gray-300";
          if (log.includes("ERROR")) colorClass = "text-red-400";
          else if (log.includes("WARN")) colorClass = "text-amber-400";
          else if (log.includes("INFO")) colorClass = "text-emerald-400";
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

function ScriptTextBlock({ label, text, accent = false }: {
  label: string; text: string | null | undefined; accent?: boolean;
}) {
  if (!text) return null;
  return (
    <div className="mb-6">
      <div className={`text-[10px] font-mono font-bold uppercase tracking-widest mb-2 ${accent ? 'text-primary' : 'text-muted-foreground'}`}>
        {label}
      </div>
      <div className={`text-sm leading-relaxed text-card-foreground p-4 rounded-md border ${accent ? 'border-primary/20 bg-primary/5' : 'border-border bg-card/50'}`}>
        {text}
      </div>
    </div>
  );
}

function SectionCard({ section, index }: { section: ScriptSection; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const typeColors: Record<string, string> = {
    main_point: 'text-blue-400 border-blue-400/20',
    example: 'text-emerald-400 border-emerald-400/20',
    analogy: 'text-purple-400 border-purple-400/20',
    transition: 'text-muted-foreground border-border',
    hook: 'text-amber-400 border-amber-400/20',
    call_to_action: 'text-red-400 border-red-400/20',
    outro: 'text-indigo-400 border-indigo-400/20',
  };
  const typeClass = typeColors[section.sectionType] ?? typeColors.main_point;
  const durationText = section.durationSeconds ? formatDuration(Math.round(section.durationSeconds)) : null;

  return (
    <div className="border border-border rounded-md overflow-hidden">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-start gap-3 p-3 text-left hover:bg-accent/30 transition-colors"
      >
        <div className="mt-0.5 text-[10px] font-mono font-bold text-muted-foreground w-6 shrink-0 text-right">
          {String(index + 1).padStart(2, '0')}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`text-[9px] font-mono font-bold uppercase px-1.5 py-0.5 rounded border ${typeClass}`}>
              {section.sectionType.replace('_', ' ')}
            </span>
            <span className="text-sm font-medium text-foreground truncate">{section.title}</span>
          </div>
          <div className="flex items-center gap-3 text-[10px] font-mono text-muted-foreground">
            {section.wordCount !== undefined && section.wordCount > 0 && (
              <span>{section.wordCount} words</span>
            )}
            {durationText && <span>~{durationText}</span>}
          </div>
        </div>
        <ChevronRight className={`w-4 h-4 text-muted-foreground shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`} />
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="border-t border-border p-4 space-y-3 bg-card/30">
              {section.transitionIn && (
                <div className="text-[10px] font-mono text-muted-foreground italic border-l-2 border-primary/30 pl-3">
                  ↑ {section.transitionIn}
                </div>
              )}
              <p className="text-sm text-card-foreground leading-relaxed">{section.content}</p>
              {section.transitionOut && (
                <div className="text-[10px] font-mono text-muted-foreground italic border-l-2 border-primary/30 pl-3">
                  ↓ {section.transitionOut}
                </div>
              )}
              {section.visualSuggestion && (
                <div className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground">
                  <Film className="w-3 h-3" />
                  <span className="opacity-60">VISUAL:</span>
                  <span>{section.visualSuggestion}</span>
                </div>
              )}
              {section.storytellingNotes && (
                <div className="flex items-start gap-2 text-[10px] font-mono text-muted-foreground">
                  <Mic className="w-3 h-3 mt-0.5 shrink-0" />
                  <span><span className="opacity-60">DIRECTOR: </span>{section.storytellingNotes}</span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function NarrationTimingTable({ timing }: { timing: object[] | undefined }) {
  if (!timing || timing.length === 0) return (
    <div className="text-xs text-muted-foreground text-center py-8">No timing data yet</div>
  );
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left text-muted-foreground font-normal pb-2 pr-4">Section</th>
            <th className="text-right text-muted-foreground font-normal pb-2 pr-4">Start</th>
            <th className="text-right text-muted-foreground font-normal pb-2 pr-4">End</th>
            <th className="text-right text-muted-foreground font-normal pb-2 pr-4">WPM</th>
            <th className="text-right text-muted-foreground font-normal pb-2">Words</th>
          </tr>
        </thead>
        <tbody>
          {timing.map((t: any, i: number) => (
            <tr key={i} className="border-b border-border/50 hover:bg-accent/20 transition-colors">
              <td className="py-2 pr-4 text-foreground truncate max-w-[180px]">{t.sectionTitle}</td>
              <td className="py-2 pr-4 text-right text-muted-foreground">{(t.startMs / 1000).toFixed(1)}s</td>
              <td className="py-2 pr-4 text-right text-muted-foreground">{(t.endMs / 1000).toFixed(1)}s</td>
              <td className="py-2 pr-4 text-right text-primary">{t.wpm}</td>
              <td className="py-2 text-right text-muted-foreground">{t.wordCount}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function VisualCueList({ cues }: { cues: object[] | undefined }) {
  if (!cues || cues.length === 0) return (
    <div className="text-xs text-muted-foreground text-center py-8">No visual cues yet</div>
  );
  const cueTypeColors: Record<string, string> = {
    b_roll: 'text-blue-400', graphic: 'text-purple-400', title_card: 'text-amber-400',
    zoom: 'text-emerald-400', lower_third: 'text-cyan-400', cut: 'text-red-400',
  };
  return (
    <div className="space-y-2">
      {cues.map((c: any, i: number) => (
        <div key={i} className="flex items-start gap-3 p-2 rounded border border-border/50 hover:bg-accent/20 transition-colors">
          <div className="text-[9px] font-mono font-bold uppercase mt-0.5 shrink-0 w-16 text-right opacity-50">
            {(c.timeMs / 1000).toFixed(1)}s
          </div>
          <div className={`text-[9px] font-mono font-bold uppercase shrink-0 ${cueTypeColors[c.cueType] ?? 'text-muted-foreground'}`}>
            {c.cueType}
          </div>
          <div className="text-xs text-muted-foreground flex-1">{c.description}</div>
          <div className="text-[9px] font-mono text-muted-foreground shrink-0">{(c.durationMs / 1000).toFixed(1)}s</div>
        </div>
      ))}
    </div>
  );
}

function PronunciationList({ hints }: { hints: object[] | undefined }) {
  if (!hints || hints.length === 0) return null;
  return (
    <div className="space-y-2">
      <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-3">
        Pronunciation Guide
      </div>
      {hints.map((h: any, i: number) => (
        <div key={i} className="flex items-center gap-3 text-xs">
          <span className="font-medium text-foreground w-28 shrink-0">{h.word}</span>
          <span className="font-mono text-primary">/{h.phonetic}/</span>
          {h.note && <span className="text-muted-foreground text-[10px]">{h.note}</span>}
        </div>
      ))}
    </div>
  );
}

// ── Detail panel ───────────────────────────────────────────────────────────────

function ScriptDetailPanel({ selectedId, onClose }: { selectedId: string; onClose: () => void }) {
  const { data: script, isLoading, isError } = useGetScript(selectedId, {
    query: {
      enabled: !!selectedId,
      queryKey: getGetScriptQueryKey(selectedId),
      refetchInterval: (query: any) => {
        const d = query?.state?.data;
        return (d?.status === 'running' || d?.status === 'pending') ? 2000 : false;
      },
    },
  });

  const sections: ScriptSection[] = (script?.sections as ScriptSection[]) ?? [];
  const isActive = script?.status === 'pending' || script?.status === 'running';

  const wordCount = script?.wordCount;
  const estDur = script?.estimatedDurationSeconds;
  const readTime = script?.readingTimeSeconds;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 p-6 border-b border-border shrink-0">
        <div className="flex-1 min-w-0">
          {isLoading ? (
            <Skeleton className="h-6 w-3/4 mb-2" />
          ) : (
            <>
              <h2 className="text-sm font-bold text-foreground leading-tight mb-2 line-clamp-2">
                {script?.title ?? script?.topic}
              </h2>
              <div className="flex items-center gap-2 flex-wrap">
                {script?.status && <StatusBadge status={script.status} />}
                {script?.style && (
                  <span className={`text-[9px] font-mono font-bold uppercase px-1.5 py-0.5 rounded border ${STYLE_COLORS[script.style] ?? 'text-muted-foreground border-border'}`}>
                    {script.style.replace('_', ' ')}
                  </span>
                )}
              </div>
            </>
          )}
        </div>
        <button onClick={onClose} className="p-1 rounded hover:bg-accent transition-colors text-muted-foreground hover:text-foreground shrink-0">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Metrics bar */}
      {script?.status === 'completed' && (
        <div className="flex items-center gap-2 flex-wrap px-6 py-3 border-b border-border bg-card/30 shrink-0">
          <MetricBadge icon={Type} label="WORDS" value={wordCount?.toLocaleString()} className="border-border text-foreground" />
          <MetricBadge icon={Timer} label="EST." value={formatDuration(estDur)} className="border-border text-foreground" />
          <MetricBadge icon={BookOpen} label="READ" value={formatDuration(readTime)} className="border-border text-foreground" />
          <MetricBadge icon={Film} label="SCENES" value={script.sceneCount} className="border-border text-foreground" />
          <MetricBadge icon={Zap} label="WPM" value={script.pacingWpm} className="border-border text-foreground" />
        </div>
      )}

      {/* Active spinner */}
      {isActive && (
        <div className="flex items-center gap-3 px-6 py-3 border-b border-border bg-emerald-500/5 shrink-0">
          <RefreshCw className="w-3.5 h-3.5 text-emerald-500 animate-spin" />
          <span className="text-xs font-mono text-emerald-500">
            {script?.status === 'pending' ? 'Script job queued...' : 'Generating script...'}
          </span>
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="p-6 text-sm text-red-400 font-mono">Error loading script data.</div>
      )}

      {/* Content tabs */}
      {!isLoading && script && (
        <Tabs defaultValue="script" className="flex-1 flex flex-col min-h-0">
          <TabsList className="mx-6 mt-4 mb-0 shrink-0 justify-start bg-transparent border-b border-border rounded-none h-auto gap-0 p-0">
            {[
              { value: 'script', label: 'Script', icon: FileText },
              { value: 'production', label: 'Production', icon: Film },
              { value: 'logs', label: 'Logs', icon: Volume2 },
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

          {/* Script tab */}
          <TabsContent value="script" className="flex-1 min-h-0 mt-0">
            <ScrollArea className="h-full">
              <div className="p-6 space-y-2">
                {script.status === 'pending' || script.status === 'running' ? (
                  <div className="space-y-4">
                    {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}
                  </div>
                ) : script.status === 'failed' ? (
                  <div className="p-4 rounded-md border border-red-500/20 bg-red-500/5">
                    <p className="text-sm font-mono text-red-400">Script generation failed.</p>
                    {script.errorMessage && (
                      <p className="text-xs text-red-400/70 mt-1">{script.errorMessage}</p>
                    )}
                  </div>
                ) : (
                  <>
                    <ScriptTextBlock label="Hook" text={script.hook} accent />
                    <ScriptTextBlock label="Introduction" text={script.introduction} />

                    {sections.length > 0 && (
                      <div className="mb-6">
                        <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-3">
                          Main Sections
                        </div>
                        <div className="space-y-2">
                          {sections.map((s, i) => (
                            <SectionCard key={i} section={s} index={i} />
                          ))}
                        </div>
                      </div>
                    )}

                    <ScriptTextBlock label="Call to Action" text={script.callToAction} />
                    <ScriptTextBlock label="Outro" text={script.outro} />
                  </>
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          {/* Production tab */}
          <TabsContent value="production" className="flex-1 min-h-0 mt-0">
            <ScrollArea className="h-full">
              <div className="p-6 space-y-8">
                {script.status !== 'completed' ? (
                  <div className="text-xs text-muted-foreground text-center py-12">
                    Production metadata available after script completes.
                  </div>
                ) : (
                  <>
                    <div>
                      <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-4">
                        Narration Timing
                      </div>
                      <NarrationTimingTable timing={script.narrationTiming as object[] | undefined} />
                    </div>

                    <div>
                      <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-4">
                        Visual Cues
                      </div>
                      <VisualCueList cues={script.visualCues as object[] | undefined} />
                    </div>

                    {(script.pronunciationHints as object[] | undefined)?.length > 0 && (
                      <PronunciationList hints={script.pronunciationHints as object[] | undefined} />
                    )}

                    {(script.emphasisMarkers as object[] | undefined)?.length > 0 && (
                      <div>
                        <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-3">
                          Emphasis Markers ({(script.emphasisMarkers as object[]).length})
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {(script.emphasisMarkers as any[]).map((e, i) => (
                            <span key={i} className="text-xs font-mono px-2 py-1 rounded border border-primary/20 bg-primary/5 text-primary">
                              {e.text} <span className="opacity-50 text-[9px]">[{e.emphasisType}]</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {(script.pauses as object[] | undefined)?.length > 0 && (
                      <div>
                        <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-3">
                          Strategic Pauses ({(script.pauses as object[]).length})
                        </div>
                        <div className="space-y-2">
                          {(script.pauses as any[]).map((p, i) => (
                            <div key={i} className="flex items-center gap-3 text-xs font-mono">
                              <span className={`px-1.5 py-0.5 rounded text-[9px] uppercase font-bold ${
                                p.pauseType === 'dramatic' ? 'text-red-400 border border-red-400/20' :
                                p.pauseType === 'long' ? 'text-amber-400 border border-amber-400/20' :
                                'text-muted-foreground border border-border'
                              }`}>{p.pauseType}</span>
                              <span className="text-muted-foreground">{p.durationMs}ms</span>
                              <span className="text-muted-foreground/60 italic text-[10px]">{p.context}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          {/* Logs tab */}
          <TabsContent value="logs" className="flex-1 min-h-0 mt-0">
            <div className="p-6 h-full">
              <LogsTerminal logs={script.logs ?? []} />
            </div>
          </TabsContent>
        </Tabs>
      )}

      {isLoading && (
        <div className="flex-1 p-6 space-y-4">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}
        </div>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function ScriptsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: scriptList, isLoading: listLoading, refetch } = useListScripts(
    {},
    { query: { queryKey: getListScriptsQueryKey({}), refetchInterval: 5000 } }
  );

  const startMutation = useStartScript({
    mutation: {
      onSuccess: (data) => {
        queryClient.invalidateQueries({ queryKey: getListScriptsQueryKey() });
        setSelectedId(data.id);
        toast({ title: "Script job started", description: `Generating script for "${data.topic}"` });
      },
      onError: () => toast({ title: "Failed to start script", variant: "destructive" }),
    },
  });

  const deleteMutation = useDeleteScript({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListScriptsQueryKey() });
        if (selectedId) setSelectedId(null);
        toast({ title: "Script deleted" });
      },
    },
  });

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      topic: '',
      style: 'educational',
      tone: 'engaging',
      targetDurationMinutes: 10,
      providers: ['openai', 'claude'],
    },
  });

  const onSubmit = (values: z.infer<typeof formSchema>) => {
    startMutation.mutate({
      data: {
        topic: values.topic,
        style: values.style,
        tone: values.tone,
        targetDurationMinutes: values.targetDurationMinutes,
        providers: values.providers,
      },
    });
  };

  const scripts: ScriptResult[] = (scriptList?.items as ScriptResult[]) ?? [];

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left column: form + list */}
      <div className="flex flex-col w-full md:w-[420px] shrink-0 border-r border-border overflow-hidden">
        {/* Form */}
        <div className="p-6 border-b border-border shrink-0">
          <h1 className="text-sm font-bold font-mono text-primary mb-4 flex items-center gap-2">
            <ScrollText className="w-4 h-4" /> SCRIPT_GENERATOR
          </h1>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3">
              <FormField
                control={form.control}
                name="topic"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-[10px] font-mono uppercase text-muted-foreground">Topic</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. quantum computing, machine learning..." {...field} className="font-mono text-sm" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-2 gap-3">
                <FormField
                  control={form.control}
                  name="style"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-[10px] font-mono uppercase text-muted-foreground">Style</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger className="font-mono text-xs">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {STYLES.map(s => (
                            <SelectItem key={s.value} value={s.value} className="font-mono text-xs">{s.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="tone"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-[10px] font-mono uppercase text-muted-foreground">Tone</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger className="font-mono text-xs">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {TONES.map(t => (
                            <SelectItem key={t.value} value={t.value} className="font-mono text-xs">{t.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="targetDurationMinutes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className="text-[10px] font-mono uppercase text-muted-foreground">
                      Target Duration (minutes)
                    </FormLabel>
                    <FormControl>
                      <Input type="number" min={1} max={120} {...field} className="font-mono text-sm" />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="providers"
                render={() => (
                  <FormItem>
                    <FormLabel className="text-[10px] font-mono uppercase text-muted-foreground">Providers</FormLabel>
                    <div className="grid grid-cols-2 gap-2">
                      {AVAILABLE_PROVIDERS.map(p => (
                        <FormField
                          key={p.id}
                          control={form.control}
                          name="providers"
                          render={({ field }) => (
                            <FormItem className="flex flex-row items-center space-x-2 space-y-0">
                              <FormControl>
                                <Checkbox
                                  checked={field.value?.includes(p.id)}
                                  onCheckedChange={(checked) => {
                                    const current = field.value ?? [];
                                    field.onChange(
                                      checked ? [...current, p.id] : current.filter((v: string) => v !== p.id)
                                    );
                                  }}
                                />
                              </FormControl>
                              <FormLabel className="text-xs font-mono font-normal cursor-pointer">{p.label}</FormLabel>
                            </FormItem>
                          )}
                        />
                      ))}
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Button
                type="submit"
                disabled={startMutation.isPending}
                className="w-full font-mono text-xs"
              >
                {startMutation.isPending ? (
                  <><RefreshCw className="w-3 h-3 mr-2 animate-spin" /> Starting...</>
                ) : (
                  <><Play className="w-3 h-3 mr-2" /> Generate Script</>
                )}
              </Button>
            </form>
          </Form>
        </div>

        {/* Script list */}
        <div className="flex-1 overflow-hidden flex flex-col">
          <div className="px-6 py-3 border-b border-border flex items-center justify-between shrink-0">
            <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-widest">
              Scripts ({scripts.length})
            </span>
            <button onClick={() => refetch()} className="text-muted-foreground hover:text-foreground transition-colors">
              <RefreshCw className="w-3 h-3" />
            </button>
          </div>

          <ScrollArea className="flex-1">
            {listLoading ? (
              <div className="p-4 space-y-3">
                {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
              </div>
            ) : scripts.length === 0 ? (
              <div className="p-8 text-center text-xs text-muted-foreground font-mono">
                No scripts yet. Generate your first one above.
              </div>
            ) : (
              <div className="divide-y divide-border">
                {scripts.map((script) => (
                  <button
                    key={script.id}
                    onClick={() => setSelectedId(script.id === selectedId ? null : script.id)}
                    className={cn(
                      "w-full text-left px-6 py-4 flex items-start gap-3 hover:bg-accent/30 transition-colors",
                      selectedId === script.id && "bg-accent/50"
                    )}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <StatusBadge status={script.status} />
                        {script.style && (
                          <span className={`text-[9px] font-mono font-bold uppercase px-1 py-0.5 rounded border ${STYLE_COLORS[script.style] ?? ''}`}>
                            {script.style.replace('_', ' ')}
                          </span>
                        )}
                      </div>
                      <div className="text-xs font-medium text-foreground truncate mb-1">
                        {script.topic}
                      </div>
                      <div className="text-[10px] font-mono text-muted-foreground flex items-center gap-2">
                        <span>{format(new Date(script.createdAt), 'MMM d, HH:mm')}</span>
                        {script.wordCount && <span>· {script.wordCount.toLocaleString()} words</span>}
                        {script.estimatedDurationSeconds && (
                          <span>· ~{formatDuration(script.estimatedDurationSeconds)}</span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteMutation.mutate({ id: script.id });
                      }}
                      className="p-1 rounded hover:bg-destructive/20 hover:text-destructive transition-colors text-muted-foreground opacity-0 group-hover:opacity-100 shrink-0"
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

      {/* Right panel: detail */}
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
            <ScriptDetailPanel selectedId={selectedId} onClose={() => setSelectedId(null)} />
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
              <ScrollText className="w-7 h-7 text-muted-foreground/40" />
            </div>
            <div>
              <p className="text-sm font-medium text-muted-foreground">Select a script to view details</p>
              <p className="text-xs text-muted-foreground/60 mt-1 font-mono">
                Or generate a new script using the form
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
