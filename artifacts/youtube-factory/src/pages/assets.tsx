import React, { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { format } from 'date-fns';
import { motion, AnimatePresence } from 'framer-motion';
import {
  useListAssets, useAcquireAssets, useDeleteAsset, useListAssetProviders,
  getListAssetsQueryKey, getListAssetProvidersQueryKey,
  useListStoryboards,
  AssetResult, AssetProviderStats,
} from '@workspace/api-client-react';

import {
  Image as ImageIcon, Film, Sparkles, Shapes, Map as MapIcon, PanelTop,
  RefreshCw, CheckCircle2, Clock, AlertCircle, Search, Download,
  Trash2, X, Zap, DollarSign, Layers, Server, Gauge, Database,
} from 'lucide-react';

import { cn } from "@/lib/utils";
import { Button } from '@/components/ui/button';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useToast } from '@/hooks/use-toast';

// ── Constants ──────────────────────────────────────────────────────────────────

const ASSET_KINDS = [
  { id: 'image', label: 'Image', icon: ImageIcon },
  { id: 'video', label: 'Video', icon: Film },
  { id: 'icon', label: 'Icon', icon: Shapes },
  { id: 'svg', label: 'SVG', icon: PanelTop },
  { id: 'chart', label: 'Chart', icon: Gauge },
  { id: 'map', label: 'Map', icon: MapIcon },
];

const ALL_PROVIDERS = [
  { id: 'wikimedia', label: 'Wikimedia', type: 'stock' },
  { id: 'unsplash', label: 'Unsplash', type: 'stock' },
  { id: 'pixabay', label: 'Pixabay', type: 'stock' },
  { id: 'pexels', label: 'Pexels', type: 'stock' },
  { id: 'pexels_video', label: 'Pexels Video', type: 'stock' },
  { id: 'pixabay_video', label: 'Pixabay Video', type: 'stock' },
  { id: 'mixkit', label: 'Mixkit', type: 'stock' },
  { id: 'lucide', label: 'Lucide', type: 'icon' },
  { id: 'heroicons', label: 'Heroicons', type: 'icon' },
  { id: 'material_icons', label: 'Material Icons', type: 'icon' },
  { id: 'flux', label: 'Flux', type: 'generate' },
  { id: 'sdxl', label: 'SDXL', type: 'generate' },
  { id: 'gpt_image', label: 'GPT Image', type: 'generate' },
  { id: 'gemini_image', label: 'Gemini Image', type: 'generate' },
  { id: 'ideogram', label: 'Ideogram', type: 'generate' },
];

const KIND_ICON: Record<string, any> = {
  image: ImageIcon, video: Film, icon: Shapes, svg: PanelTop, chart: Gauge, map: MapIcon,
};

const IN_PROGRESS_STATUSES = ['pending', 'searching', 'downloading', 'generating'];

// ── Form schema ─────────────────────────────────────────────────────────────────

const formSchema = z.object({
  storyboardId: z.string().min(1, 'Select a storyboard'),
  assetKinds: z.array(z.string()).min(1, 'Select at least one asset kind').default(['image']),
  providers: z.array(z.string()).min(1, 'Select at least one provider').default(['wikimedia', 'pexels', 'pixabay', 'flux']),
  forceGenerate: z.boolean().default(false),
});

// ── Helpers ────────────────────────────────────────────────────────────────────

