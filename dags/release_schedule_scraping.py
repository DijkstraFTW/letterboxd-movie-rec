import sys
sys.path.insert(0, "/root/letterboxd-movie-rec")

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import random
import re
import time

from airflow import DAG
from airflow.operators.python import PythonOperator
from dotenv import load_dotenv

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app_logger.app_logger import setup_logger
from messaging.redis_client import RedisClient

load_dotenv("/root/letterboxd-movie-rec/.env")

logger = setup_logger("/root/letterboxd-movie-rec/logs/release_schedule_dag.log", "ReleaseScheduleDAG")


BASE_URL = "https://whentostream.com"

MONTH_NAMES = {
    1: "january", 2: "february", 3: "march", 4: "april",
    5: "may", 6: "june", 7: "july", 8: "august",
    9: "september", 10: "october", 11: "november", 12: "december",
}

DEFAULT_ARGS = {
    "owner": "DijkstraFTW",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
    "Connection": "keep-alive",
}


def _build_url(page_type: str, year: int, month: int) -> str:
    """Build a whentostream.com calendar URL.

    Args:
        page_type: 'streaming' or 'in-theaters'
        year: e.g. 2026
        month: 1-12
    """
    month_name = MONTH_NAMES[month]
    return f"{BASE_URL}/{page_type}-{month_name}-{year}/"


def _slug_to_title(slug: str) -> str:
    """Convert a URL slug like 'hurry-up-tomorrow-2025' to a readable title."""
    return re.sub(r"-\d{4}$", "", slug).replace("-", " ").title()


def _extract_year_from_slug(slug: str) -> str | None:
    """Extract the year from a slug like 'hurry-up-tomorrow-2025'."""
    m = re.search(r"-(\d{4})$", slug)
    return m.group(1) if m else None


def _parse_calendar_page(html: str, page_type: str) -> dict[str, list[dict]]:
    """Parse a whentostream calendar page and return releases grouped by date.

    Returns:
        Dict mapping 'YYYY-MM-DD' -> list of movie dicts
    """
    soup = BeautifulSoup(html, "html.parser")
    releases: dict[str, list[dict]] = {}

    for header in soup.find_all("h2"):
        try:
            date = datetime.strptime(header.get_text(strip=True), "%B %d, %Y")
        except ValueError:
            continue

        date_key = date.strftime("%Y-%m-%d")
        movies: list[dict] = []

        sib = header.find_next_sibling()
        while sib and sib.name != "h2":
            if hasattr(sib, "find_all"):
                for link in sib.find_all("a", href=True):
                    href = link["href"]

                    if not href.startswith(("/", BASE_URL)):
                        continue
                    if any(x in href for x in (
                        "streaming-", "in-theaters-", "when-to-stream",
                        "whats-streaming", "weekly-tracking", "?share="
                    )):
                        continue

                    slug = href.rstrip("/").split("/")[-1]
                    if not slug or any(m["slug"] == slug for m in movies):
                        continue

                    movie = {
                        "title": _slug_to_title(slug),
                        "slug": slug,
                        "url": href if href.startswith("http") else BASE_URL + href,
                        "release_date": date_key,
                        "release_type": page_type,
                    }

                    year = _extract_year_from_slug(slug)
                    if year:
                        movie["year"] = year

                    img = link.find("img")
                    if img:
                        movie["poster_url"] = img.get("data-src") or img.get("src")

                    movies.append(movie)

            sib = sib.find_next_sibling()

        if movies:
            releases[date_key] = movies

    return releases


def _fetch_page(url: str, session: requests.Session) -> str | None:
    """Fetch a page with retry logic and rate limiting handling."""
    for attempt in range(5):
        try:
            resp = session.get(url, headers=HEADERS, timeout=30)

            if resp.status_code == 429:
                wait = 60 * (attempt + 1) + random.randint(0, 30)
                logger.warning(f"429 received, sleeping {wait}s")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp.text

        except requests.RequestException as e:
            wait = 30 * (attempt + 1)
            logger.warning(f"Request failed ({e}), sleeping {wait}s")
            time.sleep(wait)

    return None


def scrape_and_publish(**context):
    """Main task: scrape current + next 2 months for both streaming and theaters,
    then publish all releases to Redis queue."""

    execution_date: datetime = context["logical_date"]
    today_str = execution_date.strftime("%Y-%m-%d")

    months_to_scrape = []
    for offset in range(3):
        target = execution_date + relativedelta(months=offset)
        months_to_scrape.append((target.year, target.month))

    logger.info(
        "Scraping months: %s",
        [f"{y}-{m:02d}" for y, m in months_to_scrape],
    )

    session = requests.Session()
    adapter = HTTPAdapter(
        max_retries=Retry(
            total=0,
            respect_retry_after_header=True,
        )
    )
    session.mount("https://", adapter)

    all_streaming: dict[str, list[dict]] = {}
    all_theaters: dict[str, list[dict]] = {}

    for year, month in months_to_scrape:
        for page_type, collector in [
            ("streaming", all_streaming),
            ("in-theaters", all_theaters),
        ]:
            url = _build_url(page_type, year, month)
            logger.info("Fetching: %s", url)

            html = _fetch_page(url, session)
            if html is None:
                logger.warning("Skipping %s (fetch failed)", url)
                continue

            parsed = _parse_calendar_page(html, page_type)
            for date_key, movies in parsed.items():
                seen = {m["slug"] for m in collector.get(date_key, [])}
                collector.setdefault(date_key, []).extend(
                    m for m in movies if m["slug"] not in seen
                )

            delay = random.uniform(45, 90)
            logger.info(f"Sleeping for {delay:.1f}s before next request")
            time.sleep(delay)

    all_dates = sorted(set(all_streaming) | set(all_theaters))

    logger.info(
        "Found %d streaming releases and %d theater releases across %d dates",
        sum(len(movies) for movies in all_streaming.values()),
        sum(len(movies) for movies in all_theaters.values()),
        len(all_dates),
    )

    try:
        redis_client = RedisClient()

        all_releases = [
            {
                'date': date_key,
                'scraped_at': today_str,
                'streaming_releases': all_streaming.get(date_key, []),
                'theater_releases': all_theaters.get(date_key, []),
            }
            for date_key in all_dates
        ]

        redis_client.client.set("upcoming_releases", json.dumps(all_releases, ensure_ascii=False))
        logger.info("Stored %d release dates in Redis under key 'upcoming_releases'", len(all_dates))

    except Exception as e:
        logger.error("Error writing releases to Redis: %s", e, exc_info=True)
        raise

    return len(all_dates)



with DAG(
    dag_id="whentostream_daily_scraper",
    default_args=DEFAULT_ARGS,
    description=(
        "Daily scrape of whentostream.com for streaming and theater releases. "
        "Scrapes the current month + next 2 months and publishes to Redis."
    ),
    schedule="0 5 * * *", 
    start_date=datetime(2026, 2, 1),
    catchup=False,
) as dag:

    scrape_task = PythonOperator(
        task_id="scrape_and_publish_releases",
        python_callable=scrape_and_publish,
        provide_context=True,
    )