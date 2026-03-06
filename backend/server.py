import asyncio
import json
import logging
import os
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage
from fastapi import APIRouter, FastAPI, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorClient
from playwright.async_api import Browser, BrowserContext, Error as PlaywrightError, Playwright, async_playwright
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="AdInsight API")
api_router = APIRouter(prefix="/api")

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

COMPETITOR_BRANDS = [
    "BeBodywise",
    "Man Matters",
    "Little Joys",
    "Mamaearth",
    "The Derma Co",
    "Minimalist",
    "Chemist at Play",
    "Beardo",
    "Ustraa",
    "Troovy",
    "Bombay Shaving Company",
    "Mcaffeine",
    "Foxtale",
]

MESSAGE_THEME_RULES = {
    "UGC testimonial": ["review", "testimonial", "real users", "customer said", "users love"],
    "doctor/expert authority": ["doctor", "dermatologist", "expert", "clinically", "recommended by"],
    "before and after results": ["before", "after", "transformation", "results in", "visible results"],
    "product education": ["how to use", "ingredients", "formulated", "what it does", "routine"],
    "problem/solution": ["struggle", "problem", "fix", "solution", "treat", "repair"],
    "lifestyle branding": ["confidence", "lifestyle", "everyday", "glow", "look and feel"],
    "discount/promotion": ["off", "%", "sale", "coupon", "deal", "shop now", "limited time", "free"],
}

THEME_ORDER = list(MESSAGE_THEME_RULES.keys())
FORMAT_ORDER = ["image", "video", "carousel", "unknown"]

BRAND_ALIASES = {
    "BeBodywise": ["bebodywise", "bodywise"],
    "Man Matters": ["manmatters", "man matters"],
    "Little Joys": ["littlejoys", "little joys"],
    "Mamaearth": ["mamaearth"],
    "The Derma Co": ["thedermaco", "dermaco", "derma co"],
    "Minimalist": ["minimalist"],
    "Chemist at Play": ["chemistatplay", "chemist at play", "chemistatplay"],
    "Beardo": ["beardo"],
    "Ustraa": ["ustraa"],
    "Troovy": ["troovy"],
    "Bombay Shaving Company": ["bombayshavingcompany", "bombay shaving"],
    "Mcaffeine": ["mcaffeine", "m caffeine"],
    "Foxtale": ["foxtale"],
}

sync_lock = asyncio.Lock()
daily_sync_task: Optional[asyncio.Task] = None
manual_sync_task: Optional[asyncio.Task] = None
sync_state: Dict[str, Any] = {
    "running": False,
    "current_brand": None,
    "scanned_brands": 0,
    "total_brands": len(COMPETITOR_BRANDS),
    "started_at": None,
    "last_completed_at": None,
    "trigger": None,
    "last_summary": None,
}

playwright_lock = asyncio.Lock()
playwright_driver: Optional[Playwright] = None
playwright_browser: Optional[Browser] = None
playwright_context: Optional[BrowserContext] = None


class SyncNowRequest(BaseModel):
    max_ads_per_brand: int = Field(default=20, ge=5, le=60)


class InsightsRequest(BaseModel):
    recency_days: int = Field(default=90, ge=7, le=365)


class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def classify_message_theme(text: str) -> str:
    content = (text or "").lower()
    for theme, keywords in MESSAGE_THEME_RULES.items():
        if any(keyword in content for keyword in keywords):
            return theme
    return "product education"


def get_platform_label(platforms: List[str]) -> str:
    normalized = set(platforms or [])
    selected = []
    if "FACEBOOK" in normalized:
        selected.append("Facebook")
    if "INSTAGRAM" in normalized:
        selected.append("Instagram")
    return ", ".join(selected) if selected else "Unknown"


def extract_ad_format_and_creative(snapshot: Dict[str, Any]) -> tuple[str, str]:
    videos = snapshot.get("videos") or []
    cards = snapshot.get("cards") or []
    images = snapshot.get("images") or []
    display_format = str(snapshot.get("display_format") or "").upper()

    def get_video_link(record: Dict[str, Any]) -> str:
        return (
            record.get("video_hd_url")
            or record.get("video_sd_url")
            or record.get("watermarked_video_hd_url")
            or record.get("watermarked_video_sd_url")
            or ""
        )

    def get_image_link(record: Dict[str, Any]) -> str:
        return record.get("original_image_url") or record.get("resized_image_url") or ""

    video_link = ""
    image_link = ""

    for item in videos:
        video_link = get_video_link(item)
        if video_link:
            break

    for item in cards:
        if not video_link:
            video_link = get_video_link(item)
        if not image_link:
            image_link = get_image_link(item)

    for item in images:
        if not image_link:
            image_link = get_image_link(item)

    if "VIDEO" in display_format or video_link:
        return "video", video_link or image_link
    if "CAROUSEL" in display_format or "DPA" in display_format or len(cards) > 1:
        return "carousel", image_link or video_link
    if image_link:
        return "image", image_link
    return "unknown", ""


