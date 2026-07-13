import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import NotFound from '@/pages/not-found';
import { Route, Switch, Router as WouterRouter } from 'wouter';

import { Shell } from '@/components/shell';
import Dashboard from '@/pages/dashboard';
import Projects from '@/pages/projects';
import ProjectDetail from '@/pages/project-detail';
import Pipelines from '@/pages/pipelines';
import Jobs from '@/pages/jobs';
import Logs from '@/pages/logs';
import SettingsPage from '@/pages/settings';
import ResearchPage from '@/pages/research';
import ScriptsPage from '@/pages/scripts';
import StoryboardsPage from '@/pages/storyboards';
import AssetsPage from '@/pages/assets';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

function Router() {
  return (
    <Shell>
      <Switch>
        <Route path="/" component={Dashboard} />
        <Route path="/research" component={ResearchPage} />
        <Route path="/scripts" component={ScriptsPage} />
        <Route path="/storyboards" component={StoryboardsPage} />
        <Route path="/assets" component={AssetsPage} />
        <Route path="/projects" component={Projects} />
        <Route path="/projects/:id" component={ProjectDetail} />
        <Route path="/pipelines" component={Pipelines} />
        <Route path="/jobs" component={Jobs} />
        <Route path="/logs" component={Logs} />
        <Route path="/settings" component={SettingsPage} />
        <Route component={NotFound} />
      </Switch>
    </Shell>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Router />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
