import React, { useState, useEffect, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { format } from 'date-fns';
import { motion, AnimatePresence } from 'framer-motion';
import { useQueryClient } from '@tanstack/react-query';
import { 
  useListResearch, getListResearchQueryKey,
  useStartResearch, useDeleteResearch, useGetResearch, getGetResearchQueryKey,
  ResearchResult, ResearchSection, ResearchReference, ResearchKeyword
} from '@workspace/api-client-react';

import { 
  Search, Play, RefreshCw, CheckCircle2, Clock, AlertCircle, Database, 
  Trash2, X, FileText, Fingerprint, BookOpen, HelpCircle
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
import { Progress } from '@/components/ui/progress';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { useToast } from '@/hooks/use-toast';
import { Skeleton } from '@/components/ui/skeleton';

// Constants
const AVAILABLE_PROVIDERS = [
  { id: 'openai', label: 'OpenAI' },
  { id: 'gemini', label: 'Gemini' },
  { id: 'claude', label: 'Claude' },
  { id: 'openrouter', label: 'OpenRouter' },
  { id: 'perplexity', label: 'Perplexity' },
  { id: 'wikipedia', label: 'Wikipedia' },
  { id: 'duckduckgo', label: 'DuckDuckGo' },
  { id: 'google_search', label: 'Google Search' },
];

const STYLES = ['educational', 'entertaining', 'documentary', 'how-to'];
const TONES = ['engaging', 'authoritative', 'casual', 'inspirational'];

const formSchema = z.object({
  topic: z.string().min(1, "Topic is required"),
  targetAudience: z.string().optional(),
  videoLengthMinutes: z.coerce.number().optional(),
  language: z.string().optional(),
  style: z.string().optional(),
  tone: z.string().optional(),
  providers: z.array(z.string()).default([]),
});

// Components
function CircularProgress({ value, size = 40, strokeWidth = 4 }: { value: number, size?: number, strokeWidth?: number }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg className="transform -rotate-90 w-full h-full">
        <circle
          className="text-muted/20"
          strokeWidth={strokeWidth}
          stroke="currentColor"
          fill="transparent"
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
        <circle
          className="text-primary transition-all duration-1000 ease-out"
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          stroke="currentColor"
          fill="transparent"
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
      </svg>
      <div className="absolute flex items-center justify-center text-[10px] font-mono font-bold text-foreground">
        {Math.round(value)}%
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string, className: string, icon: any }> = {
    pending: { label: 'PENDING', className: 'bg-status-queued text-amber-500 border-amber-500/20', icon: Clock },
    running: { label: 'RUNNING', className: 'bg-status-running text-emerald-500 border-emerald-500/20 animate-pulse-running', icon: RefreshCw },
    completed: { label: 'COMPLETED', className: 'bg-status-completed text-blue-500 border-blue-500/20', icon: CheckCircle2 },
    failed: { label: 'FAILED', className: 'bg-status-failed text-red-500 border-red-500/20', icon: AlertCircle },
    cached: { label: 'CACHED', className: 'bg-status-draft text-gray-400 border-gray-400/20', icon: Database },
  };

  const c = config[status] || config.pending;
  const Icon = c.icon;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${c.className}`}>
      <Icon className="w-3 h-3" />
      {c.label}
    </span>
  );
}

function KeywordChip({ keyword }: { keyword: ResearchKeyword }) {
  const { term, relevance, searchVolume, difficulty } = keyword;
  const hue = 220; 
  const saturation = 50 + (relevance * 50); 
  const lightness = 20 + (relevance * 40); 
  
  return (
    <div 
      className="group relative flex items-center px-3 py-1 rounded-full text-xs font-medium border cursor-default transition-all"
      style={{
        backgroundColor: `hsl(${hue} ${saturation}% ${lightness}% / 0.1)`,
        borderColor: `hsl(${hue} ${saturation}% ${lightness}% / 0.2)`,
        color: `hsl(${hue} ${saturation}% 80%)`,
      }}
    >
      {term}
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 p-2 bg-popover border border-border rounded shadow-xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 text-[10px] font-mono text-muted-foreground space-y-1">
        <div className="flex justify-between">
          <span>RELEVANCE:</span>
          <span className="text-primary">{(relevance * 100).toFixed(0)}%</span>
        </div>
        {searchVolume !== undefined && searchVolume !== null && (
          <div className="flex justify-between">
            <span>VOLUME:</span>
            <span className="text-primary">{searchVolume}</span>
          </div>
        )}
        {difficulty && (
          <div className="flex justify-between">
            <span>DIFFICULTY:</span>
            <span className="text-primary">{difficulty}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function ReferenceCard({ reference }: { reference: ResearchReference }) {
  return (
    <a 
      href={reference.url} 
      target="_blank" 
      rel="noopener noreferrer"
      className="block group bg-card hover:bg-accent/50 border border-border p-4 rounded-md transition-all"
    >
      <div className="flex items-start justify-between gap-4 mb-2">
        <div className="flex-1">
          <h4 className="text-sm font-medium text-foreground group-hover:text-primary transition-colors line-clamp-2 leading-tight">
            {reference.title}
          </h4>
          <div className="flex items-center gap-2 mt-1.5 text-xs text-muted-foreground font-mono">
            <Badge variant="secondary" className="text-[9px] px-1.5 py-0 h-4 uppercase">
              {reference.sourceType}
            </Badge>
            {reference.provider && <span className="opacity-50">via {reference.provider}</span>}
          </div>
        </div>
        <div className="w-16 shrink-0 flex flex-col items-end gap-1">
          <div className="text-[10px] font-mono text-muted-foreground">CREDIBILITY</div>
          <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
            <div 
              className="h-full bg-primary" 
              style={{ width: `${reference.credibilityScore * 100}%` }} 
            />
          </div>
        </div>
      </div>
      {reference.snippet && (
        <p className="text-xs text-muted-foreground mt-2 line-clamp-2 opacity-80 leading-relaxed italic">
          "{reference.snippet}"
        </p>
      )}
    </a>
  );
}

function SectionRenderer({ section }: { section: ResearchSection }) {
  const { sectionType, title, content, items } = section;
  
  if (sectionType === 'summary') return null; 

  if (sectionType === 'timeline') {
    return (
      <section className="mb-8">
        <h3 className="text-sm font-mono font-bold text-primary mb-4 uppercase tracking-wider">{title}</h3>
        <div className="space-y-4 relative before:absolute before:inset-0 before:ml-2.5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-border">
          {items?.map((item, i) => {
            const parts = item.split(':');
            const date = parts[0];
            const text = parts.slice(1).join(':').trim() || item;
            return (
              <div key={i} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
                <div className="flex items-center justify-center w-5 h-5 rounded-full border border-border bg-card shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 z-10">
                  <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                </div>
                <div className="w-[calc(100%-2.5rem)] md:w-[calc(50%-1.5rem)] p-4 rounded-md border border-border bg-card/50">
                  <div className="text-xs font-mono font-bold text-primary mb-1">{date}</div>
                  <div className="text-sm text-card-foreground leading-relaxed">{text}</div>
                </div>
              </div>
            );
          })}
        </div>
      </section>
    );
  }

  if (sectionType === 'entity') {
    return (
      <section className="mb-8">
        <h3 className="text-sm font-mono font-bold text-primary mb-3 uppercase tracking-wider flex items-center gap-2">
          <Fingerprint className="w-4 h-4" /> {title}
        </h3>
        <div className="flex flex-wrap gap-2">
          {items?.map((item, i) => (
            <Badge key={i} variant="outline" className="bg-primary/5 text-primary border-primary/20 hover:bg-primary/10 transition-colors">
              {item}
            </Badge>
          ))}
        </div>
      </section>
    );
  }

  if (sectionType === 'faq') {
    return (
      <section className="mb-8">
        <h3 className="text-sm font-mono font-bold text-primary mb-3 uppercase tracking-wider flex items-center gap-2">
          <HelpCircle className="w-4 h-4" /> {title}
        </h3>
        <Accordion type="multiple" className="w-full">
          {items?.map((item, i) => {
            const splitMatch = item.match(/^(.*?[\?])\s+(.*)$/);
            let q = item, a = "";
            if (splitMatch) {
              q = splitMatch[1];
              a = splitMatch[2];
            } else {
              const parts = item.split(':');
              if (parts.length > 1) {
                q = parts[0];
                a = parts.slice(1).join(':').trim();
              }
            }
            return (
              <AccordionItem key={i} value={`item-${i}`} className="border-border">
                <AccordionTrigger className="text-sm hover:text-primary transition-colors text-left py-3">{q}</AccordionTrigger>
                <AccordionContent className="text-sm text-muted-foreground leading-relaxed pb-4">
                  {a}
                </AccordionContent>
              </AccordionItem>
            );
          })}
        </Accordion>
      </section>
    );
  }

  return (
    <section className="mb-8">
      <h3 className="text-sm font-mono font-bold text-primary mb-3 uppercase tracking-wider">{title}</h3>
      <Card className="bg-card/50 border-border shadow-none">
        <CardContent className="p-4">
          {content && <p className="text-sm text-card-foreground leading-relaxed mb-4">{content}</p>}
          {items && items.length > 0 && (
            <ul className="space-y-2.5">
              {items.map((item, i) => (
                <li key={i} className="text-sm flex gap-3 items-start">
                  <div className="mt-1.5 w-1.5 h-1.5 rounded-full bg-primary/50 shrink-0" />
                  <span className="text-muted-foreground leading-relaxed">{item}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

function LogsTerminal({ logs }: { logs: string[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  if (!logs || logs.length === 0) {
    return <div className="p-4 text-xs font-mono text-muted-foreground h-full flex items-center justify-center">AWAITING TELEMETRY...</div>;
  }

  return (
    <div className="bg-black text-gray-300 font-mono text-xs rounded-md overflow-hidden flex flex-col h-full border border-gray-800">
      <div className="bg-gray-900 px-3 py-2 flex items-center gap-2 border-b border-gray-800 shrink-0">
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500/80" />
          <div className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
        </div>
        <span className="text-gray-500 text-[10px] ml-2 tracking-widest">RESEARCH_PROCESS_TTY</span>
      </div>
      <div ref={scrollRef} className="p-4 overflow-y-auto flex-1 space-y-1">
        {logs.map((log, i) => {
          let colorClass = "text-gray-300";
          if (log.includes("[ERROR]") || log.includes("ERROR")) colorClass = "text-red-400";
          else if (log.includes("[WARN]") || log.includes("WARN")) colorClass = "text-amber-400";
          else if (log.includes("[INFO]") || log.includes("INFO")) colorClass = "text-emerald-400";
          else if (log.includes("[DEBUG]")) colorClass = "text-gray-500";
          
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

function ResearchResults({ research }: { research: ResearchResult }) {
  return (
    <div className="space-y-10 pb-8">
      {research.summary && (
        <section>
          <h3 className="text-sm font-mono font-bold text-primary mb-3 uppercase tracking-wider flex items-center gap-2">
            <FileText className="w-4 h-4" /> Executive Summary
          </h3>
          <div className="bg-card border border-border p-5 rounded-md text-sm text-card-foreground leading-relaxed">
            {research.summary}
          </div>
        </section>
      )}

      {research.sections?.map((section, idx) => (
        <SectionRenderer key={idx} section={section} />
      ))}

      {research.keywords?.length > 0 && (
        <section>
          <h3 className="text-sm font-mono font-bold text-primary mb-3 uppercase tracking-wider flex items-center gap-2">
            <Search className="w-4 h-4" /> Topic Intelligence (Keywords)
          </h3>
          <div className="flex flex-wrap gap-2">
            {research.keywords.map((kw, i) => (
              <KeywordChip key={i} keyword={kw} />
            ))}
          </div>
        </section>
      )}

      {research.references?.length > 0 && (
        <section>
          <h3 className="text-sm font-mono font-bold text-primary mb-3 uppercase tracking-wider flex items-center gap-2">
            <BookOpen className="w-4 h-4" /> Source Citations
          </h3>
          <div className="grid grid-cols-1 gap-3">
            {research.references.map((ref, i) => (
              <ReferenceCard key={i} reference={ref} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function ResearchDetailPanel({ selectedId, onClose }: { selectedId: string, onClose: () => void }) {
  const { data: research, isLoading, isError } = useGetResearch(selectedId, {
    query: {
      enabled: !!selectedId,
      queryKey: getGetResearchQueryKey(selectedId),
      refetchInterval: (query: any) => {
        const d = query?.state?.data;
        return (d?.status === 'running' || d?.status === 'pending') ? 2000 : false;
      }
    }
  });

  const [activeTab, setActiveTab] = useState("logs");
  
  useEffect(() => {
    if (research?.status === 'completed' || research?.status === 'cached') {
      setActiveTab("results");
    } else {
      setActiveTab("logs");
    }
  }, [research?.status]);

  if (isLoading && !research) {
    return (
      <div className="h-full flex flex-col p-6 space-y-6">
        <div className="flex justify-between items-start">
          <Skeleton className="h-10 w-2/3 bg-muted" />
          <Skeleton className="h-8 w-8 bg-muted rounded-md" />
        </div>
        <Skeleton className="h-24 w-full bg-muted" />
        <Skeleton className="flex-1 w-full bg-muted" />
      </div>
    );
  }

  if (isError || !research) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
        <AlertCircle className="w-8 h-8 mb-4 opacity-50 text-destructive" />
        <p className="font-mono text-sm uppercase">Failed to load payload</p>
        <Button variant="ghost" onClick={onClose} className="mt-4 text-xs font-mono">CLOSE TERMINAL</Button>
      </div>
    );
  }

  const isComplete = research.status === 'completed' || research.status === 'cached';

  return (
    <div className="h-full flex flex-col">
      <div className="flex-none p-6 pb-0 bg-card border-b border-border shadow-sm z-10 relative">
        <div className="flex justify-between items-start mb-6">
          <div className="space-y-2 flex-1 pr-6">
            <h2 className="text-xl font-bold tracking-tight text-foreground leading-tight line-clamp-2">
              {research.topic}
            </h2>
            <div className="text-xs text-muted-foreground font-mono flex items-center gap-3">
              <span className="opacity-50 truncate max-w-[200px]">ID: {research.id}</span>
              <StatusBadge status={research.status} />
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8 shrink-0 hover:bg-destructive/10 hover:text-destructive transition-colors">
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="grid grid-cols-3 gap-3 mb-6">
          <div className="bg-background border border-border rounded-md p-3 flex flex-col items-center justify-center gap-1.5 shadow-xs">
            <span className="text-[10px] font-mono text-muted-foreground uppercase">Confidence</span>
            <div className="mt-0.5">
              {research.confidenceScore !== null && research.confidenceScore !== undefined ? (
                <CircularProgress value={research.confidenceScore * 100} size={32} strokeWidth={3} />
              ) : <span className="text-xs font-mono text-muted-foreground">--</span>}
            </div>
          </div>
          <div className="bg-background border border-border rounded-md p-3 flex flex-col items-center justify-center gap-1 text-center shadow-xs">
            <span className="text-[10px] font-mono text-muted-foreground uppercase">Duration</span>
            <div className="text-sm font-bold font-mono text-foreground mt-1">
              {research.videoLengthMinutes}m target
            </div>
          </div>
          <div className="bg-background border border-border rounded-md p-3 flex flex-col items-center justify-center gap-1 text-center shadow-xs">
            <span className="text-[10px] font-mono text-muted-foreground uppercase">Style & Tone</span>
            <div className="text-xs font-medium text-foreground mt-1 capitalize leading-tight">
              {research.style} <br/> <span className="text-muted-foreground">{research.tone}</span>
            </div>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full -mb-[1px]">
          <TabsList className="bg-transparent h-10 w-full justify-start gap-6 border-none p-0">
            <TabsTrigger value="logs" className="font-mono text-xs uppercase data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:text-primary text-muted-foreground rounded-none px-1 h-10">
              Terminal Logs
            </TabsTrigger>
            <TabsTrigger disabled={!isComplete && (!research.sections || research.sections.length === 0)} value="results" className="font-mono text-xs uppercase data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:text-primary text-muted-foreground rounded-none px-1 h-10">
              Extracted Intelligence
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <div className="flex-1 bg-background/50 overflow-hidden relative">
        <ScrollArea className="h-full">
          <div className="p-6 h-full min-h-[500px]">
            {activeTab === "logs" && (
              <div className="h-[calc(100vh-320px)] min-h-[400px]">
                <LogsTerminal logs={research.logs || []} />
              </div>
            )}
            {activeTab === "results" && (
              <ResearchResults research={research} />
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}

function StartForm({ onStarted }: { onStarted: (id: string) => void }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const startMutation = useStartResearch();
  
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      topic: "",
      targetAudience: "",
      videoLengthMinutes: 10,
      language: "en",
      style: "educational",
      tone: "engaging",
      providers: ["openai", "wikipedia"],
    }
  });

  const onSubmit = (data: z.infer<typeof formSchema>) => {
    startMutation.mutate({ data }, {
      onSuccess: (res) => {
        toast({ title: 'Research initialized', description: 'Terminal active and polling.' });
        queryClient.invalidateQueries({ queryKey: getListResearchQueryKey() });
        form.reset();
        onStarted(res.id);
      },
      onError: (err) => {
        toast({ title: 'Failed to start', variant: 'destructive', description: String(err) });
      }
    });
  };

  return (
    <Card className="border-border bg-card/40 backdrop-blur shadow-sm overflow-hidden">
      <div className="h-1 bg-gradient-to-r from-primary/50 via-primary to-primary/50" />
      <CardHeader className="pb-4">
        <CardTitle className="text-xs font-mono tracking-widest flex items-center gap-2 uppercase text-muted-foreground">
          <Play className="w-3.5 h-3.5 text-primary" />
          Initialize New Target
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-8 space-y-6">
                <FormField control={form.control} name="topic" render={({ field }) => (
                  <FormItem>
                    <FormLabel className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">Target Topic / Query <span className="text-destructive">*</span></FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. The history and physics of mechanical keyboards" className="bg-background/80 border-border font-mono h-12 text-base shadow-inner" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )} />

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField control={form.control} name="targetAudience" render={({ field }) => (
                    <FormItem>
                      <FormLabel className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">Target Audience</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. Tech enthusiasts, beginners" className="bg-background/50" {...field} />
                      </FormControl>
                    </FormItem>
                  )} />

                  <FormField control={form.control} name="videoLengthMinutes" render={({ field }) => (
                    <FormItem>
                      <FormLabel className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">Target Duration (min)</FormLabel>
                      <FormControl>
                        <Input type="number" min={1} max={180} className="bg-background/50 font-mono" {...field} />
                      </FormControl>
                    </FormItem>
                  )} />

                  <FormField control={form.control} name="style" render={({ field }) => (
                    <FormItem>
                      <FormLabel className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">Content Style</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger className="bg-background/50 text-sm">
                            <SelectValue placeholder="Select style" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {STYLES.map(s => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </FormItem>
                  )} />

                  <FormField control={form.control} name="tone" render={({ field }) => (
                    <FormItem>
                      <FormLabel className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">Content Tone</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger className="bg-background/50 text-sm">
                            <SelectValue placeholder="Select tone" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {TONES.map(s => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    </FormItem>
                  )} />
                </div>
              </div>

              <div className="lg:col-span-4 border-l-0 lg:border-l border-border lg:pl-6 pt-6 lg:pt-0">
                <FormField control={form.control} name="providers" render={() => (
                  <FormItem>
                    <FormLabel className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider mb-4 block flex items-center gap-2">
                      <Database className="w-3 h-3" /> External Databanks
                    </FormLabel>
                    <div className="space-y-2">
                      {AVAILABLE_PROVIDERS.map((provider) => (
                        <FormField
                          key={provider.id}
                          control={form.control}
                          name="providers"
                          render={({ field }) => {
                            return (
                              <FormItem key={provider.id} className="flex flex-row items-center space-x-3 space-y-0 p-2 rounded hover:bg-accent/30 transition-colors group cursor-pointer border border-transparent hover:border-border/50">
                                <FormControl>
                                  <Checkbox
                                    checked={field.value?.includes(provider.id)}
                                    onCheckedChange={(checked) => {
                                      return checked
                                        ? field.onChange([...field.value, provider.id])
                                        : field.onChange(field.value?.filter((value) => value !== provider.id))
                                    }}
                                    className="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                                  />
                                </FormControl>
                                <FormLabel className="font-mono text-xs font-normal cursor-pointer text-muted-foreground group-hover:text-foreground transition-colors leading-none pt-0.5">
                                  {provider.label}
                                </FormLabel>
                              </FormItem>
                            )
                          }}
                        />
                      ))}
                    </div>
                  </FormItem>
                )} />
              </div>
            </div>

            <div className="flex justify-end pt-5 border-t border-border mt-6">
              <Button 
                type="submit" 
                disabled={startMutation.isPending} 
                className="font-mono text-xs uppercase tracking-widest bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-6 shadow-md transition-all"
              >
                {startMutation.isPending ? 'INITIALIZING...' : 'START RESEARCH PIPELINE'}
              </Button>
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}

function ResearchTable({ items, loading, onSelect, selectedId, onDelete }: { 
  items: any[], 
  loading: boolean, 
  onSelect: (id: string) => void,
  selectedId: string | null,
  onDelete: (id: string, e: React.MouseEvent) => void 
}) {
  if (loading) return <Skeleton className="h-[400px] w-full bg-card rounded-md border border-border" />;
  if (items.length === 0) return (
    <div className="h-48 flex flex-col items-center justify-center border border-border rounded-md bg-card/20 border-dashed text-muted-foreground">
      <Search className="w-6 h-6 mb-3 opacity-30" />
      <p className="font-mono text-xs tracking-wider uppercase opacity-70">No intelligence logs found</p>
    </div>
  );

  return (
    <div className="border border-border rounded-md overflow-hidden bg-card/40 backdrop-blur shadow-sm">
      <Table>
        <TableHeader className="bg-background/80">
          <TableRow className="border-border hover:bg-transparent">
            <TableHead className="w-[350px] font-mono text-[10px] tracking-wider uppercase text-muted-foreground">TOPIC / ID</TableHead>
            <TableHead className="font-mono text-[10px] tracking-wider uppercase text-muted-foreground">STATUS</TableHead>
            <TableHead className="font-mono text-[10px] tracking-wider uppercase text-muted-foreground w-40">CONFIDENCE</TableHead>
            <TableHead className="font-mono text-[10px] tracking-wider uppercase text-muted-foreground">SOURCES</TableHead>
            <TableHead className="text-right font-mono text-[10px] tracking-wider uppercase text-muted-foreground">ACTIONS</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => (
            <TableRow 
              key={item.id}
              onClick={() => onSelect(item.id)}
              className={cn(
                "cursor-pointer transition-colors border-border group",
                selectedId === item.id ? "bg-primary/5" : "hover:bg-accent/30"
              )}
            >
              <TableCell className="py-4">
                <div className="font-medium text-foreground text-sm truncate max-w-[330px] group-hover:text-primary transition-colors">
                  {item.topic}
                </div>
                <div className="text-[10px] text-muted-foreground font-mono mt-1.5 opacity-70 flex items-center gap-2">
                  <span>{item.id.substring(0, 8)}</span>
                  <span className="w-1 h-1 rounded-full bg-border" />
                  <span>{format(new Date(item.createdAt), 'MMM d, HH:mm')}</span>
                </div>
              </TableCell>
              <TableCell>
                <StatusBadge status={item.status} />
              </TableCell>
              <TableCell>
                {item.confidenceScore !== null && item.confidenceScore !== undefined ? (
                  <div className="flex items-center gap-3">
                    <Progress value={item.confidenceScore * 100} className="h-1.5 flex-1 bg-muted" />
                    <span className="text-[10px] font-mono font-bold w-7 text-right text-muted-foreground">
                      {Math.round(item.confidenceScore * 100)}%
                    </span>
                  </div>
                ) : (
                  <span className="text-muted-foreground text-xs font-mono opacity-50">--</span>
                )}
              </TableCell>
              <TableCell>
                <div className="flex gap-1 flex-wrap max-w-[150px]">
                  {item.providers?.slice(0, 4).map((p: string, i: number) => (
                    <span key={i} className="w-5 h-5 rounded-md bg-background border border-border flex items-center justify-center text-[9px] font-bold uppercase text-muted-foreground" title={p}>
                      {p.substring(0, 1)}
                    </span>
                  ))}
                  {item.providers?.length > 4 && (
                    <span className="text-[10px] text-muted-foreground ml-1 font-mono flex items-center">+{item.providers.length - 4}</span>
                  )}
                </div>
              </TableCell>
              <TableCell className="text-right">
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-all" 
                  onClick={(e) => onDelete(item.id, e)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default function ResearchPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  
  const { data: listResponse, isLoading: listLoading } = useListResearch({ limit: 50 });
  const queryClient = useQueryClient();
  const { toast } = useToast();
  
  const deleteMutation = useDeleteResearch();
  
  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Execute deletion protocol on this record?')) return;
    deleteMutation.mutate({ id }, {
      onSuccess: () => {
        toast({ title: 'Record purged' });
        queryClient.invalidateQueries({ queryKey: getListResearchQueryKey() });
        if (selectedId === id) setSelectedId(null);
      }
    });
  };

  return (
    <div className="flex h-full w-full bg-background relative overflow-hidden">
      <div className={cn(
        "flex-1 flex flex-col h-full transition-all duration-300 ease-in-out", 
        selectedId ? "mr-[600px] border-r border-border shadow-[-10px_0_30px_rgba(0,0,0,0.5)] z-0" : "mr-0"
      )}>
        <ScrollArea className="flex-1 h-full">
          <div className="p-8 max-w-[1200px] mx-auto space-y-10 pb-20">
             <div className="flex items-start justify-between">
               <div className="flex items-center gap-4">
                 <div className="w-12 h-12 bg-primary/10 border border-primary/20 rounded-xl flex items-center justify-center shadow-inner">
                   <Search className="w-6 h-6 text-primary" />
                 </div>
                 <div>
                   <h1 className="text-2xl font-bold tracking-tight text-foreground uppercase font-sans">Intelligence Terminal</h1>
                   <p className="text-sm text-muted-foreground font-mono mt-1">Autonomous topic research and structured data extraction.</p>
                 </div>
               </div>
             </div>

             <StartForm onStarted={(id) => setSelectedId(id)} />

             <div className="space-y-4">
               <div className="flex items-center justify-between border-b border-border pb-3">
                 <h2 className="text-sm font-mono tracking-widest uppercase font-bold flex items-center gap-2">
                   <Database className="w-4 h-4 text-muted-foreground" />
                   Recent Operations
                 </h2>
                 {listResponse && (
                   <span className="text-xs font-mono text-muted-foreground">TOTAL: {listResponse.total}</span>
                 )}
               </div>
               
               <ResearchTable 
                 items={listResponse?.items || []} 
                 loading={listLoading}
                 onSelect={setSelectedId}
                 selectedId={selectedId}
                 onDelete={handleDelete}
               />
             </div>
          </div>
        </ScrollArea>
      </div>

      <AnimatePresence>
        {selectedId && (
          <motion.div 
            initial={{ x: "100%", opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "100%", opacity: 0 }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="absolute top-0 right-0 bottom-0 w-[600px] bg-card/95 backdrop-blur-xl shadow-2xl flex flex-col z-40 border-l border-border"
          >
             <ResearchDetailPanel selectedId={selectedId} onClose={() => setSelectedId(null)} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}