import time

import pytest


# AdInsight API core flow regression tests for sync, ads, analytics, and AI insights
class TestAdInsightCoreFlows:
    def test_root_api_health(self, api_client):
        from conftest import BASE_URL

        response = api_client.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        assert response.json().get("message") == "AdInsight API is running"

    def test_sync_now_starts_or_reports_running(self, api_client):
        from conftest import BASE_URL

        response = api_client.post(f"{BASE_URL}/api/sync/now", json={"max_ads_per_brand": 5})
        assert response.status_code == 200

        payload = response.json()
        assert payload.get("status") in ["started", "already_running"]
        assert "sync_state" in payload
        assert isinstance(payload["sync_state"].get("total_brands"), int)

    def test_sync_status_has_valid_progress_shape(self, api_client):
        from conftest import BASE_URL

        response = api_client.get(f"{BASE_URL}/api/sync/status")
        assert response.status_code == 200

        payload = response.json()
        sync_state = payload.get("sync_state") or {}
        assert isinstance(sync_state.get("running"), bool)
        assert isinstance(sync_state.get("scanned_brands"), int)
        assert isinstance(sync_state.get("total_brands"), int)

    def test_sync_status_eventually_has_completed_non_zero_ads(self, api_client):
        from conftest import BASE_URL

        # Poll briefly for latest completed run. If current sync is running, prior completed run may still exist.
        deadline = time.time() + 45
        latest_run = None
        while time.time() < deadline:
            status_response = api_client.get(f"{BASE_URL}/api/sync/status")
            assert status_response.status_code == 200
            latest_run = status_response.json().get("latest_run")
            if latest_run and latest_run.get("total_ads_stored", 0) > 0:
                break
            time.sleep(3)

        assert latest_run is not None
        assert latest_run.get("total_ads_stored", 0) > 0

    def test_ads_endpoint_returns_required_fields(self, api_client):
        from conftest import BASE_URL

        response = api_client.get(f"{BASE_URL}/api/ads", params={"recency_days": 90})
        assert response.status_code == 200

        payload = response.json()
        assert "items" in payload
        assert "total" in payload
        assert isinstance(payload["items"], list)

        if not payload["items"]:
            pytest.skip("No ads available to validate field-level response")

        ad = payload["items"][0]
        required_map = {
            "brand_name": "brand",
            "ad_copy": "ad copy",
            "ad_creative_link": "creative link",
            "ad_format": "format",
            "platform": "platform",
            "ad_start_date": "start date",
            "ad_status": "status",
            "ad_longevity_days": "longevity",
            "message_theme": "theme",
        }
        for key in required_map:
            assert key in ad, f"Missing required field: {key} ({required_map[key]})"

    def test_analytics_dashboard_returns_kpis_and_distributions(self, api_client):
        from conftest import BASE_URL

        response = api_client.get(f"{BASE_URL}/api/analytics/dashboard", params={"recency_days": 90})
        assert response.status_code == 200

        payload = response.json()
        assert payload.get("recency_days") == 90
        summary = payload.get("summary") or {}
        kpis = summary.get("kpis") or {}
        assert {"total_ads", "active_ads", "tracked_brands", "avg_longevity_days"}.issubset(kpis.keys())
        assert isinstance(summary.get("format_distribution"), list)
        assert isinstance(summary.get("theme_distribution"), list)
        assert isinstance(summary.get("ad_activity_over_time"), list)

    def test_generate_insights_returns_brief_json(self, api_client):
        from conftest import BASE_URL

        response = api_client.post(f"{BASE_URL}/api/insights/generate", json={"recency_days": 90})

        if response.status_code == 409:
            pytest.skip("Sync in progress; insights generation intentionally blocked")

        assert response.status_code == 200
        payload = response.json()

        expected_keys = {
            "creative_trends",
            "messaging_shifts",
            "top_long_running_ads",
            "gap_opportunities",
            "weekly_brief",
            "dataset_summary",
        }
        assert expected_keys.issubset(payload.keys())
        assert isinstance(payload.get("weekly_brief"), str)
        assert len(payload.get("weekly_brief", "").strip()) > 0
