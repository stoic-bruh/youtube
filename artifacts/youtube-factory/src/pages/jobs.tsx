import { useState } from "react";
import { useListJobs, useRetryJob, useCancelJob, getListJobsQueryKey } from "@workspace/api-client-react";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, RefreshCw, XCircle, RotateCcw } from "lucide-react";
import { Link } from "wouter";

export default function Jobs() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  
  const { data: jobsData, isLoading, refetch } = useListJobs(
    { limit: 100, status: statusFilter === "all" ? undefined : statusFilter },
    { query: { queryKey: getListJobsQueryKey({ limit: 50 }), refetchInterval: 5000 } }
  );

  const retryJob = useRetryJob();
  const cancelJob = useCancelJob();

  // Mock fallback
  const jobs = jobsData?.items || [
    { id: "job_101", type: "generate_script", status: "running", projectId: "proj_1a2b", retryCount: 0, createdAt: new Date(Date.now()-10000).toISOString() },
    { id: "job_102", type: "generate_image", status: "failed", projectId: "proj_3c4d", retryCount: 2, error: "API timeout", createdAt: new Date(Date.now()-3600000).toISOString() },
    { id: "job_103", type: "edit_video", status: "pending", projectId: "proj_5e6f", retryCount: 0, createdAt: new Date(Date.now()-50000).toISOString() },
    { id: "job_104", type: "upload_youtube", status: "completed", projectId: "proj_7g8h", retryCount: 0, createdAt: new Date(Date.now()-86400000).toISOString() },
    { id: "job_105", type: "generate_voice", status: "retrying", projectId: "proj_1a2b", retryCount: 1, createdAt: new Date(Date.now()-200000).toISOString() },
  ];

  const filteredJobs = jobs.filter(j => 
    j.type.toLowerCase().includes(search.toLowerCase()) || 
    j.id.toLowerCase().includes(search.toLowerCase()) ||
    (j.projectId && j.projectId.toLowerCase().includes(search.toLowerCase()))
  );

  const handleRetry = (id: string) => {
    retryJob.mutate({ id }, { onSuccess: () => refetch() });
  };

  const handleCancel = (id: string) => {
    cancelJob.mutate({ id }, { onSuccess: () => refetch() });
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6 flex flex-col h-full">
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-2xl font-bold font-mono tracking-tight">BACKGROUND JOBS</h1>
          <p className="text-sm text-muted-foreground mt-1">Queue management for individual AI tasks.</p>
        </div>
      </div>

      <div className="flex items-center gap-4 shrink-0">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search job ID, type, or project..."
            className="pl-9 font-mono text-sm bg-card/50"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="w-[180px]">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="font-mono text-xs">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">ALL STATUSES</SelectItem>
              <SelectItem value="pending">PENDING</SelectItem>
              <SelectItem value="running">RUNNING</SelectItem>
              <SelectItem value="failed">FAILED</SelectItem>
              <SelectItem value="completed">COMPLETED</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button variant="outline" size="icon" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      <Card className="flex-1 overflow-hidden bg-card/50 flex flex-col border-border/50">
        <div className="overflow-auto flex-1">
          <Table>
            <TableHeader className="bg-card sticky top-0 z-10">
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-[100px] font-mono text-xs">JOB ID</TableHead>
                <TableHead className="w-[180px] font-mono text-xs">TYPE</TableHead>
                <TableHead className="w-[120px] font-mono text-xs">PROJECT</TableHead>
                <TableHead className="w-[100px] font-mono text-xs">STATUS</TableHead>
                <TableHead className="w-[80px] text-center font-mono text-xs">RETRY</TableHead>
                <TableHead className="text-right font-mono text-xs">ACTIONS</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && !jobsData ? (
                Array(5).fill(0).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell><div className="h-4 w-16 bg-muted animate-pulse rounded" /></TableCell>
                    <TableCell><div className="h-4 w-32 bg-muted animate-pulse rounded" /></TableCell>
                    <TableCell><div className="h-4 w-20 bg-muted animate-pulse rounded" /></TableCell>
                    <TableCell><div className="h-4 w-16 bg-muted animate-pulse rounded" /></TableCell>
                    <TableCell><div className="h-4 w-8 bg-muted animate-pulse rounded mx-auto" /></TableCell>
                    <TableCell><div className="h-6 w-16 bg-muted animate-pulse rounded ml-auto" /></TableCell>
                  </TableRow>
                ))
              ) : filteredJobs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground font-mono text-sm">
                    No jobs found in queue.
                  </TableCell>
                </TableRow>
              ) : (
                filteredJobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {job.id.substring(0, 8)}
                    </TableCell>
                    <TableCell className="font-mono text-xs uppercase tracking-tight text-primary">
                      {job.type.replace(/_/g, ' ')}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {job.projectId ? (
                        <Link href={`/projects/${job.projectId}`} className="text-blue-400 hover:underline">
                          {job.projectId.substring(0, 8)}
                        </Link>
                      ) : "-"}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={job.status} />
                    </TableCell>
                    <TableCell className="text-center font-mono text-xs text-muted-foreground">
                      {job.retryCount || 0}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        {job.status === 'failed' && (
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className="h-7 text-xs font-mono px-2"
                            onClick={() => handleRetry(job.id)}
                            disabled={retryJob.isPending}
                          >
                            <RotateCcw className="h-3 w-3 mr-1" />
                            RETRY
                          </Button>
                        )}
                        {(job.status === 'pending' || job.status === 'running') && (
                          <Button 
                            variant="destructive" 
                            size="sm" 
                            className="h-7 text-xs font-mono px-2 bg-destructive/20 text-destructive hover:bg-destructive hover:text-destructive-foreground border-0"
                            onClick={() => handleCancel(job.id)}
                            disabled={cancelJob.isPending}
                          >
                            <XCircle className="h-3 w-3 mr-1" />
                            CANCEL
                          </Button>
                        )}
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
