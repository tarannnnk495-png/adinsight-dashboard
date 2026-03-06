import { useEffect, useMemo, useState } from "react";
import { NavLink } from "react-router-dom";
import { BarChart3, Brain, RefreshCw, Search } from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "../api";

const navItems = [
  { to: "/", label: "Dashboard", icon: BarChart3 },
  { to: "/explorer", label: "Ad Explorer", icon: Search },
  { to: "/insights", label: "AI Insights", icon: Brain },
];

const getSyncLabel = (syncState) => {
  if (!syncState) return "Not synced yet";
  if (syncState.running) {
    return `Scanning ${syncState.scanned_brands}/${syncState.total_brands} brands...`;
  }
  if (syncState.last_completed_at) return "Last sync complete";
  return "Ready to sync";
};

export default function AppLayout({ title, subtitle, children }) {
  const [syncState, setSyncState] = useState(null);
  const [syncBusy, setSyncBusy] = useState(false);

  const syncLabel = useMemo(() => getSyncLabel(syncState), [syncState]);

  const fetchStatus = async () => {
    try {
      const result = await api.getSyncStatus();
      setSyncState(result.sync_state);
    } catch (error) {
      console.error(error);
    }
  };

  const onSyncNow = async () => {
    setSyncBusy(true);
    try {
      const result = await api.triggerSync(20);
      if (result.status === "already_running") {
        toast.info("Sync is already running.");
      } else {
        toast.success("Sync started. Ads are being fetched now.");
      }
      await fetchStatus();
    } catch (error) {
      toast.error("Failed to start sync.");
    } finally {
      setSyncBusy(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col lg:flex-row">
        <aside className="w-full border-b border-border bg-card px-4 py-5 lg:sticky lg:top-0 lg:h-screen lg:w-64 lg:border-b-0 lg:border-r">
          <div className="mb-6 flex items-center justify-between lg:block">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground" data-testid="brand-app-label">
                AdInsight
              </p>
              <h1 className="mt-1 text-2xl font-bold tracking-tight text-foreground" data-testid="brand-app-heading">
                Strategy Lens
              </h1>
            </div>
          </div>

          <nav className="flex flex-row gap-2 overflow-x-auto pb-1 lg:flex-col" data-testid="primary-navigation">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  data-testid={`nav-link-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
                  className={({ isActive }) =>
                    `interactive-card flex min-w-fit items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                      isActive
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-card text-foreground hover:bg-muted"
                    }`
                  }
                >
                  <Icon size={16} />
                  {item.label}
                </NavLink>
              );
            })}
          </nav>

          <div className="mt-7 rounded-lg border border-border bg-muted p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground" data-testid="sync-status-label">
              Sync status
            </p>
            <p className="mt-2 text-sm font-medium" data-testid="sync-status-value">
              {syncLabel}
            </p>
            <Button
              className="mt-3 w-full"
              onClick={onSyncNow}
              disabled={syncBusy || syncState?.running}
              data-testid="sync-now-button"
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              {syncState?.running ? "Syncing..." : "Sync Now"}
            </Button>
          </div>
        </aside>

        <main className="w-full p-4 md:p-6 lg:p-8">
          <motion.div
            className="page-enter"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
          >
            <header className="mb-8 border-b border-border pb-5">
              <h2 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl lg:text-6xl" data-testid="page-title">
                {title}
              </h2>
              <p className="mt-3 max-w-3xl text-base text-muted-foreground md:text-lg" data-testid="page-subtitle">
                {subtitle}
              </p>
            </header>
            {children}
          </motion.div>
        </main>
      </div>
    </div>
  );
}
