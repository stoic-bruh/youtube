import { useListPipelines } from "@workspace/api-client-react";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/status-badge";
import { Progress } from "@/components/ui/progress";
import { Clock } from "lucide-react";
import { Link } from "wouter";
import { cn } from "@/lib/utils";

export default function Pipelines() {
  const { data: pipelineData, isLoading } = useListPipelines(
    { limit: 50 }, 
    { query: { refetchInterval: 3000 } }
  );

  const pipelines = pipelineData?.items || [
    { 
      id: "pipe_1", 
      projectId: "proj_1a2b", 
      status: "running", 
      progress: 65, 
      currentStage: "video_editing",
      startedAt: new Date(Date.now() - 400000).toISOString(),
      stages: Array(10).fill({}).map((_, i) => ({ 
        status: i < 5 ? "completed" : i === 5 ? "running" : "pending" 
      }))
    },
    { 
      id: "pipe_2", 
      projectId: "proj_3c4d", 
      status: "queued", 
      progress: 0, 
      currentStage: null,
      startedAt: new Date(Date.now() - 60000).toISOString(),
      stages: Array(10).fill({ status: "pending" })
    },
    { 
      id: "pipe_3", 
      projectId: "proj_5e6f", 
      status: "failed", 
      progress: 30, 
      currentStage: "image_generation",
      startedAt: new Date(Date.now() - 3600000).toISOString(),
      stages: Array(10).fill({}).map((_, i) => ({ 
        status: i < 3 ? "completed" : i === 3 ? "failed" : "pending" 
      }))
    },
    { 
      id: "pipe_4", 
      projectId: "proj_7g8h", 
      status: "completed", 
      progress: 100, 
      currentStage: "upload",
      startedAt: new Date(Date.now() - 86400000).toISOString(),
      stages: Array(10).fill({ status: "completed" })
    }
  ];

  const formatDuration = (start: string) => {
    const diffMs = Date.now() - new Date(start).getTime();
    const m = Math.floor(diffMs / 60000);
    const s = Math.floor((diffMs % 60000) / 1000);
    return `${m}m ${s}s`;
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6 flex flex-col h-full">
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-2xl font-bold font-mono tracking-tight">PIPELINE MONITOR</h1>
          <p className="text-sm text-muted-foreground mt-1">Live status of all automated video production pipelines.</p>
        </div>
      </div>

      <Card className="flex-1 overflow-hidden bg-card/50 flex flex-col border-border/50">
        <div className="overflow-auto flex-1">
          <Table>
            <TableHeader className="bg-card sticky top-0 z-10">
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-[120px] font-mono text-xs">PIPELINE ID</TableHead>
                <TableHead className="w-[120px] font-mono text-xs">PROJECT ID</TableHead>
                <TableHead className="font-mono text-xs w-[120px]">STATUS</TableHead>
                <TableHead className="font-mono text-xs min-w-[200px]">PROGRESS</TableHead>
                <TableHead className="text-right font-mono text-xs">RUNTIME</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && !pipelineData ? (
                Array(5).fill(0).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell><div className="h-4 w-20 bg-muted animate-pulse rounded" /></TableCell>
                    <TableCell><div className="h-4 w-20 bg-muted animate-pulse rounded" /></TableCell>
                    <TableCell><div className="h-4 w-16 bg-muted animate-pulse rounded" /></TableCell>
                    <TableCell><div className="h-4 w-full bg-muted animate-pulse rounded" /></TableCell>
                    <TableCell><div className="h-4 w-16 bg-muted animate-pulse rounded ml-auto" /></TableCell>
                  </TableRow>
                ))
              ) : pipelines.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8 text-muted-foreground font-mono text-sm">
                    No active pipelines.
                  </TableCell>
                </TableRow>
              ) : (
                pipelines.map((pipeline) => (
                  <TableRow key={pipeline.id} className="hover:bg-muted/30">
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {pipeline.id.substring(0, 8)}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      <Link href={`/projects/${pipeline.projectId}`} className="text-blue-400 hover:underline">
                        {pipeline.projectId.substring(0, 8)}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={pipeline.status} />
                    </TableCell>
                    <TableCell>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground">
                          <span className="uppercase">{pipeline.currentStage?.replace(/_/g, ' ') || 'Waiting...'}</span>
                          <span>{pipeline.progress}%</span>
                        </div>
                        <Progress value={pipeline.progress} className="h-1.5" />
                        <div className="flex gap-1 h-1.5">
                          {pipeline.stages?.map((stage, i) => (
                            <div 
                              key={i} 
                              className={cn(
                                "flex-1 rounded-full",
                                stage.status === 'completed' ? "bg-blue-500/50" :
                                stage.status === 'failed' ? "bg-red-500/50" :
                                stage.status === 'running' ? "bg-emerald-500 animate-pulse-running" :
                                "bg-muted"
                              )}
                            />
                          ))}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-right text-xs font-mono text-muted-foreground">
                      <div className="flex items-center justify-end gap-1.5">
                        <Clock className="h-3 w-3" />
                        {pipeline.status === 'running' ? formatDuration(pipeline.startedAt) : '-'}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </Card>
    </div>
  );
}
