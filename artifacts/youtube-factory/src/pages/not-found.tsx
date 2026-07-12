import { Card, CardContent } from "@/components/ui/card";
import { AlertCircle } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-background text-foreground p-4">
      <Card className="w-full max-w-md bg-card border-border shadow-lg">
        <CardContent className="pt-6 text-center space-y-4">
          <div className="flex justify-center mb-4">
            <AlertCircle className="h-12 w-12 text-destructive" />
          </div>
          <h1 className="text-2xl font-bold font-mono tracking-tight text-foreground">
            404 NOT FOUND
          </h1>
          <p className="text-sm font-mono text-muted-foreground">
            The requested resource was not found on this server.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
