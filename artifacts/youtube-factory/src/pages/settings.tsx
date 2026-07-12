import { useGetSettings, useUpdateSettings } from "@workspace/api-client-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Youtube, Key, Server, Settings2 } from "lucide-react";
import { useState, useEffect } from "react";
import { useToast } from "@/hooks/use-toast";

export default function SettingsPage() {
  const { data: settingsData, isLoading } = useGetSettings();
  const updateSettings = useUpdateSettings();
  const { toast } = useToast();

  const defaultSettings = {
    youtubeEnabled: true,
    autoUpload: false,
    defaultLanguage: "en-US",
    maxConcurrentJobs: 3,
    openaiModel: "gpt-4o",
    imageProvider: "midjourney",
    voiceProvider: "elevenlabs",
    defaultVideoQuality: "1080p",
    webhookUrl: ""
  };

  const [formData, setFormData] = useState(defaultSettings);

  useEffect(() => {
    if (settingsData) {
      setFormData({
        ...defaultSettings,
        ...settingsData
      });
    }
  }, [settingsData]);

  const handleSave = () => {
    updateSettings.mutate({ data: formData }, {
      onSuccess: () => {
        toast({
          title: "SETTINGS SAVED",
          description: "System configuration updated successfully.",
          className: "font-mono bg-card text-card-foreground border-border",
        });
      }
    });
  };

  if (isLoading && !settingsData) return <div className="p-6 text-center font-mono">LOADING CONFIGURATION...</div>;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6 flex flex-col h-full overflow-y-auto">
      <div>
        <h1 className="text-2xl font-bold font-mono tracking-tight flex items-center gap-2">
          <Settings2 className="h-6 w-6" /> SYSTEM CONFIGURATION
        </h1>
        <p className="text-sm text-muted-foreground mt-1">Configure external API integrations and pipeline defaults.</p>
      </div>

      <div className="grid gap-6">
        <Card className="bg-card/50 border-border/50">
          <CardHeader>
            <CardTitle className="text-sm font-medium uppercase tracking-wider font-mono flex items-center gap-2">
              <Youtube className="h-4 w-4 text-red-500" />
              YouTube Integration
            </CardTitle>
            <CardDescription className="font-sans">Configure how videos are published.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label className="font-mono text-sm">Enable YouTube Output</Label>
                <p className="text-xs text-muted-foreground">Allows pipelines to target YouTube</p>
              </div>
              <Switch 
                checked={formData.youtubeEnabled} 
                onCheckedChange={(c) => setFormData(p => ({...p, youtubeEnabled: c}))} 
              />
            </div>
            
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label className="font-mono text-sm">Auto-Upload to Channel</Label>
                <p className="text-xs text-muted-foreground">Publish immediately vs saving as draft</p>
              </div>
              <Switch 
                checked={formData.autoUpload} 
                onCheckedChange={(c) => setFormData(p => ({...p, autoUpload: c}))} 
                disabled={!formData.youtubeEnabled}
              />
            </div>

            <div className="space-y-2">
              <Label className="font-mono text-sm">Default Video Quality</Label>
              <Select 
                value={formData.defaultVideoQuality} 
                onValueChange={(v) => setFormData(p => ({...p, defaultVideoQuality: v}))}
              >
                <SelectTrigger className="font-mono">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="720p">720p HD</SelectItem>
                  <SelectItem value="1080p">1080p Full HD</SelectItem>
                  <SelectItem value="4k">4K Ultra HD</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card/50 border-border/50">
          <CardHeader>
            <CardTitle className="text-sm font-medium uppercase tracking-wider font-mono flex items-center gap-2">
              <Server className="h-4 w-4 text-blue-500" />
              Pipeline Limits
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label className="font-mono text-sm">Max Concurrent Jobs</Label>
              <div className="flex items-center gap-4">
                <input 
                  type="range" 
                  min="1" 
                  max="10" 
                  value={formData.maxConcurrentJobs}
                  onChange={(e) => setFormData(p => ({...p, maxConcurrentJobs: parseInt(e.target.value)}))}
                  className="flex-1 accent-primary"
                />
                <span className="font-mono text-lg font-bold w-8 text-center">{formData.maxConcurrentJobs}</span>
              </div>
            </div>

            <div className="space-y-2">
              <Label className="font-mono text-sm">Webhook Notification URL</Label>
              <Input 
                placeholder="https://your-server.com/webhook" 
                className="font-mono"
                value={formData.webhookUrl || ""}
                onChange={(e) => setFormData(p => ({...p, webhookUrl: e.target.value}))}
              />
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Fires on pipeline complete/fail</p>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card/50 border-border/50">
          <CardHeader>
            <CardTitle className="text-sm font-medium uppercase tracking-wider font-mono flex items-center gap-2">
              <Key className="h-4 w-4 text-emerald-500" />
              AI Providers
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label className="font-mono text-sm">Text Model</Label>
              <Select 
                value={formData.openaiModel} 
                onValueChange={(v) => setFormData(p => ({...p, openaiModel: v}))}
              >
                <SelectTrigger className="font-mono text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gpt-4o">OpenAI GPT-4o</SelectItem>
                  <SelectItem value="claude-3.5-sonnet">Claude 3.5 Sonnet</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="font-mono text-sm">Image Generator</Label>
              <Select 
                value={formData.imageProvider} 
                onValueChange={(v) => setFormData(p => ({...p, imageProvider: v}))}
              >
                <SelectTrigger className="font-mono text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="midjourney">Midjourney</SelectItem>
                  <SelectItem value="dalle3">DALL-E 3</SelectItem>
                  <SelectItem value="stable-diffusion">Stable Diffusion</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="font-mono text-sm">Voice Synthesis</Label>
              <Select 
                value={formData.voiceProvider} 
                onValueChange={(v) => setFormData(p => ({...p, voiceProvider: v}))}
              >
                <SelectTrigger className="font-mono text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="elevenlabs">ElevenLabs</SelectItem>
                  <SelectItem value="openai">OpenAI TTS</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end pt-4 pb-8">
          <Button 
            onClick={handleSave} 
            disabled={updateSettings.isPending}
            className="font-mono uppercase tracking-wider px-8"
          >
            {updateSettings.isPending ? "SAVING..." : "SAVE CONFIGURATION"}
          </Button>
        </div>
      </div>
    </div>
  );
}
