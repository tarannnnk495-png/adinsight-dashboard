import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import AppLayout from "../components/AppLayout";
import { Button } from "@/components/ui/button";
import { api } from "../api";

const ListBlock = ({ title, items, testId }) => (
  <div className="interactive-card rounded-lg border border-border bg-card p-5" data-testid={`${testId}-card`}>
    <h3 className="text-base font-semibold md:text-lg" data-testid={`${testId}-title`}>
      {title}
    </h3>
    <ul className="mt-3 space-y-2 text-sm" data-testid={`${testId}-list`}>
      {(items || []).map((item, index) => (
        <li
          key={`${testId}-${index}`}
          className="rounded-md border border-border bg-muted/40 px-3 py-2"
          data-testid={`${testId}-item-${index}`}
        >
          {typeof item === "string" ? item : `${item.ad_archive_id}: ${item.reason}`}
        </li>
      ))}
      {!items?.length ? (
        <li className="rounded-md border border-dashed border-border px-3 py-2 text-muted-foreground" data-testid={`${testId}-empty`}>
          No insights available yet.
        </li>
      ) : null}
    </ul>
  </div>
);

export default function InsightsPage() {
  const [insights, setInsights] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [syncState, setSyncState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const fetchSyncStatus = async () => {
    try {
      const status = await api.getSyncStatus();
      setSyncState(status?.sync_state || null);
    } catch (error) {
      console.error(error);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const [latestInsights, dashboard, syncStatus] = await Promise.all([
        api.getLatestInsights(),
        api.getDashboardAnalytics(90),
        api.getSyncStatus(),
      ]);
      setInsights(latestInsights?.weekly_brief ? latestInsights : null);
      setAnalytics(dashboard);
      setSyncState(syncStatus?.sync_state || null);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const onGenerateInsights = async () => {
    if (syncState?.running) {
      toast.info("Sync is in progress. Please generate insights once sync completes.");
      return;
    }

    setGenerating(true);
    try {
      const result = await api.generateInsights(90);
      setInsights(result);
      toast.success("AI insights generated successfully.");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Failed to generate AI insights.");
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    fetchData();

    const interval = setInterval(fetchSyncStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <AppLayout
      title="AI Insights & Gap Detection"
      subtitle="Generate weekly strategic briefs, detect whitespace in creative strategy, and convert observations into actions."
    >
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3" data-testid="insights-header-controls">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground" data-testid="insights-last-updated">
            {insights?.created_at
              ? `Last brief generated at ${new Date(insights.created_at).toLocaleString()}`
              : "No brief generated yet"}
          </p>
          {syncState?.running ? (
            <p className="text-xs font-medium text-amber-600" data-testid="insights-sync-warning">
              Sync is currently running. AI brief generation will unlock after sync.
            </p>
          ) : null}
        </div>
        <Button
          onClick={onGenerateInsights}
          disabled={generating || syncState?.running}
          data-testid="generate-insights-button"
        >
          <Sparkles className="mr-2 h-4 w-4" />
          {syncState?.running ? "Sync in progress" : generating ? "Generating..." : "Generate AI Brief"}
        </Button>
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2" data-testid="insights-loading-grid">
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className="h-40 animate-pulse rounded-lg border border-border bg-card" data-testid={`insights-skeleton-${item}`} />
          ))}
        </div>
      ) : (
        <>
          <div className="interactive-card rounded-lg border border-border bg-card p-5" data-testid="weekly-brief-card">
            <h3 className="text-base font-semibold md:text-lg" data-testid="weekly-brief-title">
              Weekly AI Brief
            </h3>
            <p className="mt-3 whitespace-pre-line text-sm leading-7 text-foreground" data-testid="weekly-brief-text">
              {insights?.weekly_brief ||
                "Generate the first AI brief to summarize creative trends, long-running ads, and opportunities."}
            </p>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <ListBlock title="Major creative trends" items={insights?.creative_trends} testId="creative-trends" />
            <ListBlock title="Messaging shifts" items={insights?.messaging_shifts} testId="messaging-shifts" />
            <ListBlock title="Likely top performers" items={insights?.top_long_running_ads} testId="top-performers" />
            <ListBlock title="Gap opportunities" items={insights?.gap_opportunities} testId="gap-opportunities" />
          </div>

          <div className="mt-6 rounded-lg border border-border bg-card p-5" data-testid="gap-detection-data-card">
            <h3 className="text-base font-semibold md:text-lg" data-testid="gap-detection-title">
              Data-driven gap detection
            </h3>
            <div className="mt-3 grid gap-4 md:grid-cols-2">
              <div data-testid="underused-formats-block">
                <p className="text-sm font-semibold text-muted-foreground" data-testid="underused-formats-title">
                  Underused ad formats
                </p>
                <ul className="mt-2 space-y-2 text-sm" data-testid="underused-formats-list">
                  {(analytics?.gap_detection?.underused_formats || []).map((item, index) => (
                    <li key={`${item.name}-${index}`} className="rounded-md border border-border bg-muted/40 px-3 py-2" data-testid={`underused-format-item-${index}`}>
                      {item.name} · {item.share_percent}% share
                    </li>
                  ))}
                </ul>
              </div>

              <div data-testid="underused-themes-block">
                <p className="text-sm font-semibold text-muted-foreground" data-testid="underused-themes-title">
                  Underused message themes
                </p>
                <ul className="mt-2 space-y-2 text-sm" data-testid="underused-themes-list">
                  {(analytics?.gap_detection?.underused_themes || []).map((item, index) => (
                    <li key={`${item.name}-${index}`} className="rounded-md border border-border bg-muted/40 px-3 py-2" data-testid={`underused-theme-item-${index}`}>
                      {item.name} · {item.share_percent}% share
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </>
      )}
    </AppLayout>
  );
}
