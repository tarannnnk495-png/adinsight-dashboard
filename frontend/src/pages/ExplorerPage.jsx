import { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import AppLayout from "../components/AppLayout";
import AdPreviewCard from "../components/AdPreviewCard";
import { api } from "../api";
import { Button } from "@/components/ui/button";

const THEMES = [
  "UGC testimonial",
  "doctor/expert authority",
  "before and after results",
  "product education",
  "problem/solution",
  "lifestyle branding",
  "discount/promotion",
];

const FORMATS = ["image", "video", "carousel", "unknown"];

const formatDate = (value) => {
  try {
    return format(new Date(value), "MMM dd, yyyy");
  } catch {
    return value;
  }
};

export default function ExplorerPage() {
  const [competitors, setCompetitors] = useState([]);
  const [ads, setAds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    brand: "",
    ad_format: "",
    message_theme: "",
    recency_days: 90,
    sort_by: "ad_start_date",
    sort_order: "desc",
  });

  const fetchCompetitors = async () => {
    try {
      const result = await api.getCompetitors();
      setCompetitors(result.competitors || []);
    } catch (error) {
      console.error(error);
    }
  };

  const fetchAds = async () => {
    setLoading(true);
    try {
      const result = await api.getAds(filters);
      setAds(result.items || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCompetitors();
  }, []);

  useEffect(() => {
    fetchAds();
  }, [filters]);

  const previewAds = useMemo(() => ads.slice(0, 8), [ads]);

  return (
    <AppLayout
      title="Ad Explorer"
      subtitle="Filter and audit every tracked ad by brand, format, message theme, and recency window."
    >
      <div className="grid gap-6 xl:grid-cols-[280px_1fr]">
        <aside className="interactive-card h-fit rounded-lg border border-border bg-card p-4 xl:sticky xl:top-6" data-testid="explorer-filter-sidebar">
          <h3 className="text-base font-semibold md:text-lg" data-testid="explorer-filter-title">
            Filters
          </h3>

          <label className="mt-4 block text-sm font-medium text-muted-foreground" htmlFor="brand-filter" data-testid="brand-filter-label">
            Brand
          </label>
          <select
            id="brand-filter"
            className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={filters.brand}
            onChange={(event) => setFilters((prev) => ({ ...prev, brand: event.target.value }))}
            data-testid="brand-filter-select"
          >
            <option value="">All brands</option>
            {competitors.map((brand) => (
              <option key={brand} value={brand}>
                {brand}
              </option>
            ))}
          </select>

          <label className="mt-4 block text-sm font-medium text-muted-foreground" htmlFor="format-filter" data-testid="format-filter-label">
            Ad format
          </label>
          <select
            id="format-filter"
            className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={filters.ad_format}
            onChange={(event) => setFilters((prev) => ({ ...prev, ad_format: event.target.value }))}
            data-testid="format-filter-select"
          >
            <option value="">All formats</option>
            {FORMATS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>

          <label className="mt-4 block text-sm font-medium text-muted-foreground" htmlFor="theme-filter" data-testid="theme-filter-label">
            Message theme
          </label>
          <select
            id="theme-filter"
            className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={filters.message_theme}
            onChange={(event) => setFilters((prev) => ({ ...prev, message_theme: event.target.value }))}
            data-testid="theme-filter-select"
          >
            <option value="">All themes</option>
            {THEMES.map((theme) => (
              <option key={theme} value={theme}>
                {theme}
              </option>
            ))}
          </select>

          <label className="mt-4 block text-sm font-medium text-muted-foreground" htmlFor="recency-filter" data-testid="recency-filter-label">
            Recency window
          </label>
          <select
            id="recency-filter"
            className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={filters.recency_days}
            onChange={(event) => setFilters((prev) => ({ ...prev, recency_days: Number(event.target.value) }))}
            data-testid="recency-filter-select"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>

          <label className="mt-4 block text-sm font-medium text-muted-foreground" htmlFor="sort-filter" data-testid="sort-filter-label">
            Sort by
          </label>
          <select
            id="sort-filter"
            className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={`${filters.sort_by}:${filters.sort_order}`}
            onChange={(event) => {
              const [sortBy, sortOrder] = event.target.value.split(":");
              setFilters((prev) => ({ ...prev, sort_by: sortBy, sort_order: sortOrder }));
            }}
            data-testid="sort-filter-select"
          >
            <option value="ad_start_date:desc">Newest first</option>
            <option value="ad_start_date:asc">Oldest first</option>
            <option value="ad_longevity_days:desc">Longest running first</option>
            <option value="brand_name:asc">Brand A-Z</option>
          </select>

          <Button
            variant="outline"
            className="mt-5 w-full"
            onClick={() =>
              setFilters({
                brand: "",
                ad_format: "",
                message_theme: "",
                recency_days: 90,
                sort_by: "ad_start_date",
                sort_order: "desc",
              })
            }
            data-testid="reset-filters-button"
          >
            Reset filters
          </Button>
        </aside>

        <section>
          <div className="mb-4 flex items-center justify-between" data-testid="explorer-results-header">
            <h3 className="text-base font-semibold md:text-lg" data-testid="explorer-results-title">
              Matching ads
            </h3>
            <p className="mono-data text-sm text-muted-foreground" data-testid="explorer-results-count">
              {ads.length} ads
            </p>
          </div>

          {loading ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" data-testid="explorer-loading-grid">
              {[1, 2, 3, 4].map((item) => (
                <div key={item} className="h-72 animate-pulse rounded-lg border border-border bg-card" data-testid={`explorer-skeleton-${item}`} />
              ))}
            </div>
          ) : (
            <>
              {previewAds.length ? (
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" data-testid="explorer-cards-grid">
                  {previewAds.map((ad) => (
                    <AdPreviewCard key={ad.ad_archive_id} ad={ad} testId={`explorer-ad-${ad.ad_archive_id}`} />
                  ))}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground" data-testid="explorer-empty-state">
                  No matching ads found for current filters.
                </div>
              )}

              <div className="mt-6 overflow-x-auto rounded-lg border border-border bg-card" data-testid="ad-table-wrapper">
                <table className="w-full min-w-[940px] text-left text-sm" data-testid="ad-table">
                  <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground" data-testid="ad-table-head">
                    <tr>
                      <th className="px-4 py-3" data-testid="ad-table-header-brand">Brand</th>
                      <th className="px-4 py-3" data-testid="ad-table-header-format">Format</th>
                      <th className="px-4 py-3" data-testid="ad-table-header-theme">Theme</th>
                      <th className="px-4 py-3" data-testid="ad-table-header-platform">Platform</th>
                      <th className="px-4 py-3" data-testid="ad-table-header-start">Start date</th>
                      <th className="px-4 py-3" data-testid="ad-table-header-longevity">Longevity</th>
                      <th className="px-4 py-3" data-testid="ad-table-header-status">Status</th>
                    </tr>
                  </thead>
                  <tbody data-testid="ad-table-body">
                    {ads.map((ad) => (
                      <tr key={ad.ad_archive_id} className="border-t border-border" data-testid={`ad-table-row-${ad.ad_archive_id}`}>
                        <td className="px-4 py-3" data-testid={`ad-table-brand-${ad.ad_archive_id}`}>{ad.brand_name}</td>
                        <td className="px-4 py-3" data-testid={`ad-table-format-${ad.ad_archive_id}`}>{ad.ad_format}</td>
                        <td className="px-4 py-3" data-testid={`ad-table-theme-${ad.ad_archive_id}`}>{ad.message_theme}</td>
                        <td className="px-4 py-3" data-testid={`ad-table-platform-${ad.ad_archive_id}`}>{ad.platform}</td>
                        <td className="px-4 py-3 mono-data" data-testid={`ad-table-start-${ad.ad_archive_id}`}>
                          {formatDate(ad.ad_start_date)}
                        </td>
                        <td className="px-4 py-3 mono-data" data-testid={`ad-table-longevity-${ad.ad_archive_id}`}>
                          {ad.ad_longevity_days} days
                        </td>
                        <td className="px-4 py-3" data-testid={`ad-table-status-${ad.ad_archive_id}`}>{ad.ad_status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      </div>
    </AppLayout>
  );
}
