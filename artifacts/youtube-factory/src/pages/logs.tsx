import { useState, useRef, useEffect } from "react";
import { useListLogs, getListLogsQueryKey } from "@workspace/api-client-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Pause, Play, Download, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";

export default function Logs() {
  const [isPaused, setIsPaused] = useState(false);
  const [level, setLevel] = useState<string>("all");
  const [service, setService] = useState<string>("all");
  const logsEndRef = useRef<HTMLDivElement>(null);
  
  const { data: logsData } = useListLogs(
    { 
      limit: 100, 
      level: level === "all" ? undefined : level,
      service: service === "all" ? undefined : service 
    },
    { query: { queryKey: getListLogsQueryKey({ limit: 100 }), refetchInterval: isPaused ? false : 2000 } }
  );

  // Auto-scroll to bottom unless paused
  useEffect(() => {
    if (!isPaused && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logsData, isPaused]);

  // Mock fallback
  const mockLogs = Array(50).fill(0).map((_, i) => ({
    id: `log_${i}`,
    timestamp: new Date(Date.now() - (50 - i) * 1000).toISOString(),
    level: i % 15 === 0 ? "error" : i % 8 === 0 ? "warn" : i % 3 === 0 ? "debug" : "info",
    service: ["ai_pipeline", "job_worker", "youtube_api"][i % 3],
    message: `[Process ${i}] Handling data segment execution via worker node...`,
    projectId: i % 2 === 0 ? "proj_1a2b" : undefined
  }));

  const logs = logsData?.items || mockLogs;

  const filteredLogs = logs.filter(log => {
    if (level !== "all" && log.level !== level) return false;
    if (service !== "all" && log.service !== service) return false;
    return true;
  });

  const getLogColor = (lvl: string) => {
    switch(lvl) {
      case "error": return "text-red-500";
      case "warn": return "text-amber-500";
      case "debug": return "text-muted-foreground";
      default: return "text-blue-400";
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-4 flex flex-col h-full">
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Terminal className="h-6 w-6 text-muted-foreground" />
          <h1 className="text-2xl font-bold font-mono tracking-tight">SYSTEM LOGS</h1>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="w-[140px]">
            <Select value={level} onValueChange={setLevel}>
              <SelectTrigger className="h-8 font-mono text-xs">
                <SelectValue placeholder="Level" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">ALL LEVELS</SelectItem>
                <SelectItem value="info">INFO</SelectItem>
                <SelectItem value="warn">WARN</SelectItem>
                <SelectItem value="error">ERROR</SelectItem>
                <SelectItem value="debug">DEBUG</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="w-[160px]">
            <Select value={service} onValueChange={setService}>
              <SelectTrigger className="h-8 font-mono text-xs">
                <SelectValue placeholder="Service" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">ALL SERVICES</SelectItem>
                <SelectItem value="ai_pipeline">AI PIPELINE</SelectItem>
                <SelectItem value="job_worker">JOB WORKER</SelectItem>
                <SelectItem value="youtube_api">YOUTUBE API</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button 
            variant="outline" 
            size="sm" 
            className="h-8 font-mono text-xs w-24"
            onClick={() => setIsPaused(!isPaused)}
          >
            {isPaused ? <><Play className="h-3 w-3 mr-1" /> RESUME</> : <><Pause className="h-3 w-3 mr-1" /> PAUSE</>}
          </Button>
        </div>
      </div>

      <Card className="flex-1 bg-black border-border overflow-hidden flex flex-col relative rounded-md">
        <div className="absolute top-0 w-full h-8 bg-gradient-to-b from-black to-transparent pointer-events-none z-10" />
        <div className="flex-1 overflow-y-auto p-4 font-mono text-[11px] leading-relaxed tracking-tight text-gray-300">
          {filteredLogs.map((log) => (
            <div key={log.id} className="flex gap-4 hover:bg-white/5 px-2 py-0.5 rounded -mx-2">
              <div className="text-gray-600 shrink-0 select-none">
                {new Date(log.timestamp).toISOString().split('T')[1].slice(0, -1)}
              </div>
              <div className={cn("uppercase w-12 shrink-0 select-none font-bold", getLogColor(log.level))}>
                {log.level}
              </div>
              <div className="text-gray-500 w-28 shrink-0 select-none truncate">
                [{log.service}]
              </div>
              <div className="flex-1 whitespace-pre-wrap break-all">
                <span className={cn(log.level === 'error' && "text-red-400")}>
                  {log.message}
                </span>
                {log.projectId && (
                  <span className="ml-2 text-blue-400/70 select-none">projectId={log.projectId}</span>
                )}
              </div>
            </div>
          ))}
          {filteredLogs.length === 0 && (
            <div className="text-gray-600 italic">No logs matched the current filters...</div>
          )}
          <div ref={logsEndRef} className="h-4" />
        </div>
        <div className="absolute bottom-0 w-full h-8 bg-gradient-to-t from-black to-transparent pointer-events-none" />
      </Card>
    </div>
  );
}
