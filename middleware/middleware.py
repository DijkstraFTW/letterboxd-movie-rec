import json
import math
import os
import time
import random

from dotenv import load_dotenv
from database.mongodb_client import MongoDBClient
from messaging.redis_client import RedisClient
from app_logger.app_logger import setup_logger
from middleware.security_utils import ip_blocker, ip_whitelist, security_monitor
from typing import List, Dict, Any, Optional, Union

import httpx
from fastapi import Depends, FastAPI, HTTPException, Body, Header, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.concurrency import run_in_threadpool
import uvicorn
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

logger = setup_logger("/root/letterboxd-movie-rec/logs/middleware.log", "MiddlewareLogger")
load_dotenv("/root/letterboxd-movie-rec/.env")

class Movie(BaseModel):
    id: Union[int, str]
    title: str
    year: int
    rating: float
    source: str
    genres: Optional[List[str]] = []
    poster_url: Optional[str] = None

class RecommendationTrigger(BaseModel):
    letterboxd_username: str
    data_opt_in: bool
    run_id: Optional[str] = None

class FallbackRecommendationTrigger(BaseModel):
    genres: List[str] = Field(..., description="Preferred genres (e.g., ['Action', 'Sci-Fi'])")
    minimum_rating: float = Field(..., ge=0.0, le=10.0, description="Minimum user rating (0.0-10.0)")

class TriggerResponse(BaseModel):
    status: str
    message: str
    dag_run_id: Optional[str] = None
    
class Announcement(BaseModel):
    id: str
    title: str
    message: str
    created_at: Optional[int] = None

class MovieTopPick(BaseModel):
    movie_title: str
    movie_title_formatted: str
    lb_rating: Optional[float] = 0.0
    histogram: Optional[dict] = {}
    genres: Optional[List[str]] = []
    runtime: Optional[int] = 0
    poster_url: Optional[str] = None