function formatBytes(n: number | null | undefined): string {
  if (!n) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; className: string; icon: any }> = {
    pending: { label: 'PENDING', className: 'bg-status-queued text-amber-500 border-amber-500/20', icon: Clock },
    searching: { label: 'SEARCHING', className: 'bg-status-running text-blue-500 border-blue-500/20 animate-pulse-running', icon: Search },
    downloading: { label: 'DOWNLOADING', className: 'bg-status-running text-cyan-500 border-cyan-500/20 animate-pulse-running', icon: Download },
    generating: { label: 'GENERATING', className: 'bg-status-running text-purple-500 border-purple-500/20 animate-pulse-running', icon: Sparkles },
    ready: { label: 'READY', className: 'bg-status-completed text-emerald-500 border-emerald-500/20', icon: CheckCircle2 },
    cached: { label: 'CACHED', className: 'bg-status-completed text-blue-500 border-blue-500/20', icon: Database },
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
  if (!logs?.length) {
    return <div className="p-4 text-xs font-mono text-muted-foreground flex items-center justify-center h-full">AWAITING TELEMETRY...</div>;
  }
  return (
    <div className="bg-black text-gray-300 font-mono text-xs rounded-md overflow-hidden flex flex-col border border-gray-800">
      <div className="bg-gray-900 px-3 py-2 flex items-center gap-2 border-b border-gray-800 shrink-0">
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500/80" />
          <div className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
        </div>
        <span className="text-gray-500 text-[10px] ml-2 tracking-widest">ASSET_ACQUISITION_TTY</span>
      </div>
      <div className="p-4 overflow-y-auto flex-1 space-y-1 max-h-64">
        {logs.map((log, i) => {
          const colorClass = log.includes('ERROR') ? 'text-red-400' :
                             log.includes('WARN') ? 'text-amber-400' :
                             log.includes('INFO') ? 'text-emerald-400' : 'text-gray-300';
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

// ── Asset card ─────────────────────────────────────────────────────────────────

function AssetCard({ asset, onOpen, onDelete }: { asset: AssetResult; onOpen: () => void; onDelete: () => void }) {
  const Icon = KIND_ICON[asset.assetKind] ?? ImageIcon;
  return (
    <div
      className="border border-border rounded-md overflow-hidden group hover:border-primary/40 transition-colors cursor-pointer"
      onClick={onOpen}
    >
      <div className="aspect-video bg-muted/40 flex items-center justify-center relative">
        <Icon className="w-8 h-8 text-muted-foreground/40" />
        <div className="absolute top-2 left-2"><StatusBadge status={asset.status} /></div>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded bg-black/50 hover:bg-red-500/70 text-white"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>
      <div className="p-2.5 space-y-1.5">
        <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground">
          <span className="uppercase font-bold">{asset.assetKind}</span>
          <span className="truncate">{asset.sceneId}</span>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          {asset.provider && (
            <Badge variant="outline" className="text-[9px] font-mono">{asset.provider}</Badge>
          )}
          {asset.license && asset.license !== 'unknown' && (
            <Badge variant="outline" className="text-[9px] font-mono">{asset.license}</Badge>
          )}
        </div>
        {(asset.qualityScore != null || asset.relevanceScore != null) && (
          <div className="flex gap-2 text-[9px] font-mono text-muted-foreground">
            {asset.qualityScore != null && <span>Q {(asset.qualityScore * 100).toFixed(0)}%</span>}
            {asset.relevanceScore != null && <span>R {(asset.relevanceScore * 100).toFixed(0)}%</span>}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function AssetsPage() {
  const { toast } = useToast();
  const [selectedAsset, setSelectedAsset] = useState<AssetResult | null>(null);
  const [filterStoryboardId, setFilterStoryboardId] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterKind, setFilterKind] = useState<string>('all');

  const { data: storyboardsData } = useListStoryboards({ limit: 100 });
  const storyboards = storyboardsData?.items ?? [];

  const listParams = {
    limit: 200,
    storyboardId: filterStoryboardId !== 'all' ? filterStoryboardId : undefined,
    status: filterStatus !== 'all' ? filterStatus : undefined,
    assetKind: filterKind !== 'all' ? filterKind : undefined,
  };
  const { data: assetsData, isLoading, refetch } = useListAssets(
    listParams,
    { query: { queryKey: getListAssetsQueryKey(listParams), refetchInterval: 3000 } },
  );
  const assets = assetsData?.items ?? [];

  const { data: providersData } = useListAssetProviders({ query: { queryKey: getListAssetProvidersQueryKey(), refetchInterval: 5000 } });
  const providerStats = providersData?.items ?? [];

  const acquireMutation = useAcquireAssets({
    mutation: {
      onSuccess: (res) => {
        toast({ title: 'Acquisition queued', description: res.message });
        refetch();
      },
      onError: (err: any) => {
        toast({ title: 'Failed to queue acquisition', description: String(err?.message ?? err), variant: 'destructive' });
      },
    },
  });

  const deleteMutation = useDeleteAsset({
    mutation: {
      onSuccess: () => { refetch(); setSelectedAsset(null); },
    },
  });

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: { storyboardId: '', assetKinds: ['image'], providers: ['wikimedia', 'pexels', 'pixabay', 'flux'], forceGenerate: false },
  });

  const onSubmit = (values: z.infer<typeof formSchema>) => {
    acquireMutation.mutate({
      data: {
        storyboardId: values.storyboardId,
        assetKinds: values.assetKinds as any,
        providers: values.providers,
        forceGenerate: values.forceGenerate,
      },
    });
  };

  const downloadQueue = useMemo(() => assets.filter(a => IN_PROGRESS_STATUSES.includes(a.status)), [assets]);
  const cacheStats = useMemo(() => {
    const cached = assets.filter(a => a.status === 'cached' || a.status === 'ready');
    const totalCostUsd = cached.reduce((s, a) => s + (a.costEstimateUsd ?? 0), 0);
    const totalBytes = cached.reduce((s, a) => s + (a.fileSizeBytes ?? 0), 0);
    return { count: cached.length, totalCostUsd, totalBytes, failedCount: assets.filter(a => a.status === 'failed').length };
  }, [assets]);

  return (
    <div className="flex-1 flex flex-col overflow-y-auto">
      <div className="border-b border-border px-6 py-4 flex items-center justify-between sticky top-0 bg-background z-10">
        <div>
          <h1 className="text-lg font-bold tracking-tight flex items-center gap-2">
            <ImageIcon className="w-5 h-5 text-primary" /> Asset Library
          </h1>
          <p className="text-xs text-muted-foreground font-mono mt-0.5">
            Cache → Stock Search → AI Generation decision engine
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
        </Button>
      </div>

      <div className="p-6 space-y-6">
        {/* Acquisition form */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm flex items-center gap-2"><Zap className="w-4 h-4" /> Acquire Assets</CardTitle>
          </CardHeader>
          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="storyboardId"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Storyboard</FormLabel>
                      <Select value={field.value} onValueChange={field.onChange}>
                        <FormControl>
                          <SelectTrigger><SelectValue placeholder="Select a storyboard" /></SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {storyboards.map((s) => (
                            <SelectItem key={s.id} value={s.id}>{s.title ?? s.topic} ({s.sceneCount ?? 0} scenes)</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="assetKinds"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Asset kinds</FormLabel>
                      <div className="flex flex-wrap gap-3">
                        {ASSET_KINDS.map((k) => (
                          <label key={k.id} className="flex items-center gap-2 text-sm cursor-pointer">
                            <Checkbox
                              checked={field.value?.includes(k.id)}
                              onCheckedChange={(checked) => {
                                const next = checked
                                  ? [...(field.value ?? []), k.id]
                                  : (field.value ?? []).filter((v: string) => v !== k.id);
                                field.onChange(next);
                              }}
                            />
                            <k.icon className="w-3.5 h-3.5 text-muted-foreground" /> {k.label}
                          </label>
                        ))}
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="providers"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Provider preference (tried in order)</FormLabel>
                      <div className="flex flex-wrap gap-3">
                        {ALL_PROVIDERS.map((p) => (
                          <label key={p.id} className="flex items-center gap-1.5 text-xs cursor-pointer">
                            <Checkbox
                              checked={field.value?.includes(p.id)}
                              onCheckedChange={(checked) => {
                                const next = checked
                                  ? [...(field.value ?? []), p.id]
                                  : (field.value ?? []).filter((v: string) => v !== p.id);
                                field.onChange(next);
                              }}
                            />
                            {p.label}
                          </label>
                        ))}
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="forceGenerate"
                  render={({ field }) => (
                    <FormItem className="flex items-center gap-2 space-y-0">
                      <FormControl>
                        <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                      <FormLabel className="!mt-0">Force AI generation (skip stock search)</FormLabel>
                    </FormItem>
                  )}
                />

                <Button type="submit" disabled={acquireMutation.isPending}>
                  {acquireMutation.isPending ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Zap className="w-4 h-4 mr-2" />}
                  Queue Acquisition
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>

        <Tabs defaultValue="browser" className="w-full">
          <TabsList>
            <TabsTrigger value="browser">Browser</TabsTrigger>
            <TabsTrigger value="queue">Download Queue ({downloadQueue.length})</TabsTrigger>
            <TabsTrigger value="cache">Cache Manager</TabsTrigger>
            <TabsTrigger value="providers">Provider Stats</TabsTrigger>
          </TabsList>

          {/* Browser */}
          <TabsContent value="browser" className="space-y-4">
            <div className="flex gap-3 flex-wrap">
              <Select value={filterStoryboardId} onValueChange={setFilterStoryboardId}>
                <SelectTrigger className="w-56"><SelectValue placeholder="All storyboards" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All storyboards</SelectItem>
                  {storyboards.map((s) => <SelectItem key={s.id} value={s.id}>{s.title ?? s.topic}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger className="w-40"><SelectValue placeholder="All statuses" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  {['pending', 'searching', 'downloading', 'generating', 'ready', 'cached', 'failed'].map(s => (
                    <SelectItem key={s} value={s}>{s}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={filterKind} onValueChange={setFilterKind}>
                <SelectTrigger className="w-36"><SelectValue placeholder="All kinds" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All kinds</SelectItem>
                  {ASSET_KINDS.map(k => <SelectItem key={k.id} value={k.id}>{k.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>

            {isLoading ? (
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="aspect-video rounded-md" />)}
              </div>
            ) : assets.length === 0 ? (
              <div className="text-center py-16 text-sm text-muted-foreground">No assets yet — queue an acquisition above.</div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                {assets.map((a) => (
                  <AssetCard key={a.id} asset={a} onOpen={() => setSelectedAsset(a)} onDelete={() => deleteMutation.mutate({ id: a.id })} />
                ))}
              </div>
            )}
          </TabsContent>

          {/* Download Queue */}
          <TabsContent value="queue" className="space-y-2">
            {downloadQueue.length === 0 ? (
              <div className="text-center py-16 text-sm text-muted-foreground">Nothing in progress.</div>
            ) : downloadQueue.map((a) => {
              const stepIndex = IN_PROGRESS_STATUSES.indexOf(a.status);
              const pct = ((stepIndex + 1) / IN_PROGRESS_STATUSES.length) * 100;
              return (
                <div key={a.id} className="border border-border rounded-md p-3 flex items-center gap-4 cursor-pointer hover:border-primary/40" onClick={() => setSelectedAsset(a)}>
                  <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center shrink-0">
                    {React.createElement(KIND_ICON[a.assetKind] ?? ImageIcon, { className: 'w-4 h-4 text-primary' })}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-mono text-muted-foreground truncate">{a.sceneId} — {a.assetKind}</span>
                      <StatusBadge status={a.status} />
                    </div>
                    <Progress value={pct} className="h-1.5" />
                  </div>
                </div>
              );
            })}
          </TabsContent>

          {/* Cache manager */}
          <TabsContent value="cache" className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <MetricChip icon={Database} label="Cached/Ready" value={cacheStats.count} className="border-emerald-500/20 text-emerald-500" />
              <MetricChip icon={DollarSign} label="Total Cost" value={`$${cacheStats.totalCostUsd.toFixed(2)}`} className="border-amber-500/20 text-amber-500" />
              <MetricChip icon={Layers} label="Cache Size" value={formatBytes(cacheStats.totalBytes)} className="border-blue-500/20 text-blue-500" />
              <MetricChip icon={AlertCircle} label="Failed" value={cacheStats.failedCount} className="border-red-500/20 text-red-500" />
            </div>
            <div className="space-y-1.5">
              {assets.filter(a => a.localCachePath).map((a) => (
                <div key={a.id} className="flex items-center justify-between text-xs font-mono border border-border rounded-md px-3 py-2">
                  <span className="truncate text-muted-foreground">{a.localCachePath}</span>
                  <div className="flex items-center gap-3 shrink-0 ml-4">
                    <span className="text-muted-foreground">{formatBytes(a.fileSizeBytes)}</span>
                    <StatusBadge status={a.status} />
                    <button onClick={() => deleteMutation.mutate({ id: a.id })} className="text-red-400 hover:text-red-500">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          {/* Provider stats */}
          <TabsContent value="providers">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {providerStats.map((p: AssetProviderStats) => {
                const successRate = p.totalRequests > 0 ? (p.successfulRequests / p.totalRequests) * 100 : 0;
                return (
                  <div key={p.providerName} className="border border-border rounded-md p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium flex items-center gap-1.5">
                        <Server className="w-3.5 h-3.5 text-muted-foreground" /> {p.providerName}
                      </span>
                      <Badge variant="outline" className="text-[9px] font-mono uppercase">{p.providerType}</Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-muted-foreground">
                      <div>Requests: <span className="text-foreground font-bold">{p.totalRequests}</span></div>
                      <div>Success: <span className="text-foreground font-bold">{successRate.toFixed(0)}%</span></div>
                      <div>Avg latency: <span className="text-foreground font-bold">{p.avgLatencyMs != null ? `${p.avgLatencyMs.toFixed(0)}ms` : '—'}</span></div>
                      <div>Cache hits: <span className="text-foreground font-bold">{p.cacheHits}</span></div>
                      <div>Avg cost: <span className="text-foreground font-bold">{p.avgCostUsd != null ? `$${p.avgCostUsd.toFixed(3)}` : '—'}</span></div>
                      <div>Total cost: <span className="text-foreground font-bold">${p.totalCostUsd.toFixed(2)}</span></div>
                    </div>
                    <Progress value={successRate} className="h-1" />
                  </div>
                );
              })}
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* Preview / detail dialog */}
      <Dialog open={!!selectedAsset} onOpenChange={(open) => !open && setSelectedAsset(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          {selectedAsset && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {React.createElement(KIND_ICON[selectedAsset.assetKind] ?? ImageIcon, { className: 'w-4 h-4' })}
                  {selectedAsset.assetKind} — {selectedAsset.sceneId}
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="flex items-center gap-2 flex-wrap">
                  <StatusBadge status={selectedAsset.status} />
                  {selectedAsset.provider && <Badge variant="outline">{selectedAsset.provider}</Badge>}
                  {selectedAsset.license && <Badge variant="outline">{selectedAsset.license}</Badge>}
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs font-mono text-muted-foreground">
                  <div>Dimensions: <span className="text-foreground">{selectedAsset.width && selectedAsset.height ? `${selectedAsset.width}×${selectedAsset.height}` : '—'}</span></div>
                  <div>File size: <span className="text-foreground">{formatBytes(selectedAsset.fileSizeBytes)}</span></div>
                  <div>Quality: <span className="text-foreground">{selectedAsset.qualityScore != null ? `${(selectedAsset.qualityScore * 100).toFixed(0)}%` : '—'}</span></div>
                  <div>Relevance: <span className="text-foreground">{selectedAsset.relevanceScore != null ? `${(selectedAsset.relevanceScore * 100).toFixed(0)}%` : '—'}</span></div>
                  <div>Cost: <span className="text-foreground">${(selectedAsset.costEstimateUsd ?? 0).toFixed(3)}</span></div>
                  <div>Created: <span className="text-foreground">{format(new Date(selectedAsset.createdAt), 'MMM d, HH:mm:ss')}</span></div>
                </div>
                {selectedAsset.localCachePath && (
                  <div className="text-xs font-mono text-muted-foreground bg-muted/30 rounded p-2 truncate">{selectedAsset.localCachePath}</div>
                )}
                {selectedAsset.errorMessage && (
                  <div className="text-xs text-red-400 bg-red-500/5 border border-red-500/20 rounded p-2">{selectedAsset.errorMessage}</div>
                )}
                <LogsTerminal logs={selectedAsset.logs} />
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => deleteMutation.mutate({ id: selectedAsset.id })}
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1.5" /> Delete asset
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