def brand_match(brand: str, record: Dict[str, Any]) -> bool:
    aliases = [normalize_text(item) for item in BRAND_ALIASES.get(brand, [brand])]
    snapshot = record.get("snapshot") or {}
    cards = snapshot.get("cards") or []
    card_text = " ".join(
        f"{card.get('title', '')} {card.get('body', '')} {card.get('link_url', '')}" for card in cards
    )
    body_text = ""
    if isinstance(snapshot.get("body"), dict):
        body_text = snapshot.get("body", {}).get("text", "")
    elif isinstance(snapshot.get("body"), str):
        body_text = snapshot.get("body")

    full_text = " ".join(
        [
            str(record.get("page_name") or ""),
            str(snapshot.get("page_name") or ""),
            body_text,
            card_text,
            str(snapshot.get("link_url") or ""),
        ]
    )
    normalized = normalize_text(full_text)
    return any(alias in normalized for alias in aliases)


def get_body_text(snapshot: Dict[str, Any]) -> str:
    body = snapshot.get("body")
    if isinstance(body, dict):
        text = body.get("text")
        if text:
            return text.strip()
    if isinstance(body, str):
        return body.strip()
    cards = snapshot.get("cards") or []
    if cards:
        card = cards[0]
        return (card.get("body") or card.get("title") or "").strip()
    return ""


async def close_playwright_resources() -> None:
    global playwright_context, playwright_browser, playwright_driver

    if playwright_context is not None:
        try:
            await playwright_context.close()
        except Exception:  # noqa: BLE001
            pass
        playwright_context = None

    if playwright_browser is not None:
        try:
            await playwright_browser.close()
        except Exception:  # noqa: BLE001
            pass
        playwright_browser = None

    if playwright_driver is not None:
        try:
            await playwright_driver.stop()
        except Exception:  # noqa: BLE001
            pass
        playwright_driver = None


async def ensure_playwright_context() -> BrowserContext:
    global playwright_driver, playwright_browser, playwright_context

    async with playwright_lock:
        if playwright_context is not None:
            return playwright_context

        playwright_driver = await async_playwright().start()
        playwright_browser = await playwright_driver.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        playwright_context = await playwright_browser.new_context(
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 1600},
        )
        return playwright_context


async def fetch_meta_ad_library_html(brand_name: str) -> tuple[str, str]:
    encoded_brand = quote_plus(brand_name)
    search_url = (
        "https://www.facebook.com/ads/library/?active_status=all"
        "&ad_type=all&country=IN&is_targeted_country=false&media_type=all"
        f"&search_type=keyword_unordered&q={encoded_brand}"
    )

    last_error: Optional[str] = None
    for attempt in range(2):
        page = None
        try:
            context = await ensure_playwright_context()
            page = await context.new_page()
            await page.goto(search_url, wait_until="domcontentloaded", timeout=120000)
            await page.wait_for_timeout(6500)
            html = await page.content()

            if "ad_archive_id" not in html:
                await page.reload(wait_until="domcontentloaded", timeout=120000)
                await page.wait_for_timeout(4500)
                html = await page.content()

            if "ad_archive_id" not in html:
                raise ValueError("Meta Ad Library page loaded but ad payload not found.")

            return html, page.url
        except (PlaywrightError, asyncio.TimeoutError, ValueError) as exc:
            last_error = str(exc)
            logger.warning("Playwright scrape retry for %s (attempt %s): %s", brand_name, attempt + 1, exc)
            await close_playwright_resources()
            await asyncio.sleep(1.2)
        finally:
            if page is not None and not page.is_closed():
                await page.close()

    raise ValueError(f"Meta Ad Library scrape failed for {brand_name}. Last error: {last_error}")


