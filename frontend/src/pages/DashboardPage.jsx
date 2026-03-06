import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import AppLayout from "../components/AppLayout";
import StatCard from "../components/StatCard";
import AdPreviewCard from "../components/AdPreviewCard";
import { Button } from "@/components/ui/button";
import { api } from "../api";

const COLORS = ["#09090B", "#2563EB", "#16A34A", "#F59E0B", "#EF4444", "#A16207", "#0891B2"];
const RECENCY_OPTIONS = [7, 30, 90];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="rounded-md bg-black px-3 py-2 text-xs text-white" data-testid="chart-tooltip">
      <p className="font-semibold">{label || payload[0].name}</p>
      {payload.map((item) => (
        <p key={`${item.name}-${item.value}`}>
          {item.name}: {item.value}
        </p>
      ))}
    </div>
  );
};

export default function DashboardPage() {
  const [recency, setRecency] = useState(90);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = async () => {
    setLoading(true);
    try {
      const result = await api.getDashboardAnalytics(recency);
      setAnalytics(result);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, [recency]);

  const summary = analytics?.summary;
  const kpis = summary?.kpis;

  const topAdCards = useMemo(() => summary?.longest_running_ads?.slice(0, 4) || [], [summary]);

  return (
    <AppLayout
      title="Competitor Pulse Dashboard"
      subtitle="Track live ad behavior, discover creative trends, and spot strategic whitespace across D2C competitors."
    >
      <div className="mb-6 flex flex-wrap items-center gap-2" data-testid="dashboard-recency-controls">
        {RECENCY_OPTIONS.map((option) => (
          <Button
            key={option}
            variant={recency === option ? "default" : "outline"}
            onClick={() => setRecency(option)}
            data-testid={`recency-${option}-button`}
          >
            Last {option} days
          </Button>
        ))}
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" data-testid="dashboard-loading-grid">
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className="h-32 animate-pulse rounded-lg border border-border bg-card" data-testid={`dashboard-skeleton-${item}`} />
          ))}
        </div>
      ) : (
        <>
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" data-testid="kpi-section">
            <StatCard label="Total ads tracked" value={kpis?.total_ads || 0} testId="kpi-total-ads" />
            <StatCard label="Active ads" value={kpis?.active_ads || 0} testId="kpi-active-ads" />
            <StatCard label="Tracked brands" value={kpis?.tracked_brands || 0} testId="kpi-tracked-brands" />
            <StatCard
              label="Average ad longevity"
              value={`${kpis?.avg_longevity_days || 0} days`}
              testId="kpi-longevity"
            />
          </section>

          <section className="mt-8 grid gap-4 xl:grid-cols-4">
            <div className="stagger-item interactive-card rounded-lg border border-border bg-card p-5 xl:col-span-2" data-testid="activity-chart-card">
              <h3 className="text-base font-semibold md:text-lg" data-testid="activity-chart-title">
                Ad activity over time
              </h3>
              <div className="mt-4 h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={summary?.ad_activity_over_time || []}>
                    <CartesianGrid strokeDasharray="2 2" stroke="#E4E4E7" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Line type="monotone" dataKey="ads_started" stroke="#2563EB" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="stagger-item interactive-card rounded-lg border border-border bg-card p-5" data-testid="active-advertisers-chart-card">
              <h3 className="text-base font-semibold md:text-lg" data-testid="active-advertisers-chart-title">
                Most active advertisers
              </h3>
              <div className="mt-4 h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={summary?.most_active_advertisers || []} layout="vertical" margin={{ left: 10, right: 10 }}>
                    <XAxis type="number" hide />
                    <YAxis dataKey="brand_name" type="category" width={110} tick={{ fontSize: 11 }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="count" fill="#09090B" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="stagger-item interactive-card rounded-lg border border-border bg-card p-5" data-testid="format-distribution-chart-card">
              <h3 className="text-base font-semibold md:text-lg" data-testid="format-distribution-chart-title">
                Format distribution
              </h3>
              <div className="mt-4 h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={summary?.format_distribution || []}
                      dataKey="count"
                      nameKey="name"
                      outerRadius={90}
                      innerRadius={50}
                    >
                      {(summary?.format_distribution || []).map((entry, index) => (
                        <Cell key={`format-${entry.name}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                    <Legend iconSize={10} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="stagger-item interactive-card rounded-lg border border-border bg-card p-5 xl:col-span-2" data-testid="theme-distribution-chart-card">
              <h3 className="text-base font-semibold md:text-lg" data-testid="theme-distribution-chart-title">
                Message theme distribution
              </h3>
              <div className="mt-4 h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={summary?.theme_distribution || []}>
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-15} textAnchor="end" height={58} />
                    <YAxis allowDecimals={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="count" fill="#2563EB" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </section>

          <section className="mt-8" data-testid="top-long-running-ads-section">
            <h3 className="mb-4 text-base font-semibold md:text-lg" data-testid="top-long-running-ads-title">
              Longest running ads
            </h3>
            {topAdCards.length ? (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" data-testid="top-ads-grid">
                {topAdCards.map((ad) => (
                  <AdPreviewCard key={ad.ad_archive_id} ad={ad} testId={`top-ad-${ad.ad_archive_id}`} />
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground" data-testid="top-ads-empty-state">
                No ads available yet. Click Sync Now to fetch competitor campaigns.
              </div>
            )}
          </section>
        </>
      )}
    </AppLayout>
  );
}
