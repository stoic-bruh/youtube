import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function StatusBadge({ status, className }: { status: string, className?: string }) {
  const normalizedStatus = status.toLowerCase();
  
  let variantClass = "bg-status-draft";
  
  if (["running", "active"].includes(normalizedStatus)) {
    variantClass = "bg-status-running animate-pulse-running";
  } else if (["failed", "error", "cancelled"].includes(normalizedStatus)) {
    variantClass = "bg-status-failed";
  } else if (["queued", "pending", "retrying"].includes(normalizedStatus)) {
    variantClass = "bg-status-queued";
  } else if (["completed", "success"].includes(normalizedStatus)) {
    variantClass = "bg-status-completed";
  }

  return (
    <Badge 
      variant="outline" 
      className={cn(
        "font-mono text-[10px] uppercase tracking-wider rounded-sm px-1.5 py-0.5 border-0", 
        variantClass,
        className
      )}
    >
      {status}
    </Badge>
  );
}