def extract_ad_objects(html: str, max_ads: int) -> List[Dict[str, Any]]:
    decoder = json.JSONDecoder()
    records: List[Dict[str, Any]] = []
    seen_ids = set()
    cursor = 0
    max_scan = max_ads * 8

    for _ in range(max_scan):
        start_index = html.find('{"ad_archive_id"', cursor)
        if start_index == -1:
            break
        try:
            ad_record, consumed = decoder.raw_decode(html[start_index:])
        except json.JSONDecodeError:
            cursor = start_index + 16
            continue

        cursor = start_index + consumed
        ad_id = str(ad_record.get("ad_archive_id") or "")
        if not ad_id or ad_id in seen_ids:
            continue
        seen_ids.add(ad_id)
        records.append(ad_record)
        if len(records) >= max_ads * 3:
            break

    return records


def parse_meta_record(brand_name: str, raw_record: Dict[str, Any], source_url: str) -> Optional[Dict[str, Any]]:
    start_timestamp = raw_record.get("start_date")
    if not isinstance(start_timestamp, int):
        return None

    snapshot = raw_record.get("snapshot") or {}
    start_dt = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
    today = datetime.now(timezone.utc)
    longevity_days = max(1, (today - start_dt).days)

    ad_copy = get_body_text(snapshot)
    ad_format, creative_link = extract_ad_format_and_creative(snapshot)
    page_name = str(raw_record.get("page_name") or snapshot.get("page_name") or brand_name)
    message_theme = classify_message_theme(ad_copy)

    record = {
        "id": str(uuid.uuid4()),
        "ad_archive_id": str(raw_record.get("ad_archive_id")),
        "brand_name": brand_name,
        "page_name": page_name,
        "ad_copy": ad_copy,
        "ad_creative_link": creative_link,
        "ad_format": ad_format,
        "platform": get_platform_label(raw_record.get("publisher_platform") or []),
        "ad_start_date": start_dt.date().isoformat(),
        "ad_status": "active" if raw_record.get("is_active") else "inactive",
        "ad_longevity_days": longevity_days,
        "message_theme": message_theme,
        "source": "meta_ad_library_public_search",
        "source_url": source_url,
        "last_seen_at": today.isoformat(),
    }
    return record