class MiddlewareService:
    """Encapsulates recommendation logic and Airflow integration."""

    def __init__(self):
        self.airflow_base_url = os.getenv("AIRFLOW_BASE_URL")
        self.airflow_dag_id = os.getenv("AIRFLOW_DAG_ID")
        self.airflow_username = os.getenv("AIRFLOW_USERNAME")
        self.airflow_password = os.getenv("AIRFLOW_PASSWORD")
        self.recs_queue = os.getenv("REDIS_QUEUE_RECS")
        self.redis_client = RedisClient()
        self.client = self.redis_client.client

    def _fetch_from_redis_sync(self, key: str) -> List[Dict[str, Any]]:
        key_type = self.client.type(key)
        if key_type == b"string":
            raw = self.client.get(key)
            if not raw:
                return []
            try:
                data = json.loads(raw)
                return data if isinstance(data, list) else [data]
            except Exception:
                return []
        raw = self.client.lrange(key, 0, -1)
        result = []
        for item in raw:
            try:
                result.append(json.loads(item))
            except Exception:
                continue
        return result

    async def fetch_from_redis(self, key: str) -> List[Dict[str, Any]]:
        return await run_in_threadpool(self._fetch_from_redis_sync, key)

    def add_to_redis(self, key: str, movie: Dict[str, Any]) -> None:
        self.client.rpush(key, json.dumps(movie))
        logger.info(f"Added movie '{movie['title']}' to '{key}'")

    async def trigger_airflow_recommendation(self, username: str, opt_in: bool, timeout: float = 15.0, extra_conf: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Triggers an Airflow DAG asynchronously using HTTPX.

        :param username: Letterboxd username
        :param opt_in: Whether user opted into data sharing
        :param timeout: HTTP request timeout in seconds
        :param extra_conf: Optional additional fields to merge into the DAG conf
        :return: Dictionary with DAG trigger info
        """
        endpoint = f"{self.airflow_base_url}/dags/{self.airflow_dag_id}/dagRuns"
        conf = {
            "letterboxd_username": username,
            "data_opt_in": opt_in,
            "request_timestamp": int(time.time())
        }
        if extra_conf:
            conf.update(extra_conf)
        payload = {"conf": conf}
        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"Triggering Airflow DAG '{self.airflow_dag_id}' for user '{username}'")
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    auth=(self.airflow_username, self.airflow_password),
                    timeout=timeout
                )
                response.raise_for_status()
                dag_run_id = response.json().get("dag_run_id", f"MOCK-ID-{int(time.time())}")
                logger.info(f"DAG triggered successfully: {dag_run_id}")
                return {"status": "Airflow Triggered", "message": f"DAG triggered for {username}", "dag_run_id": dag_run_id}
            except httpx.HTTPStatusError as e:
                logger.error(f"Airflow API error: {e.response.text}")
                raise HTTPException(status_code=e.response.status_code, detail=f"Airflow API error: {e.response.text}")
            except httpx.RequestError as e:
                logger.error(f"Airflow connection error: {e}")
                raise HTTPException(status_code=503, detail=f"Cannot connect to Airflow API: {e}")


    def _collect_genre_recommendations_sync(
        self,
        genres: List[str],
        min_rating: float,
        max_results: int,
        queue_timeout: float
    ) -> List[Dict[str, Any]]:
        genres_lower = {g.lower() for g in genres}
        collected_movies = []
        seen_ids = set()

        result = self.client.blpop(self.recs_queue, timeout=int(queue_timeout))
        if not result:
            return []

        try:
            data = json.loads(result[1])
            for m in data.get("user_recommendation", []):
                movie_id = m.get("movie_title_formatted") or m.get("movie_title")
                if movie_id in seen_ids:
                    continue

                lb_rating = float(m.get("lb_rating") or 0.0)
                raw_genres = m.get("genres") or []
                movie_genres = [g.lower() for g in raw_genres]
                if lb_rating >= min_rating / 2 and (not genres or genres_lower & set(movie_genres)):
                    # Put matching genres first so MovieCard badge shows them
                    sorted_genres = (
                        [g for g in raw_genres if g.lower() in genres_lower] +
                        [g for g in raw_genres if g.lower() not in genres_lower]
                    )
                    collected_movies.append({
                        "id": movie_id,
                        "movie_title": m.get("movie_title", ""),
                        "movie_title_formatted": m.get("movie_title_formatted", ""),
                        "year_released": m.get("year_released") or 0,
                        "lb_rating": lb_rating,
                        "source": f"Fallback ({'/'.join(genres)}, >{min_rating})",
                        "genres": sorted_genres,
                        "poster_url": m.get("poster_url"),
                        "histogram": m.get("histogram") or {},
                        "runtime": m.get("runtime") or 0,
                    })
                    seen_ids.add(movie_id)

                if len(collected_movies) >= max_results:
                    break
        except Exception as e:
            logger.error(f"Error collecting genre recommendations: {e}", exc_info=True)

        return collected_movies[:max_results]

    async def generate_genre_recommendations_sync(
        self,
        genres: List[str],
        min_rating: float,
        max_results: int = 24,
        queue_timeout: float = 60.0
    ) -> List[Dict[str, Any]]:
        """
        Always triggers the Airflow DAG using 'default_username' to generate fallback recommendations,
        then subscribes to the RECS_QUEUE and filters movies by genres and minimum rating.

        :param genres: List of preferred genres (case-insensitive)
        :param min_rating: Minimum rating threshold
        :param max_results: Maximum number of movies to return
        :param queue_timeout: Max seconds to wait for messages from the queue
        :return: List of Movie objects
        """
        try:
            await self.trigger_airflow_recommendation(
                username="default_username",
                opt_in=False,
                extra_conf={
                    "genres": genres,
                    "minimum_rating": min_rating,
                    "type": "fallback",
                }
            )
        except HTTPException as e:
            logger.warning(f"Airflow DAG trigger failed: {e.detail}")

        return await run_in_threadpool(
            self._collect_genre_recommendations_sync, genres, min_rating, max_results, queue_timeout
        )

    def get_random_movies(self, n: int = 24) -> List[Dict[str, Any]]:
        """
        Fetch n random movies from MongoDB.
        Results are cached in Redis for 60 s to avoid hammering the DB on repeated clicks.
        Uses $sample aggregation — O(1) vs the old skip-per-document approach.
        """
        cache_key = "random_movies_cache"
        cached = self.client.get(cache_key)
        if cached:
            return json.loads(cached)

        mongo = MongoDBClient()
        collection = mongo.client[mongo.database].movies

        # Oversample so we have enough after filtering incomplete docs
        pipeline = [
            {"$match": {
                "poster_url": {"$exists": True, "$ne": ""},
                "histogram":  {"$exists": True, "$ne": {}},
                "movie_title": {"$exists": True, "$ne": ""},
            }},
            {"$sample": {"size": n}},
        ]
        docs = list(collection.aggregate(pipeline))

        random_movies = [
            {
                "id": doc.get("movie_title_formatted", doc.get("movie_title")),
                "movie_title": doc.get("movie_title", ""),
                "movie_title_formatted": doc.get("movie_title_formatted", ""),
                "year": doc.get("year", 0),
                "lb_rating": float(doc.get("lb_rating", 0.0)),
                "runtime": doc.get("runtime", 0),
                "source": "Randomizer",
                "genres": doc.get("genres", []),
                "poster_url": doc.get("poster_url"),
                "histogram": doc.get("histogram", {}),
            }
            for doc in docs
        ]

        self.client.setex(cache_key, 60, json.dumps(random_movies))
        return random_movies

    def add_to_top_picks(self, movie: MovieTopPick):
        """
        Adds a movie to top picks in Redis with count tracking.
        Uses 'movie_title_formatted' as the unique key.
        """
        movie_id = movie.movie_title_formatted
        if not movie_id:
            raise ValueError("Movie must have 'movie_title_formatted' as a unique identifier.")
        movie_dict = movie.model_dump()
        self.client.hset("top_picks", f"{movie_id}:info", json.dumps(movie_dict))
        self.client.hincrby("top_picks", f"{movie_id}:count", 1)
        logger.info(f"Movie '{movie.movie_title}' added to top picks with updated count.")
    
    def remove_from_top_picks(self, movie: MovieTopPick):
        """
        Removes a movie from top picks in Redis with count tracking.
        Uses 'movie_title_formatted' as the unique key.
        Decrements the count and removes the movie entirely when count reaches 0.
        """
        movie_id = movie.movie_title_formatted
        if not movie_id:
            raise ValueError("Movie must have 'movie_title_formatted' as a unique identifier.")

        new_count = self.client.hincrby("top_picks", f"{movie_id}:count", -1)
        if new_count <= 0:
            self.client.hdel("top_picks", f"{movie_id}:info", f"{movie_id}:count")
            logger.info(f"Movie '{movie.movie_title}' removed from top picks (count reached 0).")
        else:
            logger.info(f"Movie '{movie.movie_title}' count decremented to {new_count} in top picks.")
        
    def get_top_picks(self, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Retrieves top picks from Redis, sorted by popularity (count), limited to `limit`.
        Returns movie_title_formatted, poster_url, and pick_count for each movie.
        """
        movies: List[Dict[str, Any]] = []

        keys = self.client.hkeys("top_picks")
        movie_ids = set(k.decode().split(":")[0] for k in keys)

        for movie_id in movie_ids:
            info_json = self.client.hget("top_picks", f"{movie_id}:info")
            count_bytes = self.client.hget("top_picks", f"{movie_id}:count")
            if not info_json or not count_bytes:
                continue

            info = json.loads(info_json)
            count = int(count_bytes)

            movies.append({
                "movie_title_formatted": info.get("movie_title_formatted"),
                "poster_url": info.get("poster_url"),
                "pick_count": count
            })

        movies.sort(key=lambda m: m["pick_count"], reverse=True)

        return movies[:limit]
    
    async def get_calendar_releases(self) -> List[Dict[str, Any]]:
        return await self.fetch_from_redis("upcoming_releases")

    async def get_announcements(self) -> List[Dict[str, Any]]:
        items = await self.fetch_from_redis("announcements")
        if items:
            return items
        return [
            {
                "id": "welcome",
                "title": "Welcome to Letterboxd Recs!",
                "message": "Get personalized movie recommendations based on your Letterboxd history.",
            },
            {
                "id": "new-calendar",
                "title": "New: Upcoming Releases Calendar",
                "message": "Check out the new calendar page to see what's coming to theaters soon.",
            },
            {
                "id": "top-picks",
                "title": "Top Picks Now Live",
                "message": "See what movies other users are picking this week on the home page.",
            },
        ]

app = FastAPI(title="Middleware", version="2.2.0")

app.add_middleware(GZipMiddleware, minimum_size=1000)

ALLOWED_HOSTS = [
    "localhost",
    "localhost:8000",
    "127.0.0.1",
    "127.0.0.1:8000",
]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

limiter = Limiter(key_func=get_remote_address, default_limits=["100/hour"])
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

MIDDLEWARE_API_KEY = os.getenv("MIDDLEWARE_API_KEY")

if not MIDDLEWARE_API_KEY:
    logger.warning("MIDDLEWARE_API_KEY not set! API will be vulnerable.")

async def require_api_key(
    request: Request,
    x_api_key: str = Header(None, description="API Key for authentication")
):
    """Validates the API key from request headers with IP blocking."""
    
    if request.method == "OPTIONS":
        return None

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
        
    client_ip = request.client.host if request.client else "unknown"

    if ip_blocker.is_blocked(client_ip):
        security_monitor.log_security_event(
            "BLOCKED_IP_ATTEMPT", client_ip,
            "Attempted access from blocked IP", "ERROR"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="IP address temporarily blocked due to multiple failed attempts"
        )

    if not ip_whitelist.is_whitelisted(client_ip):
        security_monitor.log_security_event(
            "IP_NOT_WHITELISTED", client_ip,
            "Access attempt from non-whitelisted IP", "WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="IP address not authorized"
        )

    if not MIDDLEWARE_API_KEY:
        logger.error("API key validation skipped - MIDDLEWARE_API_KEY not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error"
        )

    if x_api_key != MIDDLEWARE_API_KEY:
        should_block = ip_blocker.record_failed_attempt(client_ip)
        security_monitor.log_security_event(
            "INVALID_API_KEY",
            client_ip,
            f"Invalid API key provided. Blocked: {should_block}",
            "ERROR" if should_block else "WARNING"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    ip_blocker.reset_attempts(client_ip)
    return x_api_key

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

MAX_REQUEST_SIZE = int(os.getenv("MAX_REQUEST_SIZE"))

@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Limit request body size to prevent abuse."""
    if request.method in ["POST", "PUT", "PATCH"]:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_SIZE:
            logger.warning(f"Request too large: {content_length} bytes from {request.client.host}")
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Request body too large"}
            )
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)

middleware_service = MiddlewareService()

# TODO = response_models

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment verification."""
    return {
        "status": "healthy",
        "service": "letterboxd-middleware",
        "version": "2.2.0"
    }

@app.post("/recommend/trigger")
async def rec_api_call(data: RecommendationTrigger = Body(...)):
    extra_conf = {"type": "letterboxd"}
    if data.run_id:
        extra_conf["run_id"] = data.run_id
    result = await middleware_service.trigger_airflow_recommendation(data.letterboxd_username, data.data_opt_in, extra_conf=extra_conf)
    return TriggerResponse(**result)

@app.post("/recommend/fallback")
async def fallback_rec_api_call(data: FallbackRecommendationTrigger):
    return await middleware_service.generate_genre_recommendations_sync(data.genres, data.minimum_rating)

def _sanitize(obj: Any) -> Any:
    """Recursively replace nan/inf float values with None for JSON compliance."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj

@app.get("/recommend/results")
async def get_user_results(username: str, run_id: Optional[str] = None):
    """Non-blocking read from per-user Redis key. Returns user_recommendation and user_analytics if available."""
    def _get():
        key = f"recs:{username}:{run_id}" if run_id else f"recs:{username}"
        result = middleware_service.client.get(key)
        if result:
            data = json.loads(result)
            return _sanitize({
                "user_recommendation": data.get("user_recommendation", []),
                "user_analytics": data.get("user_analytics", {}),
            })
        return None
    return await run_in_threadpool(_get)

@app.get("/recommend/recent")
async def get_recently_recommended():
    return await middleware_service.fetch_from_redis("recently_recommended")

@app.get("/recommend/popular")
async def get_popular_movies():
    return await middleware_service.fetch_from_redis("popular_movies")

@app.get("/recommend/random")
async def get_random_movies_endpoint():
    """
    Retrieves 24 random movies directly from MongoDB.
    """
    return await run_in_threadpool(middleware_service.get_random_movies, 24)

@app.get("/recommend/top-picks")
async def get_top_picks_endpoint():
    """
    Retrieve top picks from Redis, sorted by popularity (count), limited to 15.
    """
    return await run_in_threadpool(middleware_service.get_top_picks, 15)

@app.post("/recommend/add-top-pick")
async def publish_top_pick_endpoint(movie: MovieTopPick):
    """
    Publish a movie to top picks using 'movie_title_formatted' as the unique key.
    """
    await run_in_threadpool(middleware_service.add_to_top_picks, movie)

@app.post("/recommend/remove-top-pick")
async def remove_top_pick_endpoint(movie: MovieTopPick):
    """
    Remove a movie from top picks using 'movie_title_formatted' as the unique key.
    """
    await run_in_threadpool(middleware_service.remove_from_top_picks, movie)

@app.get("/announcements")
async def get_announcements_endpoint():
    """
    Fetches announcements from Redis.
    """
    return await middleware_service.get_announcements()

@app.get("/calendar/releases")
async def get_calendar_releases_endpoint():
    """
    Fetches upcoming movie releases from Redis.
    """
    return await middleware_service.fetch_from_redis("upcoming_releases")


@app.get("/admin/security/blocked-ips", dependencies=[Depends(require_api_key)])
async def get_blocked_ips():
    """
    Get list of currently blocked IPs.
    Requires API key authentication.
    """
    blocked = ip_blocker.get_blocked_ips()
    return {
        "blocked_ips": list(blocked),
        "count": len(blocked),
        "block_duration_seconds": ip_blocker.block_duration
    }

@app.post("/admin/security/unblock-ip", dependencies=[Depends(require_api_key)])
async def unblock_ip(ip_address: str = Body(..., embed=True)):
    """
    Manually unblock an IP address.
    Requires API key authentication.
    """
    ip_blocker.unblock_ip(ip_address)
    security_monitor.log_security_event(
        "MANUAL_UNBLOCK", ip_address,
        "IP manually unblocked via admin endpoint", "INFO"
    )
    return {"status": "success", "message": f"IP {ip_address} unblocked"}

@app.get("/admin/security/stats")
async def get_security_stats(request: Request, api_key: str = Depends(require_api_key)):
    """
    Get security statistics and system status.
    Requires API key authentication.
    """
    return {
        "blocked_ips_count": len(ip_blocker.get_blocked_ips()),
        "rate_limiter_enabled": True,
        "ip_whitelist_enabled": bool(ip_whitelist.whitelist),
        "whitelisted_ips_count": len(ip_whitelist.whitelist),
        "max_failed_attempts": ip_blocker.max_attempts,
        "block_duration_hours": ip_blocker.block_duration / 3600,
    }


if __name__ == "__main__":
    uvicorn.run(
        "middleware.middleware:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
    