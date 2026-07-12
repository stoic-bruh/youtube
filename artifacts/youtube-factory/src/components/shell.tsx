import { Link, useLocation } from "wouter";
import { Activity, LayoutDashboard, ListTree, Settings, Terminal, Video } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: Video },
  { href: "/pipelines", label: "Pipelines", icon: Activity },
  { href: "/jobs", label: "Job Queue", icon: ListTree },
  { href: "/logs", label: "System Logs", icon: Terminal },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const [location] = useLocation();

  return (
    <div className="w-64 border-r border-border bg-sidebar flex-shrink-0 flex flex-col hidden md:flex">
      <div className="h-14 flex items-center px-4 border-b border-border">
        <h1 className="text-sm font-bold font-mono tracking-tight text-primary flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-destructive animate-pulse-running" />
          YOUTUBE_FACTORY
        </h1>
      </div>
      <nav className="flex-1 overflow-y-auto py-4">
        <ul className="space-y-1 px-2">
          {navItems.map((item) => {
            const isActive = location === item.href || (item.href !== "/" && location.startsWith(item.href));
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                    isActive 
                      ? "bg-accent text-accent-foreground" 
                      : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="p-4 border-t border-border">
        <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider">
          System Status
        </div>
        <div className="mt-2 flex items-center gap-2 text-xs">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          <span className="text-emerald-500 font-mono">ONLINE</span>
        </div>
      </div>
    </div>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col md:flex-row">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0 h-screen overflow-y-auto relative">
        {children}
      </main>
    </div>
  );
}