async def scrape_brand_ads(brand_name: str, max_ads_per_brand: int) -> Dict[str, Any]:
    html, source_url = await fetch_meta_ad_library_html(brand_name)
    raw_records = extract_ad_objects(html, max_ads_per_brand)

    parsed_records: List[Dict[str, Any]] = []
    for record in raw_records:
        if not brand_match(brand_name, record):
            continue
        parsed = parse_meta_record(brand_name, record, source_url)
        if parsed:
            parsed_records.append(parsed)

    inserted_count = 0
    for item in parsed_records:
        await db.ads.update_one(
            {"ad_archive_id": item["ad_archive_id"]},
            {
                "$set": {
                    "brand_name": item["brand_name"],
                    "page_name": item["page_name"],
                    "ad_copy": item["ad_copy"],
                    "ad_creative_link": item["ad_creative_link"],
                    "ad_format": item["ad_format"],
                    "platform": item["platform"],
                    "ad_start_date": item["ad_start_date"],
                    "ad_status": item["ad_status"],
                    "ad_longevity_days": item["ad_longevity_days"],
                    "message_theme": item["message_theme"],
                    "source": item["source"],
                    "source_url": item["source_url"],
                    "last_seen_at": item["last_seen_at"],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                "$setOnInsert": {
                    "id": item["id"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            },
            upsert=True,
        )
        inserted_count += 1

    return {
        "brand_name": brand_name,
        "fetched_raw": len(raw_records),
        "stored_ads": inserted_count,
    }


async def run_sync_job(trigger: str, max_ads_per_brand: int = 20) -> Dict[str, Any]:
    async with sync_lock:
        sync_state["running"] = True
        sync_state["current_brand"] = None
        sync_state["scanned_brands"] = 0
        sync_state["total_brands"] = len(COMPETITOR_BRANDS)
        sync_state["started_at"] = datetime.now(timezone.utc).isoformat()
        sync_state["trigger"] = trigger

        run_details = []
        errors = []
        total_stored = 0
        started_at = datetime.now(timezone.utc)

        for index, brand_name in enumerate(COMPETITOR_BRANDS, start=1):
            sync_state["current_brand"] = brand_name
            sync_state["scanned_brands"] = index - 1

            try:
                result = await scrape_brand_ads(brand_name, max_ads_per_brand)
                run_details.append(result)
                total_stored += result["stored_ads"]
            except Exception as exc:  # noqa: BLE001
                logger.exception("Sync failed for %s", brand_name)
                errors.append({"brand_name": brand_name, "error": str(exc)})

            sync_state["scanned_brands"] = index
            await asyncio.sleep(1.0)

        completed_at = datetime.now(timezone.utc)
        summary = {
            "trigger": trigger,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": round((completed_at - started_at).total_seconds(), 2),
            "total_brands": len(COMPETITOR_BRANDS),
            "total_ads_stored": total_stored,
            "errors": errors,
            "details": run_details,
        }

        await db.sync_runs.insert_one(summary.copy())

        sync_state["running"] = False
        sync_state["current_brand"] = None
        sync_state["last_completed_at"] = completed_at.isoformat()
        sync_state["last_summary"] = summary
        return summary


async def fetch_ads(
    brand: Optional[str] = None,
    ad_format: Optional[str] = None,
    message_theme: Optional[str] = None,
    recency_days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    filters: Dict[str, Any] = {}
    if brand:
        filters["brand_name"] = brand
    if ad_format:
        filters["ad_format"] = ad_format
    if message_theme:
        filters["message_theme"] = message_theme
    if recency_days:
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=recency_days)).date().isoformat()
        filters["ad_start_date"] = {"$gte": cutoff_date}

    records = await db.ads.find(filters, {"_id": 0}).to_list(5000)

    today = datetime.now(timezone.utc).date()
    for item in records:
        try:
            start_dt = datetime.fromisoformat(item["ad_start_date"]).date()
            item["ad_longevity_days"] = max(1, (today - start_dt).days)
        except Exception:  # noqa: BLE001
            item["ad_longevity_days"] = item.get("ad_longevity_days", 1)

    return records


def summarize_ads(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    format_counter = Counter((item.get("ad_format") or "unknown") for item in records)
    theme_counter = Counter((item.get("message_theme") or "product education") for item in records)
    brand_counter = Counter((item.get("brand_name") or "Unknown") for item in records)
    activity_counter = Counter((item.get("ad_start_date") or "") for item in records)

    longest_running = sorted(records, key=lambda item: item.get("ad_longevity_days", 0), reverse=True)[:10]

    ad_activity = [
        {"date": date_key, "ads_started": count}
        for date_key, count in sorted(activity_counter.items(), key=lambda pair: pair[0])
        if date_key
    ]

    return {
        "kpis": {
            "total_ads": len(records),
            "active_ads": sum(1 for item in records if item.get("ad_status") == "active"),
            "tracked_brands": len(set(item.get("brand_name") for item in records if item.get("brand_name"))),
            "avg_longevity_days": round(
                (sum(item.get("ad_longevity_days", 0) for item in records) / len(records)) if records else 0,
                1,
            ),
        },
        "format_distribution": [
            {"name": item, "count": format_counter.get(item, 0)}
            for item in FORMAT_ORDER
            if format_counter.get(item, 0) > 0
        ],
        "theme_distribution": [
            {"name": item, "count": theme_counter.get(item, 0)}
            for item in THEME_ORDER
            if theme_counter.get(item, 0) > 0
        ],
        "most_active_advertisers": [
            {"brand_name": brand, "count": count}
            for brand, count in brand_counter.most_common(8)
        ],
        "longest_running_ads": longest_running,
        "ad_activity_over_time": ad_activity,
    }


def detect_gaps(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not records:
        return {
            "underused_formats": [],
            "underused_themes": [],
            "opportunity_notes": ["No ad data available yet. Run Sync Now to generate opportunities."],
        }

    total = len(records)
    format_counter = Counter((item.get("ad_format") or "unknown") for item in records)
    theme_counter = Counter((item.get("message_theme") or "product education") for item in records)

    underused_formats = []
    for ad_format in ["image", "video", "carousel"]:
        count = format_counter.get(ad_format, 0)
        percentage = (count / total) * 100
        if percentage < 18:
            underused_formats.append(
                {
                    "name": ad_format,
                    "count": count,
                    "share_percent": round(percentage, 1),
                }
            )

    underused_themes = []
    for theme in THEME_ORDER:
        count = theme_counter.get(theme, 0)
        percentage = (count / total) * 100
        if percentage < 12:
            underused_themes.append(
                {
                    "name": theme,
                    "count": count,
                    "share_percent": round(percentage, 1),
                }
            )

    opportunity_notes = []
    if underused_formats:
        names = ", ".join(item["name"] for item in underused_formats)
        opportunity_notes.append(f"Test more {names} creatives to stand out from the category norm.")
    if underused_themes:
        names = ", ".join(item["name"] for item in underused_themes[:3])
        opportunity_notes.append(f"Messaging whitespace exists in: {names}.")

    return {
        "underused_formats": underused_formats,
        "underused_themes": underused_themes,
        "opportunity_notes": opportunity_notes,
    }


async def generate_ai_insights_payload(recency_days: int, trigger: str) -> Dict[str, Any]:
    records = await fetch_ads(recency_days=recency_days)
    summary = summarize_ads(records)
    gaps = detect_gaps(records)

    payload = {
        "recency_days": recency_days,
        "kpis": summary["kpis"],
        "format_distribution": summary["format_distribution"],
        "theme_distribution": summary["theme_distribution"],
        "most_active_advertisers": summary["most_active_advertisers"],
        "longest_running_ads": [
            {
                "brand_name": item.get("brand_name"),
                "ad_archive_id": item.get("ad_archive_id"),
                "longevity_days": item.get("ad_longevity_days"),
                "message_theme": item.get("message_theme"),
                "ad_format": item.get("ad_format"),
            }
            for item in summary["longest_running_ads"][:10]
        ],
        "gap_detection": gaps,
    }

    llm_key = os.environ.get("EMERGENT_LLM_KEY")
    if not llm_key:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY is missing in backend environment.")

    system_message = (
        "You are a senior D2C performance strategist. Return concise, practical marketing insights in strict JSON."
    )
    user_prompt = (
        "Analyze this competitor ads dataset and return STRICT JSON with keys: "
        "creative_trends (array of 3-6 bullets), messaging_shifts (array of 3-6 bullets), "
        "top_long_running_ads (array of objects with ad_archive_id, reason), "
        "gap_opportunities (array of 3-6 bullets), weekly_brief (single paragraph).\n\n"
        f"DATA:\n{json.dumps(payload, ensure_ascii=False)}"
    )

    chat = LlmChat(
        api_key=llm_key,
        session_id=f"adinsight-insights-{uuid.uuid4()}",
        system_message=system_message,
    ).with_model("openai", "gpt-5.2")

    llm_response = await chat.send_message(UserMessage(text=user_prompt))
    response_text = llm_response if isinstance(llm_response, str) else str(llm_response)

    insights_json: Dict[str, Any]
    try:
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON object found in model response")
        insights_json = json.loads(json_match.group(0))
    except Exception:  # noqa: BLE001
        insights_json = {
            "creative_trends": [
                "Competitors are repeatedly scaling creatives with durable hooks and clear CTAs.",
                "Long-running creatives typically combine functional benefits with social proof.",
                "Category messaging clusters around routine-based education and offers.",
            ],
            "messaging_shifts": [
                "Messaging appears to be moving from pure discounting toward education-led persuasion.",
                "Brands are mixing expert-led and lifestyle-led storytelling in the same campaign sets.",
            ],
            "top_long_running_ads": [
                {
                    "ad_archive_id": item.get("ad_archive_id"),
                    "reason": "High longevity suggests this concept likely sustains performance.",
                }
                for item in payload["longest_running_ads"][:5]
            ],
            "gap_opportunities": gaps["opportunity_notes"] or ["Run Sync Now to detect category whitespace."],
            "weekly_brief": (
                "This week, leading competitors are scaling consistency-driven creatives while leaving room "
                "for differentiated formats and underused themes. Prioritize one experimental format and one "
                "underused message angle to gain share of attention."
            ),
        }

    output = {
        "trigger": trigger,
        "recency_days": recency_days,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "creative_trends": insights_json.get("creative_trends", []),
        "messaging_shifts": insights_json.get("messaging_shifts", []),
        "top_long_running_ads": insights_json.get("top_long_running_ads", []),
        "gap_opportunities": insights_json.get("gap_opportunities", []),
        "weekly_brief": insights_json.get("weekly_brief", ""),
        "dataset_summary": payload,
    }

    await db.ai_briefs.insert_one(output.copy())
    return output


async def run_daily_jobs_loop() -> None:
    await asyncio.sleep(20)
    while True:
        try:
            await run_sync_job(trigger="auto_daily", max_ads_per_brand=20)
            latest_brief = await db.ai_briefs.find({}, {"_id": 0}).sort("created_at", -1).to_list(1)
            if not latest_brief:
                await generate_ai_insights_payload(recency_days=90, trigger="auto_weekly")
            else:
                last_created = datetime.fromisoformat(latest_brief[0]["created_at"])
                if (datetime.now(timezone.utc) - last_created) >= timedelta(days=7):
                    await generate_ai_insights_payload(recency_days=90, trigger="auto_weekly")
        except Exception:  # noqa: BLE001
            logger.exception("Daily automation loop failed")

        await asyncio.sleep(24 * 60 * 60)


@api_router.get("/")
async def root():
    return {"message": "AdInsight API is running"}


@api_router.get("/competitors")
async def get_competitors():
    return {"competitors": COMPETITOR_BRANDS}


@api_router.post("/sync/now")
async def sync_now(input: SyncNowRequest):
    global manual_sync_task
    if sync_state["running"]:
        return {
            "status": "already_running",
            "sync_state": sync_state,
        }

    manual_sync_task = asyncio.create_task(run_sync_job(trigger="manual", max_ads_per_brand=input.max_ads_per_brand))
    return {
        "status": "started",
        "sync_state": sync_state,
    }


@api_router.get("/sync/status")
async def get_sync_status():
    latest = await db.sync_runs.find({}, {"_id": 0}).sort("started_at", -1).to_list(1)
    return {
        "sync_state": sync_state,
        "latest_run": latest[0] if latest else None,
    }


@api_router.get("/ads")
async def list_ads(
    brand: Optional[str] = Query(default=None),
    ad_format: Optional[str] = Query(default=None),
    message_theme: Optional[str] = Query(default=None),
    recency_days: Optional[int] = Query(default=90),
    sort_by: str = Query(default="ad_start_date"),
    sort_order: str = Query(default="desc"),
):
    records = await fetch_ads(
        brand=brand,
        ad_format=ad_format,
        message_theme=message_theme,
        recency_days=recency_days,
    )

    reverse_sort = sort_order.lower() == "desc"
    if sort_by in {"ad_longevity_days", "ad_start_date", "brand_name", "ad_format", "message_theme"}:
        records.sort(key=lambda item: item.get(sort_by) or "", reverse=reverse_sort)

    return {"items": records, "total": len(records)}


@api_router.get("/analytics/dashboard")
async def dashboard_analytics(recency_days: int = Query(default=90, ge=7, le=365)):
    records = await fetch_ads(recency_days=recency_days)
    summary = summarize_ads(records)
    return {
        "recency_days": recency_days,
        "summary": summary,
        "gap_detection": detect_gaps(records),
    }


@api_router.post("/insights/generate")
async def generate_insights(input: InsightsRequest):
    if sync_state["running"]:
        raise HTTPException(status_code=409, detail="Sync is in progress. Try again in a few moments.")
    output = await generate_ai_insights_payload(recency_days=input.recency_days, trigger="manual")
    return output


@api_router.get("/insights/latest")
async def get_latest_insights():
    latest = await db.ai_briefs.find({}, {"_id": 0}).sort("created_at", -1).to_list(1)
    return latest[0] if latest else {"message": "No AI brief generated yet."}


@api_router.get("/insights/weekly-brief")
async def get_weekly_brief():
    latest = await db.ai_briefs.find({}, {"_id": 0}).sort("created_at", -1).to_list(1)
    if latest:
        latest_created = datetime.fromisoformat(latest[0]["created_at"])
        if (datetime.now(timezone.utc) - latest_created) < timedelta(days=7):
            return latest[0]
    return await generate_ai_insights_payload(recency_days=90, trigger="weekly_on_demand")


@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    doc = status_obj.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    await db.status_checks.insert_one(doc.copy())
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for check in status_checks:
        if isinstance(check["timestamp"], str):
            check["timestamp"] = datetime.fromisoformat(check["timestamp"])
    return status_checks


@app.on_event("startup")
async def startup_tasks() -> None:
    global daily_sync_task
    await db.ads.create_index("ad_archive_id", unique=True)
    await db.ads.create_index([("brand_name", 1), ("ad_start_date", -1)])
    await db.sync_runs.create_index("started_at")
    await db.ai_briefs.create_index("created_at")
    try:
        await ensure_playwright_context()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Playwright warmup failed on startup: %s", exc)
    if daily_sync_task is None or daily_sync_task.done():
        daily_sync_task = asyncio.create_task(run_daily_jobs_loop())


@app.on_event("shutdown")
async def shutdown_db_client():
    if daily_sync_task and not daily_sync_task.done():
        daily_sync_task.cancel()
    if manual_sync_task and not manual_sync_task.done():
        manual_sync_task.cancel()
    await close_playwright_resources()
    client.close()


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)