import sys
sys.path.insert(0, "/root/letterboxd-movie-rec")

import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import time

from airflow import DAG
from airflow.operators.python import PythonOperator
from dotenv import load_dotenv

import requests

from app_logger.app_logger import setup_logger
from messaging.redis_client import RedisClient

load_dotenv("/root/letterboxd-movie-rec/.env")

logger = setup_logger(
    "/root/letterboxd-movie-rec/logs/release_schedule_dag.log",
    "ReleaseScheduleDAG",
)

TMDB_BASE = "https://api.themoviedb.org/3"
REGION = "US"

DIGITAL_TYPES = {4}
THEATER_TYPES = {2, 3}

DEFAULT_ARGS = {
    "owner": "DijkstraFTW",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def _session() -> requests.Session:
    token = os.getenv("THEMOVIEDB_KEY")
    if not token:
        raise RuntimeError("THEMOVIEDB_KEY not set in environment")
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    return s


def _get(session: requests.Session, path: str, params: dict | None = None) -> dict | None:
    """GET with retry/backoff. TMDB allows ~50 req/s; we stay far below."""
    url = f"{TMDB_BASE}{path}"
    for attempt in range(4):
        try:
            resp = session.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 2)) + 1
                logger.warning("TMDB 429, sleeping %ss", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            wait = 5 * (attempt + 1)
            logger.warning("TMDB request failed (%s), sleeping %ss", e, wait)
            time.sleep(wait)
    return None


def _discover_ids(session: requests.Session, gte: str, lte: str,
                  release_types: str) -> dict[int, dict]:
    """Discover movies whose {release_types} release in REGION falls in [gte, lte].

    Returns {movie_id: basic_info}. Paginates fully (max 500 pages).
    """
    movies: dict[int, dict] = {}
    page = 1
    while True:
        data = _get(session, "/discover/movie", {
            "region": REGION,
            "with_release_type": release_types,   # e.g. "4" or "2|3"
            "release_date.gte": gte,
            "release_date.lte": lte,
            "sort_by": "popularity.desc",
            "include_adult": "false",
            "page": page,
        })
        if not data or not data.get("results"):
            break
        for r in data["results"]:
            movies[r["id"]] = {
                "tmdb_id": r["id"],
                "title": r["title"],
                "original_title": r.get("original_title"),
                "year": (r.get("release_date") or "")[:4] or None,
                "poster_url": (
                    f"https://image.tmdb.org/t/p/w500{r['poster_path']}"
                    if r.get("poster_path") else None
                ),
                "popularity": r.get("popularity"),
                "vote_average": r.get("vote_average"),
                "url": f"https://www.themoviedb.org/movie/{r['id']}",
            }
        if page >= min(data.get("total_pages", 1), 500):
            break
        page += 1
        time.sleep(0.05)
    return movies


def _exact_dates(session: requests.Session, movie_id: int,
                 wanted_types: set[int]) -> list[str]:
    """Fetch the movie's REGION release dates matching wanted_types.

    Discover filters correctly, but the release_date field it returns is the
    *primary* release date — not necessarily the digital date. This call gets
    the real per-type dates.
    """
    data = _get(session, f"/movie/{movie_id}/release_dates")
    if not data:
        return []
    dates = []
    for entry in data.get("results", []):
        if entry.get("iso_3166_1") != REGION:
            continue
        for rel in entry.get("release_dates", []):
            if rel.get("type") in wanted_types and rel.get("release_date"):
                dates.append(rel["release_date"][:10])  # YYYY-MM-DD
    return sorted(set(dates))


def _collect(session: requests.Session, gte: str, lte: str,
             wanted_types: set[int], release_type_label: str) -> dict[str, list[dict]]:
    """Full pipeline for one release category: discover -> exact dates -> group by date."""
    type_filter = "|".join(str(t) for t in sorted(wanted_types))
    candidates = _discover_ids(session, gte, lte, type_filter)
    logger.info("%s: %d candidates in [%s, %s]",
                release_type_label, len(candidates), gte, lte)

    grouped: dict[str, list[dict]] = {}
    for i, (movie_id, info) in enumerate(candidates.items(), 1):
        for date_key in _exact_dates(session, movie_id, wanted_types):
            if not (gte <= date_key <= lte):
                continue
            movie = dict(info)
            movie["release_date"] = date_key
            movie["release_type"] = release_type_label
            grouped.setdefault(date_key, []).append(movie)
        if i % 50 == 0:
            logger.info("%s: enriched %d/%d", release_type_label, i, len(candidates))
        time.sleep(0.03)
    return grouped


def scrape_and_publish(**context):
    """Fetch current + next 2 months of digital and theatrical releases from
    TMDB and publish to Redis under 'upcoming_releases' (same schema as before)."""

    execution_date: datetime = context["logical_date"]
    today_str = execution_date.strftime("%Y-%m-%d")

    window_start = execution_date.replace(day=1)
    window_end = (window_start + relativedelta(months=3)) - timedelta(days=1)
    gte, lte = window_start.strftime("%Y-%m-%d"), window_end.strftime("%Y-%m-%d")
    logger.info("TMDB window: %s -> %s (region=%s)", gte, lte, REGION)

    session = _session()

    all_streaming = _collect(session, gte, lte, DIGITAL_TYPES, "streaming")
    all_theaters = _collect(session, gte, lte, THEATER_TYPES, "in-theaters")

    all_dates = sorted(set(all_streaming) | set(all_theaters))

    logger.info(
        "Found %d streaming releases and %d theater releases across %d dates",
        sum(len(m) for m in all_streaming.values()),
        sum(len(m) for m in all_theaters.values()),
        len(all_dates),
    )

    try:
        redis_client = RedisClient()

        all_releases = [
            {
                "date": date_key,
                "scraped_at": today_str,
                "streaming_releases": all_streaming.get(date_key, []),
                "theater_releases": all_theaters.get(date_key, []),
            }
            for date_key in all_dates
        ]

        redis_client.client.set(
            "upcoming_releases", json.dumps(all_releases, ensure_ascii=False)
        )
        logger.info(
            "Stored %d release dates in Redis under key 'upcoming_releases'",
            len(all_dates),
        )
    except Exception as e:
        logger.error("Error writing releases to Redis: %s", e, exc_info=True)
        raise

    return len(all_dates)


with DAG(
    dag_id="tmdb_daily_release_schedule",
    default_args=DEFAULT_ARGS,
    description=(
        "Daily fetch of upcoming digital and theatrical releases from TMDB. "
        "Covers the current month + next 2 months and publishes to Redis."
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