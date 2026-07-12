import { useState } from "react";
import { Link, useLocation } from "wouter";
import { useListProjects, useCreateProject } from "@workspace/api-client-react";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { projectSchema } from "@/lib/schemas";
import { Plus, Search, Video, Clock } from "lucide-react";
import { z } from "zod";
import { Textarea } from "@/components/ui/textarea";

export default function Projects() {
  const [, setLocation] = useLocation();
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  
  const { data: projectsData, isLoading, refetch } = useListProjects({ limit: 100 });
  const createProject = useCreateProject();

  const form = useForm<z.infer<typeof projectSchema>>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      title: "",
      topic: "",
      description: "",
      tags: ""
    }
  });

  const onSubmit = (values: z.infer<typeof projectSchema>) => {
    createProject.mutate({
      data: {
        ...values,
        tags: values.tags ? values.tags.split(",").map(t => t.trim()).filter(Boolean) : []
      }
    }, {
      onSuccess: (newProject) => {
        setDialogOpen(false);
        form.reset();
        refetch();
        setLocation(`/projects/${newProject.id}`);
      }
    });
  };

  // Mock data fallback
  const projects = projectsData?.items || [
    { id: "proj_1a2b", title: "Why AI Agents Will Replace Us", topic: "AI Trends", status: "completed", createdAt: new Date(Date.now() - 86400000 * 2).toISOString() },
    { id: "proj_3c4d", title: "React 19 Features Explained", topic: "Web Development", status: "running", createdAt: new Date(Date.now() - 3600000 * 5).toISOString() },
    { id: "proj_5e6f", title: "Astro vs Next.js Benchmark", topic: "Web Frameworks", status: "queued", createdAt: new Date(Date.now() - 1800000).toISOString() },
    { id: "proj_7g8h", title: "Top 10 VS Code Extensions", topic: "Productivity", status: "failed", createdAt: new Date(Date.now() - 86400000).toISOString() },
    { id: "proj_9i0j", title: "My First Mechanical Keyboard", topic: "Tech Reviews", status: "draft", createdAt: new Date().toISOString() },
  ];

  const filteredProjects = projects.filter(p => 
    p.title.toLowerCase().includes(search.toLowerCase()) || 
    p.topic.toLowerCase().includes(search.toLowerCase()) ||
    p.id.toLowerCase().includes(search.toLowerCase())
  );

  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleDateString(undefined, { 
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' 
    });
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6 flex flex-col h-full">
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-2xl font-bold font-mono tracking-tight">PROJECTS</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage and monitor your automated video pipelines.</p>
        </div>
        
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button className="font-mono text-xs uppercase tracking-wider">
              <Plus className="h-4 w-4 mr-2" />
              New Project
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle className="font-mono uppercase tracking-wider">Create Project</DialogTitle>
            </DialogHeader>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 pt-4">
                <FormField
                  control={form.control}
                  name="title"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Video Title</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. Why AI Agents Will Replace Us" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="topic"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Topic / Core Idea</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. AI, Future of Work" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Description (Optional)</FormLabel>
                      <FormControl>
                        <Textarea 
                          placeholder="Provide context for the AI researcher and script writer..." 
                          className="resize-none" 
                          {...field} 
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="tags"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Tags (Comma separated)</FormLabel>
                      <FormControl>
                        <Input placeholder="tech, ai, tutorial" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="flex justify-end pt-4">
                  <Button type="submit" disabled={createProject.isPending}>
                    {createProject.isPending ? "CREATING..." : "INITIALIZE PROJECT"}
                  </Button>
                </div>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex items-center gap-4 shrink-0">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search projects..."
            className="pl-9 font-mono text-sm bg-card/50"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <Card className="flex-1 overflow-hidden bg-card/50 flex flex-col border-border/50">
        <div className="overflow-auto flex-1">
          <Table>
            <TableHeader className="bg-card sticky top-0 z-10">
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-[120px] font-mono text-xs">ID</TableHead>
                <TableHead className="font-mono text-xs">TITLE / TOPIC</TableHead>
                <TableHead className="font-mono text-xs">STATUS</TableHead>
                <TableHead className="text-right font-mono text-xs">CREATED</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && !projectsData ? (
                Array(5).fill(0).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell><div className="h-4 w-20 bg-muted animate-pulse rounded" /></TableCell>
                    <TableCell><div className="h-4 w-48 bg-muted animate-pulse rounded" /></TableCell>
                    <TableCell><div className="h-4 w-16 bg-muted animate-pulse rounded" /></TableCell>
                    <TableCell><div className="h-4 w-24 bg-muted animate-pulse rounded ml-auto" /></TableCell>
                  </TableRow>
                ))
              ) : filteredProjects.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center py-8 text-muted-foreground font-mono text-sm">
                    No projects found.
                  </TableCell>
                </TableRow>
              ) : (
                filteredProjects.map((project) => (
                  <TableRow 
                    key={project.id} 
                    className="cursor-pointer group"
                    onClick={() => setLocation(`/projects/${project.id}`)}
                  >
                    <TableCell className="font-mono text-xs text-muted-foreground group-hover:text-primary transition-colors">
                      {project.id.substring(0, 8)}
                    </TableCell>
                    <TableCell>
                      <div className="font-medium text-sm group-hover:text-primary transition-colors">{project.title}</div>
                      <div className="text-xs text-muted-foreground mt-0.5">{project.topic}</div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={project.status} />
                    </TableCell>
                    <TableCell className="text-right text-xs font-mono text-muted-foreground flex items-center justify-end gap-2">
                      <Clock className="h-3 w-3" />
                      {formatDate(project.createdAt)}
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
