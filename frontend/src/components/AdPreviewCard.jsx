import { format } from "date-fns";

const parseDate = (value) => {
  try {
    return format(new Date(value), "MMM dd, yyyy");
  } catch {
    return value;
  }
};

export default function AdPreviewCard({ ad, testId }) {
  return (
    <article className="interactive-card overflow-hidden rounded-lg border border-border bg-card" data-testid={`${testId}-card`}>
      <div className="aspect-[4/3] w-full overflow-hidden bg-muted" data-testid={`${testId}-media-wrapper`}>
        {ad.ad_creative_link ? (
          <img
            src={ad.ad_creative_link}
            alt={`${ad.brand_name} creative`}
            className="safe-media h-full w-full"
            loading="lazy"
            data-testid={`${testId}-media-image`}
          />
        ) : (
          <div className="flex h-full items-center justify-center px-4 text-sm text-muted-foreground" data-testid={`${testId}-media-empty`}>
            No creative preview available
          </div>
        )}
      </div>
      <div className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground" data-testid={`${testId}-brand`}>
              {ad.brand_name}
            </p>
            <p className="mt-1 text-sm font-medium text-foreground" data-testid={`${testId}-page`}>
              {ad.page_name}
            </p>
          </div>
          <span className="rounded-full border border-border px-2 py-1 text-xs font-semibold" data-testid={`${testId}-format`}>
            {ad.ad_format}
          </span>
        </div>

        <p className="line-clamp-3 text-sm text-foreground" data-testid={`${testId}-copy`}>
          {ad.ad_copy || "No ad copy available"}
        </p>

        <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
          <span className="mono-data" data-testid={`${testId}-start-date`}>
            {parseDate(ad.ad_start_date)}
          </span>
          <span className="text-right mono-data" data-testid={`${testId}-longevity`}>
            {ad.ad_longevity_days} days
          </span>
          <span data-testid={`${testId}-platform`}>{ad.platform}</span>
          <span className="text-right" data-testid={`${testId}-theme`}>
            {ad.message_theme}
          </span>
        </div>
      </div>
    </article>
  );
}
