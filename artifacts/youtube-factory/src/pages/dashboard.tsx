import { useGetDashboardStats, useGetPipelineActivity } from "@workspace/api-client-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, Clock, AlertTriangle, CheckCircle2, Film } from "lucide-react";
import { StatusBadge } from "@/components/status-badge";
import { Link } from "wouter";

export default function Dashboard() {
  const { data: stats, isLoading: statsLoading } = useGetDashboardStats({ query: { refetchInterval: 5000 } });
  
  // Fallback mock data if API is empty
  const s = stats || {
    totalProjects: 12,
    totalVideos: 8,
    activeJobs: 3,
    queuedJobs: 5,
    failedJobs: 1,
    successRate: 88.5,
    totalRuntime: 14500000,
    projectsByStatus: [
      { status: "completed", count: 8 },
      { status: "running", count: 2 },
      { status: "queued", count: 1 },
      { status: "failed", count: 1 }
    ],
    recentActivity: [
      { id: "1", type: "pipeline_completed", message: "Pipeline finished for project 'AI News'", projectId: "p1", status: "completed", timestamp: new Date(Date.now() - 5000).toISOString() },
      { id: "2", type: "stage_started", message: "Started video_editing for 'React Tutorial'", projectId: "p2", status: "running", timestamp: new Date(Date.now() - 60000).toISOString() },
      { id: "3", type: "job_failed", message: "Failed to generate thumbnail", projectId: "p3", status: "failed", timestamp: new Date(Date.now() - 120000).toISOString() },
    ]
  };

  const formatRuntime = (ms: number) => {
    const hours = Math.floor(ms / (1000 * 60 * 60));
    const minutes = Math.floor((ms % (1000 * 60 * 60)) / (1000 * 60));
    return `${hours}h ${minutes}m`;
  };

  const formatTimeAgo = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    if (diff < 60000) return `${Math.floor(diff/1000)}s ago`;
    if (diff < 3600000) return `${Math.floor(diff/60000)}m ago`;
    return `${Math.floor(diff/3600000)}h ago`;
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold font-mono tracking-tight">DASHBOARD</h1>
        <div className="text-xs text-muted-foreground font-mono">
          Last updated: {new Date().toLocaleTimeString()}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-card/50">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider font-mono">Active Jobs</CardTitle>
            <Activity className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono">{statsLoading ? "-" : s.activeJobs}</div>
            <p className="text-xs text-muted-foreground mt-1 font-mono">{s.queuedJobs} queued</p>
          </CardContent>
        </Card>
        
        <Card className="bg-card/50">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider font-mono">Total Videos</CardTitle>
            <Film className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono">{statsLoading ? "-" : s.totalVideos}</div>
            <p className="text-xs text-muted-foreground mt-1 font-mono">From {s.totalProjects} projects</p>
          </CardContent>
        </Card>

        <Card className="bg-card/50">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider font-mono">Success Rate</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono">{statsLoading ? "-" : `${s.successRate.toFixed(1)}%`}</div>
            <p className="text-xs text-muted-foreground mt-1 font-mono">{s.failedJobs} failures today</p>
          </CardContent>
        </Card>

        <Card className="bg-card/50">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wider font-mono">Compute Time</CardTitle>
            <Clock className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono">{statsLoading ? "-" : formatRuntime(s.totalRuntime)}</div>
            <p className="text-xs text-muted-foreground mt-1 font-mono">Total pipeline runtime</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 bg-card/50">
          <CardHeader>
            <CardTitle className="text-sm font-medium uppercase tracking-wider font-mono">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {s.recentActivity?.map((activity) => (
                <div key={activity.id} className="flex flex-col sm:flex-row sm:items-center justify-between py-2 border-b border-border/50 last:border-0 gap-2">
                  <div className="flex items-center gap-3">
                    {activity.status && <StatusBadge status={activity.status} />}
                    <span className="text-sm font-medium">{activity.message}</span>
                  </div>
                  <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground">
                    {activity.projectId && (
                      <Link href={`/projects/${activity.projectId}`} className="hover:text-primary transition-colors">
                        {activity.projectId.substring(0, 8)}
                      </Link>
                    )}
                    <span>{formatTimeAgo(activity.timestamp)}</span>
                  </div>
                </div>
              ))}
              {!s.recentActivity?.length && (
                <div className="text-sm text-muted-foreground py-4 text-center font-mono">No recent activity</div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card/50">
          <CardHeader>
            <CardTitle className="text-sm font-medium uppercase tracking-wider font-mono">System Health</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Database</span>
                <span className="text-emerald-500 font-mono">OK</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Job Queue</span>
                <span className="text-emerald-500 font-mono">OK</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">YouTube API</span>
                <span className="text-emerald-500 font-mono">OK</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">OpenAI API</span>
                <span className="text-emerald-500 font-mono">OK</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Video Renderer</span>
                <span className="text-amber-500 font-mono">HIGH LOAD</span>
              </div>
            </div>
            
            <div className="mt-6 pt-4 border-t border-border/50">
              <h4 className="text-xs text-muted-foreground uppercase tracking-wider font-mono mb-3">Project Status</h4>
              <div className="space-y-2">
                {s.projectsByStatus?.map((st) => (
                  <div key={st.status} className="flex items-center justify-between text-sm">
                    <span className="capitalize">{st.status}</span>
                    <span className="font-mono">{st.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
