# PRD — AdInsight

## Original Problem Statement
Build a full-stack web app (AdInsight) for D2C marketing managers to analyze competitor ad strategies from Meta Ad Library with live data, ad longevity, theme categorization, dashboard analytics, AI insights (GPT-5.2), gap detection, weekly AI brief, manual sync + daily auto-sync, and no login.

## User Choices Implemented
- No Meta API key; scrape publicly available Meta Ad Library search pages by competitor brand names.
- AI model: OpenAI GPT-5.2.
- Key source: Emergent universal key.
- Sync model: Manual "Sync Now" + daily auto-sync.
- Access control: No login.

## Architecture Decisions
- **Frontend**: React + Tailwind + Recharts + Shadcn UI, route-based dashboard UX.
- **Backend**: FastAPI + Motor (MongoDB) + emergentintegrations LLM chat.
- **Data ingestion**: Switched from requests-based scrape to **Playwright-based scrape** in backend to reliably bypass anti-bot challenge and capture live ad payload embedded in page HTML.
- **Persistence**: MongoDB collections for `ads`, `sync_runs`, `ai_briefs`, `status_checks`.
- **Scheduling**: async daily loop for auto-sync + weekly brief refresh.

## What’s Implemented
1. **Live competitor ad sync pipeline**
   - Tracks 13 competitors (includes required 10+).
   - Extracts/stores: brand, ad copy, creative link, format, platform, start date, status, longevity, theme.
   - Upsert by `ad_archive_id`, sync progress state, run history.
2. **Analytics APIs**
   - Filterable ad listing: brand/format/theme/recency + sorting.
   - Dashboard summary: format distribution, theme distribution, active advertisers, longest-running ads, activity over time.
3. **AI intelligence APIs**
   - GPT-5.2-powered insights generation.
   - Gap detection (underused formats/themes).
   - Weekly AI brief endpoint + persistence.
4. **Frontend dashboard app**
   - Pages: Dashboard, Ad Explorer, AI Insights.
   - Sidebar nav + Sync Now action + live sync status.
   - Charts, KPI cards, ad cards, filter sidebar, sortable table.
   - Insights generation UI with sync-aware disable state to prevent 409 conflicts.
5. **Testing**
   - API + frontend validation completed.
   - Added backend pytest regression tests in `/app/backend/tests/`.

## Prioritized Backlog
### P0
- Add pagination/virtualization for large ad lists (avoid heavy payloads).
- Add robust retry/backoff + brand-level timeout controls for Playwright scraping.
- Improve dedupe quality when same creative appears across multiple collated nodes.

### P1
- Add campaign-level grouping and creative family clustering.
- Add export (CSV/XLSX) for filtered ad tables and weekly brief snapshots.
- Add richer theme classifier (LLM-assisted fallback + confidence score).

### P2
- Add saved views and alerts for format/theme share shifts.
- Add creative thumbnail caching/proxying for faster rendering.
- Add benchmark comparisons against user-selected “focus competitors”.

## Next Tasks
1. Add paginated `/api/ads` response and frontend pagination controls.
2. Add ingestion observability panel (brand failures, retry reason, scrape timings).
3. Add export and scheduled email delivery for weekly briefs.
