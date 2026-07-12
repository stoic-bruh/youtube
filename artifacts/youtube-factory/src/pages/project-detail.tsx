import { useParams, Link } from "wouter";
import { useGetProject, useGetPipeline, useRunProject } from "@workspace/api-client-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { 
  ArrowLeft, Play, RefreshCw, CheckCircle2, 
  XCircle, Clock, Video, FileText, Image as ImageIcon, 
  Mic, Scissors, Subtitles, Youtube, LayoutTemplate,
  Activity
} from "lucide-react";
import { cn } from "@/lib/utils";

const STAGE_ICONS: Record<string, any> = {
  research: FileText,
  script: FileText,
  scene_planning: LayoutTemplate,
  image_generation: ImageIcon,
  voice_generation: Mic,
  video_editing: Scissors,
  subtitle_generation: Subtitles,
  thumbnail_generation: ImageIcon,
  seo_generation: Youtube,
  upload: Youtube
};

export default function ProjectDetail() {
  const params = useParams();
  const id = params.id as string;
  
  const { data: projectData, isLoading: projectLoading } = useGetProject(id, { 
    query: { enabled: !!id, queryKey: ['project', id] } 
  });
  
  // Use pipelineId if available, otherwise just mock it for display
  const pipelineId = projectData?.pipelineId || `pipe_${id}`;
  
  const { data: pipelineData, isLoading: pipelineLoading } = useGetPipeline(pipelineId, {
    query: { enabled: !!pipelineId, refetchInterval: 3000, queryKey: ['pipeline', pipelineId] }
  });

  const runProject = useRunProject();

  // Mock fallback
  const p = projectData || {
    id: id || "proj_mock",
    title: "React 19 Features Explained",
    topic: "Web Development",
    description: "Deep dive into the new hooks like useActionState and useFormStatus.",
    status: "running",
    tags: ["react", "frontend", "tutorial"],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    youtubeUrl: null
  };

  const pl = pipelineData || {
    id: pipelineId,
    projectId: p.id,
    status: "running",
    progress: 45,
    currentStage: "voice_generation",
    stages: [
      { name: "research", status: "completed", order: 1, durationMs: 15000 },
      { name: "script", status: "completed", order: 2, durationMs: 45000 },
      { name: "scene_planning", status: "completed", order: 3, durationMs: 12000 },
      { name: "image_generation", status: "completed", order: 4, durationMs: 120000 },
      { name: "voice_generation", status: "running", order: 5, durationMs: null },
      { name: "video_editing", status: "pending", order: 6, durationMs: null },
      { name: "subtitle_generation", status: "pending", order: 7, durationMs: null },
      { name: "thumbnail_generation", status: "pending", order: 8, durationMs: null },
      { name: "seo_generation", status: "pending", order: 9, durationMs: null },
      { name: "upload", status: "pending", order: 10, durationMs: null }
    ],
    startedAt: new Date(Date.now() - 300000).toISOString()
  };

  const handleRun = () => {
    if (!id) return;
    runProject.mutate({ id });
  };

  if (projectLoading && !projectData) {
    return <div className="p-6 flex items-center justify-center h-full text-muted-foreground font-mono">LOADING PROJECT DATA...</div>;
  }

  const isRunning = p.status === 'running' || pl.status === 'running';

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6 flex flex-col h-full overflow-y-auto">
      <div className="flex items-center gap-4 shrink-0 mb-2">
        <Link href="/projects" className="text-muted-foreground hover:text-foreground transition-colors p-2 -ml-2 rounded-md hover:bg-accent">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold font-mono tracking-tight">{p.title}</h1>
            <StatusBadge status={p.status} />
          </div>
          <div className="text-xs font-mono text-muted-foreground mt-1 flex items-center gap-4">
            <span>ID: {p.id}</span>
            <span>TOPIC: {p.topic}</span>
          </div>
        </div>
        
        <div className="ml-auto flex items-center gap-2">
          <Button 
            onClick={handleRun} 
            disabled={isRunning || runProject.isPending}
            className="font-mono text-xs uppercase tracking-wider"
          >
            {isRunning ? (
              <><RefreshCw className="h-4 w-4 mr-2 animate-spin" /> Running Pipeline</>
            ) : (
              <><Play className="h-4 w-4 mr-2" /> Start Pipeline</>
            )}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 shrink-0">
        <Card className="lg:col-span-2 bg-card/50 border-border/50">
          <CardHeader>
            <CardTitle className="text-sm font-medium uppercase tracking-wider font-mono flex justify-between items-center">
              <span>Pipeline Progress</span>
              <span className="text-muted-foreground">{pl.progress}%</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <Progress value={pl.progress} className="h-2" />
            
            <div className="space-y-3 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-border before:to-transparent">
              {pl.stages?.map((stage, idx) => {
                const Icon = STAGE_ICONS[stage.name] || Activity;
                const isCurrent = stage.status === 'running';
                
                return (
                  <div key={stage.name} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group">
                    <div className="flex items-center justify-center w-10 h-10 rounded-full border-4 border-background bg-card shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 z-10 relative">
                      {stage.status === 'completed' ? (
                        <CheckCircle2 className="h-5 w-5 text-blue-500" />
                      ) : stage.status === 'failed' ? (
                        <XCircle className="h-5 w-5 text-red-500" />
                      ) : stage.status === 'running' ? (
                        <div className="h-3 w-3 rounded-full bg-emerald-500 animate-pulse-running" />
                      ) : (
                        <div className="h-2 w-2 rounded-full bg-muted-foreground" />
                      )}
                    </div>
                    
                    <div className={cn(
                      "w-[calc(100%-3rem)] md:w-[calc(50%-2.5rem)] p-4 rounded-lg border",
                      isCurrent ? "bg-accent/50 border-emerald-500/30" : "bg-card/50 border-border/50"
                    )}>
                      <div className="flex items-center justify-between mb-1">
                        <span className={cn(
                          "text-xs font-mono uppercase tracking-wider font-bold flex items-center gap-2",
                          isCurrent ? "text-emerald-500" : "text-foreground"
                        )}>
                          <Icon className="h-3.5 w-3.5" />
                          {stage.name.replace(/_/g, ' ')}
                        </span>
                        <StatusBadge status={stage.status} className="scale-90" />
                      </div>
                      {stage.durationMs && (
                        <div className="text-[10px] font-mono text-muted-foreground flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {(stage.durationMs / 1000).toFixed(1)}s
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card className="bg-card/50 border-border/50">
            <CardHeader>
              <CardTitle className="text-sm font-medium uppercase tracking-wider font-mono">Project Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div>
                <div className="text-xs font-mono text-muted-foreground mb-1">Description</div>
                <p className="text-sm">{p.description || "No description provided."}</p>
              </div>
              <div>
                <div className="text-xs font-mono text-muted-foreground mb-1">Tags</div>
                <div className="flex flex-wrap gap-2">
                  {p.tags?.map(tag => (
                    <span key={tag} className="px-2 py-1 bg-accent rounded text-[10px] font-mono">{tag}</span>
                  ))}
                  {(!p.tags || p.tags.length === 0) && <span className="text-muted-foreground">-</span>}
                </div>
              </div>
              <div className="pt-4 border-t border-border/50">
                <div className="text-xs font-mono text-muted-foreground mb-1">Created</div>
                <div className="font-mono">{new Date(p.createdAt).toLocaleString()}</div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card/50 border-border/50">
            <CardHeader>
              <CardTitle className="text-sm font-medium uppercase tracking-wider font-mono">Output Assets</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {p.youtubeUrl ? (
                <a href={p.youtubeUrl} target="_blank" rel="noreferrer" className="flex items-center gap-3 p-3 rounded-md bg-accent/50 hover:bg-accent transition-colors border border-border/50">
                  <Youtube className="h-5 w-5 text-red-500" />
                  <div className="flex-1 overflow-hidden text-sm">
                    <div className="font-medium truncate">View on YouTube</div>
                    <div className="text-xs text-muted-foreground font-mono truncate">{p.youtubeUrl}</div>
                  </div>
                </a>
              ) : (
                <div className="text-center py-6 text-xs font-mono text-muted-foreground border border-dashed border-border/50 rounded-md bg-background/50">
                  NO ASSETS YET
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
