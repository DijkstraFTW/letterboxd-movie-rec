import json
import os
import time
import random

from dotenv import load_dotenv
from database.mongodb_client import MongoDBClient
from messaging.redis_client import RedisClient
from app_logger.app_logger import setup_logger
from middleware.security_utils import ip_blocker, ip_whitelist, security_monitor
from typing import List, Dict, Any, Optional

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

logger = setup_logger("../logs/middleware.log", "MiddlewareLogger")
load_dotenv()

class Movie(BaseModel):
    id: int
    title: str
    year: int
    rating: float
    source: str
    genres: Optional[List[str]] = []
    poster_url: Optional[str] = None

class RecommendationTrigger(BaseModel):
    letterboxd_username: str
    data_opt_in: bool

class FallbackRecommendationTrigger(BaseModel):
    genres: List[str] = Field(..., description="Preferred genres (e.g., ['Action', 'Sci-Fi'])")
    minimum_rating: float = Field(..., ge=0.0, le=5.0, description="Minimum user rating (0.0-5.0)")

class TriggerResponse(BaseModel):
    status: str
    message: str
    dag_run_id: Optional[str] = None
    
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
        self.airflow_api_token = os.getenv("AIRFLOW_API_TOKEN")
        self.recs_queue = os.getenv("REDIS_QUEUE_RECS")
        self.redis_client = RedisClient()
        self.client = self.redis_client.client
        self.redis_db = {}

    def _fetch_from_redis_sync(self, key: str) -> List[Dict[str, Any]]:
        time.sleep(0.01)
        return self.redis_db.get(key, [])

    async def fetch_from_redis(self, key: str) -> List[Dict[str, Any]]:
        return await run_in_threadpool(self._fetch_from_redis_sync, key)

    def add_to_redis(self, key: str, movie: Dict[str, Any]) -> None:
        if key not in self.redis_db:
            self.redis_db[key] = []
        self.redis_db[key].append(movie)
        logger.info(f"Added movie '{movie['title']}' to '{key}'")

    async def trigger_airflow_recommendation(self, username: str, opt_in: bool, timeout: float = 15.0) -> Dict[str, str]:
        """
        Triggers an Airflow DAG asynchronously using HTTPX.

        :param username: Letterboxd username
        :param opt_in: Whether user opted into data sharing
        :param timeout: HTTP request timeout in seconds
        :return: Dictionary with DAG trigger info
        """
        endpoint = f"{self.airflow_base_url}/dags/{self.airflow_dag_id}/dagRuns"
        payload = {
            "conf": {
                "letterboxd_username": username,
                "data_opt_in": opt_in,
                "request_timestamp": int(time.time())
            }
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.airflow_api_token}"
        }

        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"Triggering Airflow DAG '{self.airflow_dag_id}' for user '{username}'")
                response = await client.post(endpoint, json=payload, headers=headers, timeout=timeout)
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


    async def generate_genre_recommendations_sync(
        self,
        genres: List[str],
        min_rating: float,
        max_results: int = 24,
        queue_timeout: float = 1.0
    ) -> List[Movie]:
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
            await self.trigger_airflow_recommendation(username="default_username", opt_in=False)
        except HTTPException as e:
            logger.warning(f"Airflow DAG trigger failed: {e.detail}")

        genres_lower = {g.lower() for g in genres}
        collected_movies = []
        seen_ids = set()

        pubsub = self.client.pubsub()
        pubsub.subscribe(self.recs_queue)

        start_time = time.time()
        try:
            for message in pubsub.listen():
                if time.time() - start_time > queue_timeout:
                    break

                if message["type"] != "message":
                    continue

                try:
                    data = json.loads(message["data"])
                    for m in data.get("user_recommendation", []):
                        movie_id = m.get("id")
                        if movie_id in seen_ids:
                            continue

                        movie_genres = [g.lower() for g in m.get("genres", [])]
                        if m["rating"] >= min_rating and (not genres or genres_lower & set(movie_genres)):
                            collected_movies.append(
                                Movie(
                                    id=m["id"],
                                    title=m["title"],
                                    year=m["year"],
                                    rating=m["rating"],
                                    source=f"Fallback ({'/'.join(genres)}, >{min_rating})",
                                    genres=m.get("genres", []),
                                    poster_url=m.get("poster_url")
                                )
                            )
                            seen_ids.add(movie_id)

                        if len(collected_movies) >= max_results:
                            break
                except Exception:
                    continue

                if len(collected_movies) >= max_results:
                    break
        finally:
            pubsub.close()

        return collected_movies[:max_results]

    def get_random_movies(self, n: int = 24) -> List[Movie]:
        """
        Fetch n random movies directly from MongoDB using MongoDBClient.
        """
        mongo = MongoDBClient()
        collection = mongo.client[mongo.database].movies
        total = collection.count_documents({})
        if total == 0:
            return []

        random_indexes = random.sample(range(total), min(n, total))
        random_movies = []

        for idx in random_indexes:
            movie_doc = collection.find().skip(idx).limit(1)[0] # to improve collection.aggregate([{"$sample": {"size": n}}])
            random_movies.append(
                Movie(
                    id=movie_doc.get("movie_title_formatted", movie_doc.get("movie_title")),
                    title=movie_doc["movie_title"],
                    year=movie_doc.get("year", 0),
                    rating=float(movie_doc.get("lb_rating", 0.0)),
                    source="Randomizer",
                    genres=movie_doc.get("genres", []),
                    poster_url=movie_doc.get("poster_url")
                )
            )

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

app = FastAPI(title="Middleware", version="2.2.0")

ALLOWED_ORIGINS = ["http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
    max_age=600,
)

ALLOWED_HOSTS = ["localhost"]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

app.add_middleware(GZipMiddleware, minimum_size=1000)

limiter = Limiter(key_func=get_remote_address, default_limits=["100/hour"])
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

MIDDLEWARE_API_KEY = "1DU3QxCx0lY3IFwp9aklWKbAtrbvIRfD"
if not MIDDLEWARE_API_KEY:
    logger.warning("MIDDLEWARE_API_KEY not set! API will be vulnerable.")

async def require_api_key(
    request: Request,
    x_api_key: str = Header(..., description="API Key for authentication")
):
    """Validates the API key from request headers with IP blocking."""
    client_ip = request.client.host if request.client else "unknown"

    # Check if IP is blocked
    if ip_blocker.is_blocked(client_ip):
        security_monitor.log_security_event(
            "BLOCKED_IP_ATTEMPT", client_ip,
            "Attempted access from blocked IP", "ERROR"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="IP address temporarily blocked due to multiple failed attempts"
        )

    # Check if IP whitelist is enabled and IP is allowed
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
        # Record failed attempt and potentially block IP
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

@app.post("/recommend/trigger", dependencies=[Depends(require_api_key)])
async def rec_api_call(data: RecommendationTrigger = Body(...)):
    result = await middleware_service.trigger_airflow_recommendation(data.letterboxd_username, data.data_opt_in)
    return TriggerResponse(**result)

@app.post("/recommend/fallback", dependencies=[Depends(require_api_key)])
async def fallback_rec_api_call(data: FallbackRecommendationTrigger):
    return await run_in_threadpool(middleware_service.generate_genre_recommendations_sync, data.genres, data.minimum_rating)

@app.get("/recommend/recent", dependencies=[Depends(require_api_key)])
async def get_recently_recommended():
    #return await middleware_service.fetch_from_redis("recently_recommended")
    return {
        "movies": [
                    {
                        "movie_title_formatted": "sicario-day-of-the-soldado",
                        "movie_title": "Sicario: Day of the Soldado",
                        "type": "movie",
                        "year_released": 2018,
                        "imdb_link": "http://www.imdb.com/title/tt5052474/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/400535/",
                        "imdb_id": "tt5052474",
                        "tmdb_id": "400535",
                        "lb_rating": "3.2",
                        "histogram": {
                        "1.0": 492,
                        "2.0": 1368,
                        "3.0": 1940,
                        "4.0": 7368,
                        "5.0": 11509,
                        "6.0": 29427,
                        "7.0": 26942,
                        "8.0": 17475,
                        "9.0": 2922,
                        "10.0": 2512,
                        "fans": 68,
                        "lb_rating": "3.2",
                        "total": 101955
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/3/3/5/2/9/4/335294-sicario-day-of-the-soldado-0-230-0-345-crop.jpg",
                        "genres": ["Action", "Crime", "Thriller"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English", "Español"],
                        "popularity": 63.776,
                        "overview": "Agent Matt Graver teams up with operative Alejandro Gillick to prevent Mexican drug cartels from smuggling terrorists across the United States border.",
                        "runtime": 122,
                        "vote_average": 6.918,
                        "vote_count": 3393,
                        "release_date": "2018-06-27",
                        "original_language": "en",
                        "themes": [
                        "High speed and special ops",
                        "Politics and human rights",
                        "Crime, drugs and gangsters",
                        "Intense political and terrorist thrillers",
                        "Exciting spy thrillers with tense intrigue",
                        "Violent action, guns, and crime",
                        "Explosive and action-packed heroes vs. villains",
                        "Violent crime and drugs"
                        ],
                        "nanogenres": [
                        "Terrorism, Government, Cia",
                        "Thriller, Unpredictable, Unexpected",
                        "Powerful, Storytelling, Complexity",
                        "Violence, Dark, Unexpected",
                        "Friendship, Realism, Dangerous",
                        "Thriller, Terror, Dark",
                        "Villain, Bullets, Criminal",
                        "Terrorism, Attacks, Bombing",
                        "Villain, Cliche, Action-Packed",
                        "Killing, Shootings, Extreme"
                        ]
                    },
                    {
                        "movie_title_formatted": "mission-impossible-iii",
                        "movie_title": "Mission: Impossible III",
                        "type": "movie",
                        "year_released": 2006,
                        "imdb_link": "http://www.imdb.com/title/tt0317919/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/956/",
                        "imdb_id": "tt0317919",
                        "tmdb_id": "956",
                        "lb_rating": "3.3",
                        "histogram": {
                        "1.0": 530,
                        "2.0": 1894,
                        "3.0": 2340,
                        "4.0": 12349,
                        "5.0": 20584,
                        "6.0": 79300,
                        "7.0": 74869,
                        "8.0": 54423,
                        "9.0": 9461,
                        "10.0": 8497,
                        "fans": 136,
                        "lb_rating": "3.3",
                        "total": 264247
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/1/2/0/4/51204-mission-impossible-iii-0-230-0-345-crop.jpg",
                        "genres": ["Adventure", "Action", "Thriller"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["Deutsch", "English", "Italiano", "普通话", "Český", "广州话 / 廣州話"],
                        "popularity": 49.344,
                        "overview": "Retired from active duty, and training recruits for the Impossible Mission Force, agent Ethan Hunt faces the toughest foe of his career: Owen Davian, an international broker of arms and information, who is as cunning as he is ruthless. Davian emerges to threaten Hunt and all that he holds dear -- including the woman Hunt loves.",
                        "runtime": 126,
                        "vote_average": 6.7,
                        "vote_count": 6497,
                        "release_date": "2006-04-25",
                        "original_language": "en",
                        "themes": [
                        "High speed and special ops",
                        "Epic heroes",
                        "Explosive and action-packed heroes vs. villains",
                        "Adrenaline-fueled action and fast cars",
                        "Exciting spy thrillers with tense intrigue",
                        "Superheroes in action-packed battles with villains",
                        "Intense political and terrorist thrillers"
                        ],
                        "nanogenres": [
                        "Action, Spy, Secret",
                        "Tense, Explosives, Bullets",
                        "Fighting, Shootout, Mindless",
                        "Suspense, Slick, Stylish",
                        "Suspense, Guns, Action-Packed",
                        "Stunts, Bullets, Speed",
                        "Jokes, Guns, Cool",
                        "Thriller, Explosives, Danger",
                        "Thrills, Stunts, Villain",
                        "Fighting, Thrills, Violence"
                        ]
                    },
                    {
                        "movie_title_formatted": "dune-part-two",
                        "movie_title": "Dune: Part Two",
                        "type": "movie",
                        "year_released": 2024,
                        "imdb_link": "http://www.imdb.com/title/tt15239678/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/693134/",
                        "imdb_id": "tt15239678",
                        "tmdb_id": "693134",
                        "lb_rating": "4.5",
                        "histogram": {
                        "1.0": 1415,
                        "2.0": 2279,
                        "3.0": 1593,
                        "4.0": 7662,
                        "5.0": 10964,
                        "6.0": 44282,
                        "7.0": 76174,
                        "8.0": 264286,
                        "9.0": 321268,
                        "10.0": 613673,
                        "fans": 46000,
                        "lb_rating": "4.5",
                        "total": 1343596
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/6/1/7/4/4/3/617443-dune-part-two-0-230-0-345-crop.jpg",
                        "genres": ["Science Fiction", "Adventure"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 1618.076,
                        "overview": "Follow the mythic journey of Paul Atreides as he unites with Chani and the Fremen while on a path of revenge against the conspirators who destroyed his family. Facing a choice between the love of his life and the fate of the known universe, Paul endeavors to prevent a terrible future only he can foresee.",
                        "runtime": 167,
                        "vote_average": 8.3,
                        "vote_count": 3286,
                        "release_date": "2024-02-27",
                        "original_language": "en",
                        "themes": [
                        "Epic heroes",
                        "Humanity and the world around us",
                        "Superheroes in action-packed battles with villains",
                        "Action-packed space and alien sagas",
                        "Thought-provoking sci-fi action and future technology",
                        "Emotional and captivating fantasy storytelling",
                        "Historical battles and epic heroism"
                        ],
                        "nanogenres": [
                        "Space, Technology, Vision",
                        "Action, Epic, Emotion",
                        "Spaceship, Explosives, Destruction",
                        "Planet, Humanity, Future",
                        "Imaginative, Breathtaking, Technology",
                        "Future, Thought-Provoking, Philosophical",
                        "Suspense, Guns, Action-Packed",
                        "Fighting, Evil, Exciting",
                        "Hero, Future, Vision",
                        "Combat, Swords, Weapons"
                        ]
                    },
                    {
                        "movie_title_formatted": "dune-2021",
                        "movie_title": "Dune",
                        "type": "movie",
                        "year_released": 2021,
                        "imdb_link": "http://www.imdb.com/title/tt1160419/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/438631/",
                        "imdb_id": "tt1160419",
                        "tmdb_id": "438631",
                        "lb_rating": "3.9",
                        "histogram": {
                        "1.0": 7586,
                        "2.0": 21709,
                        "3.0": 10826,
                        "4.0": 65934,
                        "5.0": 57377,
                        "6.0": 252563,
                        "7.0": 281523,
                        "8.0": 695835,
                        "9.0": 333093,
                        "10.0": 382719,
                        "fans": 22000,
                        "lb_rating": "3.9",
                        "total": 2109165
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/sm/upload/nx/8b/vs/gc/cDbNAY0KM84cxXhmj8f0dLWza3t-0-230-0-345-crop.jpg",
                        "genres": ["Science Fiction", "Adventure"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["普通话", "English"],
                        "popularity": 535.213,
                        "overview": "Paul Atreides, a brilliant and gifted young man born into a great destiny beyond his understanding, must travel to the most dangerous planet in the universe to ensure the future of his family and his people. As malevolent forces explode into conflict over the planet's exclusive supply of the most precious resource in existence-a commodity capable of unlocking humanity's greatest potential-only those who can conquer their fear will survive.",
                        "runtime": 155,
                        "vote_average": 7.789,
                        "vote_count": 11363,
                        "release_date": "2021-09-15",
                        "original_language": "en",
                        "themes": [
                        "Epic heroes",
                        "Monsters, aliens, sci-fi and the apocalypse",
                        "Action-packed space and alien sagas",
                        "Thought-provoking sci-fi action and future technology",
                        "Superheroes in action-packed battles with villains",
                        "Imaginative space odysseys and alien encounters",
                        "Emotional and captivating fantasy storytelling"
                        ],
                        "nanogenres": [
                        "Space, Technology, Vision",
                        "Action, Epic, Emotion",
                        "Spaceship, Explosives, Destruction",
                        "Fighting, Killing, Evil",
                        "Explosives, Cool, Exciting",
                        "Cool, Monster, Darkness",
                        "Battle, Destruction, Weapons",
                        "Weird, Chilling, Mystery",
                        "Graphics, Anticipation, Creativity",
                        "Predictable, Wins, Gorgeous"
                        ]
                    },
                    {
                        "movie_title_formatted": "past-lives",
                        "movie_title": "Past Lives",
                        "type": "movie",
                        "year_released": 2023,
                        "imdb_link": "http://www.imdb.com/title/tt13238346/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/666277/",
                        "imdb_id": "tt13238346",
                        "tmdb_id": "666277",
                        "lb_rating": "4.2",
                        "histogram": {
                        "1.0": 1219,
                        "2.0": 2546,
                        "3.0": 2120,
                        "4.0": 10840,
                        "5.0": 14942,
                        "6.0": 59817,
                        "7.0": 93778,
                        "8.0": 259379,
                        "9.0": 180620,
                        "10.0": 248161,
                        "fans": 23000,
                        "lb_rating": "4.2",
                        "total": 873422
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/9/1/0/5/3/591053-past-lives-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "Romance"],
                        "production_countries": ["South Korea", "United States of America"],
                        "spoken_languages": ["English", "한국어/조선말"],
                        "popularity": 93.056,
                        "overview": "Nora and Hae Sung, two childhood friends, are reunited in New York for one fateful week as they confront notions of destiny, love, and the choices that make a life.",
                        "runtime": 106,
                        "vote_average": 7.798,
                        "vote_count": 1239,
                        "release_date": "2023-06-02",
                        "original_language": "en",
                        "themes": [
                        "Moving relationship stories",
                        "Touching and sentimental family stories",
                        "Powerful stories of heartbreak and suffering",
                        "Captivating relationships and charming romance",
                        "Tragic sadness and captivating beauty",
                        "Passion and romance"
                        ],
                        "nanogenres": [
                        "Feelings, Moving, Crying",
                        "Drama, Cry, Endearing",
                        "Touching, Chemistry, Marriage",
                        "Romance, Sympathy, Desire",
                        "Relationships, Storytelling, Complexity",
                        "Relationships, Friendship, Sweet",
                        "Touching, Beauty, Desire",
                        "Powerful, Loving, Sentimental",
                        "Cry, Confused, Child",
                        "Charming, Magic, Dream"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-talented-mr-ripley",
                        "movie_title": "The Talented Mr. Ripley",
                        "type": "movie",
                        "year_released": 1999,
                        "imdb_link": "http://www.imdb.com/title/tt0134119/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/1213/",
                        "imdb_id": "tt0134119",
                        "tmdb_id": "1213",
                        "lb_rating": "3.8",
                        "histogram": {
                        "1.0": 414,
                        "2.0": 1215,
                        "3.0": 1222,
                        "4.0": 6486,
                        "5.0": 9562,
                        "6.0": 41864,
                        "7.0": 65258,
                        "8.0": 108969,
                        "9.0": 37067,
                        "10.0": 32404,
                        "fans": 4800,
                        "lb_rating": "3.8",
                        "total": 304461
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/1/1/3/8/51138-the-talented-mr-ripley-0-230-0-345-crop.jpg",
                        "genres": ["Thriller", "Crime", "Drama"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English", "Italiano"],
                        "popularity": 37.922,
                        "overview": "Tom Ripley is a calculating young man who believes it's better to be a fake somebody than a real nobody. Opportunity knocks in the form of a wealthy U.S. shipbuilder who hires Tom to travel to Italy to bring back his playboy son, Dickie. Ripley worms his way into the idyllic lives of Dickie and his girlfriend, plunging into a daring scheme of duplicity, lies and murder.",
                        "runtime": 139,
                        "vote_average": 7.188,
                        "vote_count": 3482,
                        "release_date": "1999-12-25",
                        "original_language": "en",
                        "themes": [
                        "Intense violence and sexual transgression",
                        "Humanity and the world around us",
                        "Thrillers and murder mysteries",
                        "Twisted dark psychological thriller",
                        "Intriguing and suspenseful murder mysteries",
                        "Suspenseful crime thrillers",
                        "Captivating relationships and charming romance",
                        "Noir and dark crime dramas"
                        ],
                        "nanogenres": [
                        "Weird, Disturbing, Intriguing",
                        "Suspense, Unexpected, Engaging",
                        "Murderer, Compelling, Sympathy",
                        "Romance, Sensitive, Lonely",
                        "Thriller, Psychotic, Dark",
                        "Suspense, Criminal, Film-Noir",
                        "Victim, Tense, Detective",
                        "Drama, Gripping, Vulnerable",
                        "Murder, Frighten, Mysterious",
                        "Detective, Twisted, Disturbed"
                        ]
                    },
                    {
                        "movie_title_formatted": "joker-2019",
                        "movie_title": "Joker",
                        "type": "movie",
                        "year_released": 2019,
                        "imdb_link": "http://www.imdb.com/title/tt7286456/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/475557/",
                        "imdb_id": "tt7286456",
                        "tmdb_id": "475557",
                        "lb_rating": "3.8",
                        "histogram": {
                        "1.0": 9828,
                        "2.0": 25508,
                        "3.0": 16395,
                        "4.0": 86737,
                        "5.0": 73912,
                        "6.0": 334163,
                        "7.0": 306361,
                        "8.0": 822871,
                        "9.0": 298212,
                        "10.0": 596197,
                        "fans": 22000,
                        "lb_rating": "3.8",
                        "total": 2570184
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/4/0/6/7/7/5/406775-joker-0-230-0-345-crop.jpg",
                        "genres": ["Crime", "Thriller", "Drama"],
                        "production_countries": ["Canada", "United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 312.884,
                        "overview": "During the 1980s, a failed stand-up comedian is driven insane and turns to a life of crime and chaos in Gotham City while becoming an infamous psychopathic crime figure.",
                        "runtime": 122,
                        "vote_average": 8.161,
                        "vote_count": 24452,
                        "release_date": "2019-10-01",
                        "original_language": "en",
                        "themes": [
                        "Intense violence and sexual transgression",
                        "Moving relationship stories",
                        "Humanity and the world around us",
                        "Crime, drugs and gangsters",
                        "Powerful stories of heartbreak and suffering",
                        "Gripping, intense violent crime",
                        "Challenging or sexual themes & twists",
                        "Emotional and captivating fantasy storytelling",
                        "Graphic violence and brutal revenge"
                        ],
                        "nanogenres": [
                        "Comic-Book, Hero, Exciting",
                        "Gory, Brutal, Extreme",
                        "Terrifying, Disturbed, Troubled",
                        "Chilling, Fear, Extreme",
                        "Shootings, Troubled, Confused",
                        "Emotion, Insanity, Mentally",
                        "Tense, Captivating, Unpredictable",
                        "Bloody, Dark, Intense",
                        "Intense, Storytelling, Compelling",
                        "Emotional, Madness, Sympathy"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-social-network",
                        "movie_title": "The Social Network",
                        "type": "movie",
                        "year_released": 2010,
                        "imdb_link": "http://www.imdb.com/title/tt1285016/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/37799/",
                        "imdb_id": "tt1285016",
                        "tmdb_id": "37799",
                        "lb_rating": "4.0",
                        "histogram": {
                        "1.0": 2701,
                        "2.0": 9573,
                        "3.0": 5307,
                        "4.0": 44698,
                        "5.0": 36360,
                        "6.0": 226230,
                        "7.0": 197799,
                        "8.0": 480848,
                        "9.0": 200002,
                        "10.0": 306040,
                        "fans": 30000,
                        "lb_rating": "4.0",
                        "total": 1509558
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/sm/upload/nw/cm/pa/ai/sGQv3ZMZBDBnl3z42Q0mEQ5uiDe-0-230-0-345-crop.jpg",
                        "genres": ["Drama"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 53.328,
                        "overview": "In 2003, Harvard undergrad and computer genius Mark Zuckerberg begins work on a new concept that eventually turns into the global social network known as Facebook. Six years later, he is one of the youngest billionaires ever, but Zuckerberg finds that his unprecedented success leads to both personal and legal complications when he ends up on the receiving end of two lawsuits, one involving his former friend.",
                        "runtime": 121,
                        "vote_average": 7.364,
                        "vote_count": 11653,
                        "release_date": "2010-10-01",
                        "original_language": "en",
                        "themes": [
                        "Humanity and the world around us",
                        "Teen school antics and laughter",
                        "Student coming-of-age challenges",
                        "Fascinating, emotional stories and documentaries"
                        ],
                        "nanogenres": [
                        "Geeks, Technology, Excitement",
                        "Relationships, Geeks, Obsession",
                        "Emotional, Biography, Facts",
                        "Cliche, College, School",
                        "College, Nerds, Silly",
                        "College, Girlfriend, Lesson",
                        "Drama, Sympathy, Complicated",
                        "Humor, Geeks, Cool",
                        "Friendship, Captivating, Soul",
                        "Cool, Intelligent, Stereotype"
                        ]
                    },
                    {
                        "movie_title_formatted": "oppenheimer-2023",
                        "movie_title": "Oppenheimer",
                        "type": "movie",
                        "year_released": 2023,
                        "imdb_link": "http://www.imdb.com/title/tt15398776/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/872585/",
                        "imdb_id": "tt15398776",
                        "tmdb_id": "872585",
                        "lb_rating": "4.2",
                        "histogram": {
                        "1.0": 4333,
                        "2.0": 9102,
                        "3.0": 5467,
                        "4.0": 31577,
                        "5.0": 32688,
                        "6.0": 146631,
                        "7.0": 181551,
                        "8.0": 542159,
                        "9.0": 446328,
                        "10.0": 678678,
                        "fans": 31000,
                        "lb_rating": "4.2",
                        "total": 2078514
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/7/8/4/3/2/8/784328-oppenheimer-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "History"],
                        "production_countries": ["United Kingdom", "United States of America"],
                        "spoken_languages": ["Nederlands", "English"],
                        "popularity": 477.921,
                        "overview": "The story of J. Robert Oppenheimer's role in the development of the atomic bomb during World War II.",
                        "runtime": 181,
                        "vote_average": 8.108,
                        "vote_count": 7733,
                        "release_date": "2023-07-19",
                        "original_language": "en",
                        "themes": [
                        "Humanity and the world around us",
                        "Politics and human rights",
                        "Epic history and literature",
                        "Intense political and terrorist thrillers",
                        "Riveting political and presidential drama",
                        "Dangerous technology and the apocalypse",
                        "Surreal and thought-provoking visions of life and death",
                        "Political drama, patriotism, and war"
                        ],
                        "nanogenres": [
                        "Intelligent, Thought-Provoking, Philosophical",
                        "Moving, Struggles, Riveting",
                        "Scientific, Thought-Provoking, Philosophy",
                        "Tear-Jerker, Breathtaking, Captivating",
                        "England, Civilian, Gripping",
                        "Touching, Historic, Nation",
                        "Reality, Revelation, Intellectual",
                        "Emotion, Humanity, Complexity",
                        "Thought-Provoking, Moral, Intellectual",
                        "Intense, Revelation, Fascinating"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-prestige",
                        "movie_title": "The Prestige",
                        "type": "movie",
                        "year_released": 2006,
                        "imdb_link": "http://www.imdb.com/title/tt0482571/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/1124/",
                        "imdb_id": "tt0482571",
                        "tmdb_id": "1124",
                        "lb_rating": "4.2",
                        "histogram": {
                        "1.0": 847,
                        "2.0": 2232,
                        "3.0": 1787,
                        "4.0": 10193,
                        "5.0": 12243,
                        "6.0": 63499,
                        "7.0": 95556,
                        "8.0": 275349,
                        "9.0": 187111,
                        "10.0": 227180,
                        "fans": 22000,
                        "lb_rating": "4.2",
                        "total": 875997
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/1/1/4/7/51147-the-prestige-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "Mystery", "Science Fiction"],
                        "production_countries": ["United Kingdom", "United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 80.535,
                        "overview": "A mysterious story of two magicians whose intense rivalry leads them on a life-long battle for supremacy -- full of obsession, deceit and jealousy with dangerous and deadly consequences.",
                        "runtime": 130,
                        "vote_average": 8.2,
                        "vote_count": 15386,
                        "release_date": "2006-10-19",
                        "original_language": "en",
                        "themes": [
                        "Thrillers and murder mysteries",
                        "Twisted dark psychological thriller",
                        "Intriguing and suspenseful murder mysteries",
                        "Intense political and terrorist thrillers"
                        ],
                        "nanogenres": [
                        "Dark, Storytelling, Captivating",
                        "Twist, Intriguing, Confusion",
                        "Twist, Sinister, Secret",
                        "Thriller, Climax, Riveting",
                        "Guessing, Thought-Provoking, Confusion",
                        "Tense, Mysterious, Solving",
                        "Suspense, Confused, Discover",
                        "Chemistry, Storytelling, Lover",
                        "Killing, Twist, Confused",
                        "Dark, Desire, Twisted"
                        ]
                    },
                    {
                        "movie_title_formatted": "mission-impossible-dead-reckoning-part-one",
                        "movie_title": "Mission: Impossible – Dead Reckoning Part One",
                        "type": "movie",
                        "year_released": 2023,
                        "imdb_link": "http://www.imdb.com/title/tt9603212/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/575264/",
                        "imdb_id": "tt9603212",
                        "tmdb_id": "575264",
                        "lb_rating": "3.7",
                        "histogram": {
                        "1.0": 1075,
                        "2.0": 2636,
                        "3.0": 2681,
                        "4.0": 11583,
                        "5.0": 17897,
                        "6.0": 62032,
                        "7.0": 95365,
                        "8.0": 162992,
                        "9.0": 62763,
                        "10.0": 39657,
                        "fans": 636,
                        "lb_rating": "3.7",
                        "total": 458681
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/0/3/4/0/2/503402-mission-impossible-dead-reckoning-part-one-0-230-0-345-crop.jpg",
                        "genres": ["Action", "Thriller"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["Français", "English", "Italiano", "Pусский"],
                        "popularity": 171.482,
                        "overview": "Ethan Hunt and his IMF team embark on their most dangerous mission yet: To track down a terrifying new weapon that threatens all of humanity before it falls into the wrong hands. With control of the future and the world's fate at stake and dark forces from Ethan's past closing in, a deadly race around the globe begins. Confronted by a mysterious, all-powerful enemy, Ethan must consider that nothing can matter more than his mission—not even the lives of those he cares about most.",
                        "runtime": 164,
                        "vote_average": 7.55,
                        "vote_count": 3342,
                        "release_date": "2023-07-08",
                        "original_language": "en",
                        "themes": [
                        "High speed and special ops",
                        "Epic heroes",
                        "Explosive and action-packed heroes vs. villains",
                        "Adrenaline-fueled action and fast cars",
                        "Superheroes in action-packed battles with villains",
                        "Exciting spy thrillers with tense intrigue",
                        "Heists and thrilling action"
                        ],
                        "nanogenres": [
                        "Action, Spy, Secret",
                        "Gadgets, Stunts, Agent",
                        "Fighting, Cool, Menacing",
                        "Thriller, Explosives, Danger",
                        "Jokes, Guns, Cool",
                        "Death, Stunts, Formulaic",
                        "Action, Thrills, Shootings",
                        "Thrills, Stunts, Villain",
                        "Stunts, Cars, Chasing",
                        "Villain, Cool, Chases"
                        ]
                    },
                    {
                        "movie_title_formatted": "avatar-the-way-of-water",
                        "movie_title": "Avatar: The Way of Water",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt1630029/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/76600/",
                        "imdb_id": "tt1630029",
                        "tmdb_id": "76600",
                        "lb_rating": "3.6",
                        "histogram": {
                        "1.0": 8013,
                        "2.0": 18840,
                        "3.0": 13763,
                        "4.0": 59089,
                        "5.0": 63137,
                        "6.0": 201025,
                        "7.0": 206460,
                        "8.0": 339319,
                        "9.0": 127502,
                        "10.0": 186852,
                        "fans": 6300,
                        "lb_rating": "3.6",
                        "total": 1224000
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/6/3/0/5/8/63058-avatar-the-way-of-water-0-230-0-345-crop.jpg",
                        "genres": ["Science Fiction", "Adventure", "Action"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 204.651,
                        "overview": "Set more than a decade after the events of the first film, learn the story of the Sully family (Jake, Neytiri, and their kids), the trouble that follows them, the lengths they go to keep each other safe, the battles they fight to stay alive, and the tragedies they endure.",
                        "runtime": 192,
                        "vote_average": 7.626,
                        "vote_count": 11200,
                        "release_date": "2022-12-14",
                        "original_language": "en",
                        "themes": [
                        "Monsters, aliens, sci-fi and the apocalypse",
                        "Epic heroes",
                        "Thought-provoking sci-fi action and future technology",
                        "Superheroes in action-packed battles with villains",
                        "Epic adventure and breathtaking battles",
                        "Emotional and captivating fantasy storytelling",
                        "Action-packed space and alien sagas"
                        ],
                        "nanogenres": [
                        "Emotional, Child, Wild",
                        "Tear-Jerker, Humans, Environment",
                        "Tear-Jerker, Magic, Captivating",
                        "Excitement, Engaging, Danger",
                        "Cry, Family, Environment",
                        "Touching, Breathtaking, Beauty",
                        "Touching, Tragic, Humanity",
                        "Action, Epic, Emotion",
                        "Action, Creature, Graphics",
                        "Adventure, Graphics, Fantasy"
                        ]
                    },
                    {
                        "movie_title_formatted": "creed-iii",
                        "movie_title": "Creed III",
                        "type": "movie",
                        "year_released": 2023,
                        "imdb_link": "http://www.imdb.com/title/tt11145118/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/677179/",
                        "imdb_id": "tt11145118",
                        "tmdb_id": "677179",
                        "lb_rating": "3.5",
                        "histogram": {
                        "1.0": 484,
                        "2.0": 1474,
                        "3.0": 1945,
                        "4.0": 9026,
                        "5.0": 16345,
                        "6.0": 54712,
                        "7.0": 69333,
                        "8.0": 74733,
                        "9.0": 19099,
                        "10.0": 14133,
                        "fans": 329,
                        "lb_rating": "3.5",
                        "total": 261284
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/6/0/1/6/2/4/601624-creed-iii-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "Action"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["Español", "English"],
                        "popularity": 128.241,
                        "overview": "After dominating the boxing world, Adonis Creed has thrived in his career and family life. When a childhood friend and former boxing prodigy, Damian Anderson, resurfaces after serving a long sentence in prison, he is eager to prove that he deserves his shot in the ring. The face-off between former friends is more than just a fight. To settle the score, Adonis must put his future on the line to battle Damian — a fighter with nothing to lose.",
                        "runtime": 116,
                        "vote_average": 7.125,
                        "vote_count": 2323,
                        "release_date": "2023-03-01",
                        "original_language": "en",
                        "themes": [
                        "Moving relationship stories",
                        "Underdog fighting and boxing stories"
                        ],
                        "nanogenres": [
                        "Boxing, Emotional, Sports",
                        "Fighter, Intense, Fought",
                        "Relationships, Dream, Desire",
                        "Predictable, Wins, Gorgeous",
                        "Compelling, Glory, Beloved",
                        "Fighter, Gritty, Wins",
                        "Cliche, Fighter, Flashy",
                        "Brutal, Battle, Fists",
                        "Feelings, Tragic, Anger",
                        "Touching, Storytelling, Flashy"
                        ]
                    },
                    {
                        "movie_title_formatted": "babylon-2022",
                        "movie_title": "Babylon",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt10640346/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/615777/",
                        "imdb_id": "tt10640346",
                        "tmdb_id": "615777",
                        "lb_rating": "3.8",
                        "histogram": {
                        "1.0": 3264,
                        "2.0": 7172,
                        "3.0": 5782,
                        "4.0": 21624,
                        "5.0": 24907,
                        "6.0": 69904,
                        "7.0": 88239,
                        "8.0": 165400,
                        "9.0": 99495,
                        "10.0": 109573,
                        "fans": 16000,
                        "lb_rating": "3.8",
                        "total": 595360
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/4/2/7/7/3/542773-babylon-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "Comedy"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["广州话 / 廣州話", "English", "Español"],
                        "popularity": 235.223,
                        "overview": "A tale of outsized ambition and outrageous excess, tracing the rise and fall of multiple characters in an era of unbridled decadence and depravity during Hollywood's transition from silent films to sound films in the late 1920s.",
                        "runtime": 189,
                        "vote_average": 7.411,
                        "vote_count": 2763,
                        "release_date": "2022-12-22",
                        "original_language": "en",
                        "themes": [
                        "Humanity and the world around us",
                        "Moving relationship stories",
                        "Emotional life of renowned artists"
                        ],
                        "nanogenres": [
                        "Emotion, Sexual, Passionate",
                        "Drugs, Depressing, Raw",
                        "Sexual, Weird, Genius",
                        "Hilarious, Sexual, Naked",
                        "Tear-Jerker, Beauty, Happiness",
                        "Emotion, Captivating, Desire",
                        "Chemistry, Gorgeous, Magic",
                        "Hilarious, Nudity, Fame",
                        "Emotion, Discover, Overcome",
                        "Predictable, Sadness, Crying"
                        ]
                    },
                    {
                        "movie_title_formatted": "mr-mme-adelman",
                        "movie_title": "Mr & Mme Adelman",
                        "type": "movie",
                        "year_released": 2017,
                        "imdb_link": "http://www.imdb.com/title/tt6095616/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/431937/",
                        "imdb_id": "tt6095616",
                        "tmdb_id": "431937",
                        "lb_rating": "3.7",
                        "histogram": {
                        "1.0": 27,
                        "2.0": 55,
                        "3.0": 46,
                        "4.0": 190,
                        "5.0": 290,
                        "6.0": 873,
                        "7.0": 1276,
                        "8.0": 2115,
                        "9.0": 696,
                        "10.0": 969,
                        "fans": 162,
                        "lb_rating": "3.7",
                        "total": 6537
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/3/6/5/0/7/0/365070-mr-mme-adelman-0-230-0-345-crop.jpg",
                        "themes": [],
                        "nanogenres": [],
                        "genres": ["Romance", "Drama", "Comedy"],
                        "production_countries": ["Belgium", "France"],
                        "spoken_languages": ["Français"],
                        "popularity": 19.138,
                        "overview": "How did Sarah and Victor get along for more than 45 years? Who was this enigmatic woman living in the shadow of her husband? Love, ambition, betrayals and secrets feed the story of this extraordinary couple, as they experience both the large and small moments of the last century's history.",
                        "runtime": 120,
                        "vote_average": 7.5,
                        "vote_count": 425,
                        "release_date": "2017-03-08",
                        "original_language": "fr"
                    },
                    {
                        "movie_title_formatted": "lord-of-war",
                        "movie_title": "Lord of War",
                        "type": "movie",
                        "year_released": 2005,
                        "imdb_link": "http://www.imdb.com/title/tt0399295/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/1830/",
                        "imdb_id": "tt0399295",
                        "tmdb_id": "1830",
                        "lb_rating": "3.6",
                        "histogram": {
                        "1.0": 277,
                        "2.0": 767,
                        "3.0": 984,
                        "4.0": 4348,
                        "5.0": 6981,
                        "6.0": 24575,
                        "7.0": 31914,
                        "8.0": 33542,
                        "9.0": 7693,
                        "10.0": 6359,
                        "fans": 379,
                        "lb_rating": "3.6",
                        "total": 117440
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/0/7/6/9/50769-lord-of-war-0-230-0-345-crop.jpg",
                        "genres": ["Crime", "Drama", "Thriller"],
                        "production_countries": ["France", "United States of America", "Germany"],
                        "spoken_languages": ["العربية", "Deutsch", "English", "Français", "Pусский", "Español", "Український", "Türkçe"],
                        "popularity": 29.464,
                        "overview": "Yuri Orlov is a globetrotting arms dealer and, through some of the deadliest war zones, he struggles to stay one step ahead of a relentless Interpol agent, his business rivals and even some of his customers who include many of the world's most notorious dictators. Finally, he must also face his own conscience.",
                        "runtime": 122,
                        "vote_average": 7.31,
                        "vote_count": 4544,
                        "release_date": "2005-09-16",
                        "original_language": "en",
                        "themes": [
                        "Politics and human rights",
                        "Crime, drugs and gangsters",
                        "Intense violence and sexual transgression",
                        "Intense political and terrorist thrillers",
                        "Gritty crime and ruthless gangsters",
                        "Riveting political and presidential drama",
                        "Violent crime and drugs",
                        "Racism and the powerful fight for justice"
                        ],
                        "nanogenres": [
                        "Addiction, Moral, Society",
                        "Drama, Morality, Cynical",
                        "Shootings, Firearms, Weapons",
                        "Violence, Guns, Dangerous",
                        "Crime, Government, Moving",
                        "Anti-War, Enemies, Fighter",
                        "Thriller, Guns, Exciting",
                        "Gangster, Class, Crazy",
                        "Gangster, Violence, Drama",
                        "Blood, Exciting, Deadly"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-menu-2022",
                        "movie_title": "The Menu",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt9764362/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/593643/",
                        "imdb_id": "tt9764362",
                        "tmdb_id": "593643",
                        "lb_rating": "3.5",
                        "histogram": {
                        "1.0": 4959,
                        "2.0": 16108,
                        "3.0": 13302,
                        "4.0": 73847,
                        "5.0": 84471,
                        "6.0": 323303,
                        "7.0": 344505,
                        "8.0": 515892,
                        "9.0": 134174,
                        "10.0": 155505,
                        "fans": 4700,
                        "lb_rating": "3.5",
                        "total": 1666066
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/2/1/3/2/3/521323-the-menu-0-230-0-345-crop.jpg",
                        "genres": ["Comedy", "Thriller", "Horror"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English", "Español"],
                        "popularity": 82.161,
                        "overview": "A young couple travels to a remote island to eat at an exclusive restaurant where the chef has prepared a lavish menu, with some shocking surprises.",
                        "runtime": 107,
                        "vote_average": 7.192,
                        "vote_count": 4342,
                        "release_date": "2022-11-17",
                        "original_language": "en",
                        "themes": [
                        "Intense violence and sexual transgression",
                        "Humanity and the world around us",
                        "Twisted dark psychological thriller",
                        "Terrifying, haunted, and supernatural horror"
                        ],
                        "nanogenres": [
                        "Twist, Psychopath, Madness",
                        "Humor, Eating, Mocking",
                        "Killing, Shock, Bizarre",
                        "Weird, Reality, Complicated",
                        "Terrifying, Extreme, Confused",
                        "Thrills, Guessing, Intriguing",
                        "Gory, Disturbing, Guessing",
                        "Guessing, Creepy, Shock",
                        "Eating, Friendship, Ensemble",
                        "Tense, Guessing, Mysterious"
                        ]
                    },
                    {
                        "movie_title_formatted": "glass-onion",
                        "movie_title": "Glass Onion",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt11564570/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/661374/",
                        "imdb_id": "tt11564570",
                        "tmdb_id": "661374",
                        "lb_rating": "3.5",
                        "histogram": {
                        "1.0": 6452,
                        "2.0": 21998,
                        "3.0": 16612,
                        "4.0": 91915,
                        "5.0": 96664,
                        "6.0": 343027,
                        "7.0": 320858,
                        "8.0": 448228,
                        "9.0": 122445,
                        "10.0": 120663,
                        "fans": 1500,
                        "lb_rating": "3.5",
                        "total": 1588862
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/8/6/7/2/3/586723-glass-onion-a-knives-out-mystery-0-230-0-345-crop.jpg",
                        "genres": ["Comedy", "Crime", "Mystery"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 84.356,
                        "overview": "World-famous detective Benoit Blanc heads to Greece to peel back the layers of a mystery surrounding a tech billionaire and his eclectic crew of friends.",
                        "runtime": 140,
                        "vote_average": 7.044,
                        "vote_count": 5093,
                        "release_date": "2022-11-12",
                        "original_language": "en",
                        "themes": [
                        "Thrillers and murder mysteries",
                        "Intriguing and suspenseful murder mysteries",
                        "Suspenseful crime thrillers"
                        ],
                        "nanogenres": [
                        "Murderer, Mysterious, Guessing",
                        "Killer, Crime, Suspects",
                        "Killer, Mysterious, Solving",
                        "Killing, Investigate, Twist",
                        "Humorous, Wit, Formulaic",
                        "Murderer, Clues, Convoluted",
                        "Delightful, Intelligent, Complicated",
                        "Victim, Investigate, Mysterious",
                        "Twist, Intriguing, Intrigue",
                        "Relationships, Mystery, Revelation"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-pale-blue-eye",
                        "movie_title": "The Pale Blue Eye",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt14138650/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/800815/",
                        "imdb_id": "tt14138650",
                        "tmdb_id": "800815",
                        "lb_rating": "3.1",
                        "histogram": {
                        "1.0": 523,
                        "2.0": 1803,
                        "3.0": 2647,
                        "4.0": 12901,
                        "5.0": 21118,
                        "6.0": 46108,
                        "7.0": 30395,
                        "8.0": 19265,
                        "9.0": 3331,
                        "10.0": 4400,
                        "fans": 131,
                        "lb_rating": "3.1",
                        "total": 142491
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/7/1/8/2/4/1/718241-the-pale-blue-eye-0-230-0-345-crop.jpg",
                        "genres": ["Thriller", "Crime", "Horror", "Mystery"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English", "Français", "Latin"],
                        "popularity": 25.209,
                        "overview": "West Point, New York, 1830. When a cadet at the burgeoning military academy is found hanged with his heart cut out, the top brass summons former New York City constable Augustus Landor to investigate. While attempting to solve this grisly mystery, the reluctant detective engages the help of one of the cadets: a strange but brilliant young fellow by the name of Edgar Allan Poe.",
                        "runtime": 128,
                        "vote_average": 6.847,
                        "vote_count": 1678,
                        "release_date": "2022-12-22",
                        "original_language": "en",
                        "themes": [
                        "Thrillers and murder mysteries",
                        "Intriguing and suspenseful murder mysteries",
                        "Suspenseful crime thrillers",
                        "Twisted dark psychological thriller",
                        "Noir and dark crime dramas",
                        "Terrifying, haunted, and supernatural horror"
                        ],
                        "nanogenres": [
                        "Killer, Detectives, Clues",
                        "Crime, Intriguing, Guilty",
                        "Tense, Mysterious, Solving",
                        "Spooky, Killer, Tense",
                        "Crime, Twist, Mysterious",
                        "Emotion, Complexity, Revelation",
                        "Suspense, Detective, Evidence",
                        "Death, Suspense, Dark",
                        "Investigate, Convoluted, Complicated",
                        "Murderer, Mysterious, Guessing"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-northman",
                        "movie_title": "The Northman",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt11138512/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/639933/",
                        "imdb_id": "tt11138512",
                        "tmdb_id": "639933",
                        "lb_rating": "3.8",
                        "histogram": {
                        "1.0": 2310,
                        "2.0": 5719,
                        "3.0": 4516,
                        "4.0": 19343,
                        "5.0": 23446,
                        "6.0": 75877,
                        "7.0": 107753,
                        "8.0": 197241,
                        "9.0": 88632,
                        "10.0": 62085,
                        "fans": 2500,
                        "lb_rating": "3.8",
                        "total": 586922
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/6/5/8/5/2/565852-the-northman-0-230-0-345-crop.jpg",
                        "genres": ["Action", "Adventure", "Fantasy"],
                        "production_countries": ["China", "United States of America"],
                        "spoken_languages": ["English", "Íslenska"],
                        "popularity": 138.858,
                        "overview": "Prince Amleth is on the verge of becoming a man when his father is brutally murdered by his uncle, who kidnaps the boy's mother. Two decades later, Amleth is now a Viking who's on a mission to save his mother, kill his uncle and avenge his father.",
                        "runtime": 137,
                        "vote_average": 7.066,
                        "vote_count": 3986,
                        "release_date": "2022-04-07",
                        "original_language": "en",
                        "themes": [
                        "Epic history and literature",
                        "Epic heroes",
                        "Humanity and the world around us",
                        "Fantasy adventure, heroism, and swordplay",
                        "Captivating vision and Shakespearean drama",
                        "Historical battles and epic heroism",
                        "Epic adventure and breathtaking battles",
                        "Bloody vampire horror"
                        ],
                        "nanogenres": [
                        "Hero, Evil, Complex",
                        "Fighting, Epic, Excitement",
                        "Swords, Mythology, Fantasy",
                        "Villain, Bloody, Battle",
                        "Voices, Battle, Action-Packed",
                        "Bloody, Action-Packed, Avenge",
                        "Death, Forest, Trip",
                        "Feelings, Complex, Captivating",
                        "Combat, Swords, Weapons",
                        "Myth, Imaginative, Quest"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-batman",
                        "movie_title": "The Batman",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt1877830/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/414906/",
                        "imdb_id": "tt1877830",
                        "tmdb_id": "414906",
                        "lb_rating": "4.0",
                        "histogram": {
                        "1.0": 4551,
                        "2.0": 15085,
                        "3.0": 8156,
                        "4.0": 55963,
                        "5.0": 47883,
                        "6.0": 240936,
                        "7.0": 255969,
                        "8.0": 685555,
                        "9.0": 359910,
                        "10.0": 482992,
                        "fans": 42000,
                        "lb_rating": "4.0",
                        "total": 2157000
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/3/4/8/9/1/4/348914-the-batman-0-230-0-345-crop.jpg",
                        "genres": ["Crime", "Mystery", "Thriller"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 184.755,
                        "overview": "In his second year of fighting crime, Batman uncovers corruption in Gotham City that connects to his own family while facing a serial killer known as the Riddler.",
                        "runtime": 177,
                        "vote_average": 7.685,
                        "vote_count": 9462,
                        "release_date": "2022-03-01",
                        "original_language": "en",
                        "themes": [
                        "Crime, drugs and gangsters",
                        "Epic heroes",
                        "High speed and special ops",
                        "Thrillers and murder mysteries",
                        "Superheroes in action-packed battles with villains",
                        "Explosive and action-packed heroes vs. villains",
                        "Violent action, guns, and crime",
                        "Noir and dark crime dramas",
                        "Intriguing and suspenseful murder mysteries"
                        ],
                        "nanogenres": [
                        "Comic-Book, Hero, Exciting",
                        "Fighting, Bullets, Exciting",
                        "Tense, Explosives, Bullets",
                        "Tense, Mysterious, Solving",
                        "Villain, Comic-Book, Campy",
                        "Hero, Evil, Complex",
                        "Villain, Stunts, Vengeance",
                        "Twist, Mysterious, Confusing",
                        "Criminal, Exciting, Climax",
                        "Explosives, Adventure, Predictable"
                        ]
                    }
                ]
    }

@app.get("/recommend/popular", dependencies=[Depends(require_api_key)])
async def get_popular_movies():
    #return await middleware_service.fetch_from_redis("popular_movies")
    return {
        "movies": [
                    {
                        "movie_title_formatted": "sicario-day-of-the-soldado",
                        "movie_title": "Sicario: Day of the Soldado",
                        "type": "movie",
                        "year_released": 2018,
                        "imdb_link": "http://www.imdb.com/title/tt5052474/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/400535/",
                        "imdb_id": "tt5052474",
                        "tmdb_id": "400535",
                        "lb_rating": "3.2",
                        "histogram": {
                        "1.0": 492,
                        "2.0": 1368,
                        "3.0": 1940,
                        "4.0": 7368,
                        "5.0": 11509,
                        "6.0": 29427,
                        "7.0": 26942,
                        "8.0": 17475,
                        "9.0": 2922,
                        "10.0": 2512,
                        "fans": 68,
                        "lb_rating": "3.2",
                        "total": 101955
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/3/3/5/2/9/4/335294-sicario-day-of-the-soldado-0-230-0-345-crop.jpg",
                        "genres": ["Action", "Crime", "Thriller"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English", "Español"],
                        "popularity": 63.776,
                        "overview": "Agent Matt Graver teams up with operative Alejandro Gillick to prevent Mexican drug cartels from smuggling terrorists across the United States border.",
                        "runtime": 122,
                        "vote_average": 6.918,
                        "vote_count": 3393,
                        "release_date": "2018-06-27",
                        "original_language": "en",
                        "themes": [
                        "High speed and special ops",
                        "Politics and human rights",
                        "Crime, drugs and gangsters",
                        "Intense political and terrorist thrillers",
                        "Exciting spy thrillers with tense intrigue",
                        "Violent action, guns, and crime",
                        "Explosive and action-packed heroes vs. villains",
                        "Violent crime and drugs"
                        ],
                        "nanogenres": [
                        "Terrorism, Government, Cia",
                        "Thriller, Unpredictable, Unexpected",
                        "Powerful, Storytelling, Complexity",
                        "Violence, Dark, Unexpected",
                        "Friendship, Realism, Dangerous",
                        "Thriller, Terror, Dark",
                        "Villain, Bullets, Criminal",
                        "Terrorism, Attacks, Bombing",
                        "Villain, Cliche, Action-Packed",
                        "Killing, Shootings, Extreme"
                        ]
                    },
                    {
                        "movie_title_formatted": "mission-impossible-iii",
                        "movie_title": "Mission: Impossible III",
                        "type": "movie",
                        "year_released": 2006,
                        "imdb_link": "http://www.imdb.com/title/tt0317919/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/956/",
                        "imdb_id": "tt0317919",
                        "tmdb_id": "956",
                        "lb_rating": "3.3",
                        "histogram": {
                        "1.0": 530,
                        "2.0": 1894,
                        "3.0": 2340,
                        "4.0": 12349,
                        "5.0": 20584,
                        "6.0": 79300,
                        "7.0": 74869,
                        "8.0": 54423,
                        "9.0": 9461,
                        "10.0": 8497,
                        "fans": 136,
                        "lb_rating": "3.3",
                        "total": 264247
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/1/2/0/4/51204-mission-impossible-iii-0-230-0-345-crop.jpg",
                        "genres": ["Adventure", "Action", "Thriller"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["Deutsch", "English", "Italiano", "普通话", "Český", "广州话 / 廣州話"],
                        "popularity": 49.344,
                        "overview": "Retired from active duty, and training recruits for the Impossible Mission Force, agent Ethan Hunt faces the toughest foe of his career: Owen Davian, an international broker of arms and information, who is as cunning as he is ruthless. Davian emerges to threaten Hunt and all that he holds dear -- including the woman Hunt loves.",
                        "runtime": 126,
                        "vote_average": 6.7,
                        "vote_count": 6497,
                        "release_date": "2006-04-25",
                        "original_language": "en",
                        "themes": [
                        "High speed and special ops",
                        "Epic heroes",
                        "Explosive and action-packed heroes vs. villains",
                        "Adrenaline-fueled action and fast cars",
                        "Exciting spy thrillers with tense intrigue",
                        "Superheroes in action-packed battles with villains",
                        "Intense political and terrorist thrillers"
                        ],
                        "nanogenres": [
                        "Action, Spy, Secret",
                        "Tense, Explosives, Bullets",
                        "Fighting, Shootout, Mindless",
                        "Suspense, Slick, Stylish",
                        "Suspense, Guns, Action-Packed",
                        "Stunts, Bullets, Speed",
                        "Jokes, Guns, Cool",
                        "Thriller, Explosives, Danger",
                        "Thrills, Stunts, Villain",
                        "Fighting, Thrills, Violence"
                        ]
                    },
                    {
                        "movie_title_formatted": "dune-part-two",
                        "movie_title": "Dune: Part Two",
                        "type": "movie",
                        "year_released": 2024,
                        "imdb_link": "http://www.imdb.com/title/tt15239678/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/693134/",
                        "imdb_id": "tt15239678",
                        "tmdb_id": "693134",
                        "lb_rating": "4.5",
                        "histogram": {
                        "1.0": 1415,
                        "2.0": 2279,
                        "3.0": 1593,
                        "4.0": 7662,
                        "5.0": 10964,
                        "6.0": 44282,
                        "7.0": 76174,
                        "8.0": 264286,
                        "9.0": 321268,
                        "10.0": 613673,
                        "fans": 46000,
                        "lb_rating": "4.5",
                        "total": 1343596
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/6/1/7/4/4/3/617443-dune-part-two-0-230-0-345-crop.jpg",
                        "genres": ["Science Fiction", "Adventure"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 1618.076,
                        "overview": "Follow the mythic journey of Paul Atreides as he unites with Chani and the Fremen while on a path of revenge against the conspirators who destroyed his family. Facing a choice between the love of his life and the fate of the known universe, Paul endeavors to prevent a terrible future only he can foresee.",
                        "runtime": 167,
                        "vote_average": 8.3,
                        "vote_count": 3286,
                        "release_date": "2024-02-27",
                        "original_language": "en",
                        "themes": [
                        "Epic heroes",
                        "Humanity and the world around us",
                        "Superheroes in action-packed battles with villains",
                        "Action-packed space and alien sagas",
                        "Thought-provoking sci-fi action and future technology",
                        "Emotional and captivating fantasy storytelling",
                        "Historical battles and epic heroism"
                        ],
                        "nanogenres": [
                        "Space, Technology, Vision",
                        "Action, Epic, Emotion",
                        "Spaceship, Explosives, Destruction",
                        "Planet, Humanity, Future",
                        "Imaginative, Breathtaking, Technology",
                        "Future, Thought-Provoking, Philosophical",
                        "Suspense, Guns, Action-Packed",
                        "Fighting, Evil, Exciting",
                        "Hero, Future, Vision",
                        "Combat, Swords, Weapons"
                        ]
                    },
                    {
                        "movie_title_formatted": "dune-2021",
                        "movie_title": "Dune",
                        "type": "movie",
                        "year_released": 2021,
                        "imdb_link": "http://www.imdb.com/title/tt1160419/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/438631/",
                        "imdb_id": "tt1160419",
                        "tmdb_id": "438631",
                        "lb_rating": "3.9",
                        "histogram": {
                        "1.0": 7586,
                        "2.0": 21709,
                        "3.0": 10826,
                        "4.0": 65934,
                        "5.0": 57377,
                        "6.0": 252563,
                        "7.0": 281523,
                        "8.0": 695835,
                        "9.0": 333093,
                        "10.0": 382719,
                        "fans": 22000,
                        "lb_rating": "3.9",
                        "total": 2109165
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/sm/upload/nx/8b/vs/gc/cDbNAY0KM84cxXhmj8f0dLWza3t-0-230-0-345-crop.jpg",
                        "genres": ["Science Fiction", "Adventure"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["普通话", "English"],
                        "popularity": 535.213,
                        "overview": "Paul Atreides, a brilliant and gifted young man born into a great destiny beyond his understanding, must travel to the most dangerous planet in the universe to ensure the future of his family and his people. As malevolent forces explode into conflict over the planet's exclusive supply of the most precious resource in existence-a commodity capable of unlocking humanity's greatest potential-only those who can conquer their fear will survive.",
                        "runtime": 155,
                        "vote_average": 7.789,
                        "vote_count": 11363,
                        "release_date": "2021-09-15",
                        "original_language": "en",
                        "themes": [
                        "Epic heroes",
                        "Monsters, aliens, sci-fi and the apocalypse",
                        "Action-packed space and alien sagas",
                        "Thought-provoking sci-fi action and future technology",
                        "Superheroes in action-packed battles with villains",
                        "Imaginative space odysseys and alien encounters",
                        "Emotional and captivating fantasy storytelling"
                        ],
                        "nanogenres": [
                        "Space, Technology, Vision",
                        "Action, Epic, Emotion",
                        "Spaceship, Explosives, Destruction",
                        "Fighting, Killing, Evil",
                        "Explosives, Cool, Exciting",
                        "Cool, Monster, Darkness",
                        "Battle, Destruction, Weapons",
                        "Weird, Chilling, Mystery",
                        "Graphics, Anticipation, Creativity",
                        "Predictable, Wins, Gorgeous"
                        ]
                    },
                    {
                        "movie_title_formatted": "past-lives",
                        "movie_title": "Past Lives",
                        "type": "movie",
                        "year_released": 2023,
                        "imdb_link": "http://www.imdb.com/title/tt13238346/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/666277/",
                        "imdb_id": "tt13238346",
                        "tmdb_id": "666277",
                        "lb_rating": "4.2",
                        "histogram": {
                        "1.0": 1219,
                        "2.0": 2546,
                        "3.0": 2120,
                        "4.0": 10840,
                        "5.0": 14942,
                        "6.0": 59817,
                        "7.0": 93778,
                        "8.0": 259379,
                        "9.0": 180620,
                        "10.0": 248161,
                        "fans": 23000,
                        "lb_rating": "4.2",
                        "total": 873422
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/9/1/0/5/3/591053-past-lives-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "Romance"],
                        "production_countries": ["South Korea", "United States of America"],
                        "spoken_languages": ["English", "한국어/조선말"],
                        "popularity": 93.056,
                        "overview": "Nora and Hae Sung, two childhood friends, are reunited in New York for one fateful week as they confront notions of destiny, love, and the choices that make a life.",
                        "runtime": 106,
                        "vote_average": 7.798,
                        "vote_count": 1239,
                        "release_date": "2023-06-02",
                        "original_language": "en",
                        "themes": [
                        "Moving relationship stories",
                        "Touching and sentimental family stories",
                        "Powerful stories of heartbreak and suffering",
                        "Captivating relationships and charming romance",
                        "Tragic sadness and captivating beauty",
                        "Passion and romance"
                        ],
                        "nanogenres": [
                        "Feelings, Moving, Crying",
                        "Drama, Cry, Endearing",
                        "Touching, Chemistry, Marriage",
                        "Romance, Sympathy, Desire",
                        "Relationships, Storytelling, Complexity",
                        "Relationships, Friendship, Sweet",
                        "Touching, Beauty, Desire",
                        "Powerful, Loving, Sentimental",
                        "Cry, Confused, Child",
                        "Charming, Magic, Dream"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-talented-mr-ripley",
                        "movie_title": "The Talented Mr. Ripley",
                        "type": "movie",
                        "year_released": 1999,
                        "imdb_link": "http://www.imdb.com/title/tt0134119/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/1213/",
                        "imdb_id": "tt0134119",
                        "tmdb_id": "1213",
                        "lb_rating": "3.8",
                        "histogram": {
                        "1.0": 414,
                        "2.0": 1215,
                        "3.0": 1222,
                        "4.0": 6486,
                        "5.0": 9562,
                        "6.0": 41864,
                        "7.0": 65258,
                        "8.0": 108969,
                        "9.0": 37067,
                        "10.0": 32404,
                        "fans": 4800,
                        "lb_rating": "3.8",
                        "total": 304461
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/1/1/3/8/51138-the-talented-mr-ripley-0-230-0-345-crop.jpg",
                        "genres": ["Thriller", "Crime", "Drama"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English", "Italiano"],
                        "popularity": 37.922,
                        "overview": "Tom Ripley is a calculating young man who believes it's better to be a fake somebody than a real nobody. Opportunity knocks in the form of a wealthy U.S. shipbuilder who hires Tom to travel to Italy to bring back his playboy son, Dickie. Ripley worms his way into the idyllic lives of Dickie and his girlfriend, plunging into a daring scheme of duplicity, lies and murder.",
                        "runtime": 139,
                        "vote_average": 7.188,
                        "vote_count": 3482,
                        "release_date": "1999-12-25",
                        "original_language": "en",
                        "themes": [
                        "Intense violence and sexual transgression",
                        "Humanity and the world around us",
                        "Thrillers and murder mysteries",
                        "Twisted dark psychological thriller",
                        "Intriguing and suspenseful murder mysteries",
                        "Suspenseful crime thrillers",
                        "Captivating relationships and charming romance",
                        "Noir and dark crime dramas"
                        ],
                        "nanogenres": [
                        "Weird, Disturbing, Intriguing",
                        "Suspense, Unexpected, Engaging",
                        "Murderer, Compelling, Sympathy",
                        "Romance, Sensitive, Lonely",
                        "Thriller, Psychotic, Dark",
                        "Suspense, Criminal, Film-Noir",
                        "Victim, Tense, Detective",
                        "Drama, Gripping, Vulnerable",
                        "Murder, Frighten, Mysterious",
                        "Detective, Twisted, Disturbed"
                        ]
                    },
                    {
                        "movie_title_formatted": "joker-2019",
                        "movie_title": "Joker",
                        "type": "movie",
                        "year_released": 2019,
                        "imdb_link": "http://www.imdb.com/title/tt7286456/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/475557/",
                        "imdb_id": "tt7286456",
                        "tmdb_id": "475557",
                        "lb_rating": "3.8",
                        "histogram": {
                        "1.0": 9828,
                        "2.0": 25508,
                        "3.0": 16395,
                        "4.0": 86737,
                        "5.0": 73912,
                        "6.0": 334163,
                        "7.0": 306361,
                        "8.0": 822871,
                        "9.0": 298212,
                        "10.0": 596197,
                        "fans": 22000,
                        "lb_rating": "3.8",
                        "total": 2570184
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/4/0/6/7/7/5/406775-joker-0-230-0-345-crop.jpg",
                        "genres": ["Crime", "Thriller", "Drama"],
                        "production_countries": ["Canada", "United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 312.884,
                        "overview": "During the 1980s, a failed stand-up comedian is driven insane and turns to a life of crime and chaos in Gotham City while becoming an infamous psychopathic crime figure.",
                        "runtime": 122,
                        "vote_average": 8.161,
                        "vote_count": 24452,
                        "release_date": "2019-10-01",
                        "original_language": "en",
                        "themes": [
                        "Intense violence and sexual transgression",
                        "Moving relationship stories",
                        "Humanity and the world around us",
                        "Crime, drugs and gangsters",
                        "Powerful stories of heartbreak and suffering",
                        "Gripping, intense violent crime",
                        "Challenging or sexual themes & twists",
                        "Emotional and captivating fantasy storytelling",
                        "Graphic violence and brutal revenge"
                        ],
                        "nanogenres": [
                        "Comic-Book, Hero, Exciting",
                        "Gory, Brutal, Extreme",
                        "Terrifying, Disturbed, Troubled",
                        "Chilling, Fear, Extreme",
                        "Shootings, Troubled, Confused",
                        "Emotion, Insanity, Mentally",
                        "Tense, Captivating, Unpredictable",
                        "Bloody, Dark, Intense",
                        "Intense, Storytelling, Compelling",
                        "Emotional, Madness, Sympathy"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-social-network",
                        "movie_title": "The Social Network",
                        "type": "movie",
                        "year_released": 2010,
                        "imdb_link": "http://www.imdb.com/title/tt1285016/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/37799/",
                        "imdb_id": "tt1285016",
                        "tmdb_id": "37799",
                        "lb_rating": "4.0",
                        "histogram": {
                        "1.0": 2701,
                        "2.0": 9573,
                        "3.0": 5307,
                        "4.0": 44698,
                        "5.0": 36360,
                        "6.0": 226230,
                        "7.0": 197799,
                        "8.0": 480848,
                        "9.0": 200002,
                        "10.0": 306040,
                        "fans": 30000,
                        "lb_rating": "4.0",
                        "total": 1509558
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/sm/upload/nw/cm/pa/ai/sGQv3ZMZBDBnl3z42Q0mEQ5uiDe-0-230-0-345-crop.jpg",
                        "genres": ["Drama"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 53.328,
                        "overview": "In 2003, Harvard undergrad and computer genius Mark Zuckerberg begins work on a new concept that eventually turns into the global social network known as Facebook. Six years later, he is one of the youngest billionaires ever, but Zuckerberg finds that his unprecedented success leads to both personal and legal complications when he ends up on the receiving end of two lawsuits, one involving his former friend.",
                        "runtime": 121,
                        "vote_average": 7.364,
                        "vote_count": 11653,
                        "release_date": "2010-10-01",
                        "original_language": "en",
                        "themes": [
                        "Humanity and the world around us",
                        "Teen school antics and laughter",
                        "Student coming-of-age challenges",
                        "Fascinating, emotional stories and documentaries"
                        ],
                        "nanogenres": [
                        "Geeks, Technology, Excitement",
                        "Relationships, Geeks, Obsession",
                        "Emotional, Biography, Facts",
                        "Cliche, College, School",
                        "College, Nerds, Silly",
                        "College, Girlfriend, Lesson",
                        "Drama, Sympathy, Complicated",
                        "Humor, Geeks, Cool",
                        "Friendship, Captivating, Soul",
                        "Cool, Intelligent, Stereotype"
                        ]
                    },
                    {
                        "movie_title_formatted": "oppenheimer-2023",
                        "movie_title": "Oppenheimer",
                        "type": "movie",
                        "year_released": 2023,
                        "imdb_link": "http://www.imdb.com/title/tt15398776/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/872585/",
                        "imdb_id": "tt15398776",
                        "tmdb_id": "872585",
                        "lb_rating": "4.2",
                        "histogram": {
                        "1.0": 4333,
                        "2.0": 9102,
                        "3.0": 5467,
                        "4.0": 31577,
                        "5.0": 32688,
                        "6.0": 146631,
                        "7.0": 181551,
                        "8.0": 542159,
                        "9.0": 446328,
                        "10.0": 678678,
                        "fans": 31000,
                        "lb_rating": "4.2",
                        "total": 2078514
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/7/8/4/3/2/8/784328-oppenheimer-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "History"],
                        "production_countries": ["United Kingdom", "United States of America"],
                        "spoken_languages": ["Nederlands", "English"],
                        "popularity": 477.921,
                        "overview": "The story of J. Robert Oppenheimer's role in the development of the atomic bomb during World War II.",
                        "runtime": 181,
                        "vote_average": 8.108,
                        "vote_count": 7733,
                        "release_date": "2023-07-19",
                        "original_language": "en",
                        "themes": [
                        "Humanity and the world around us",
                        "Politics and human rights",
                        "Epic history and literature",
                        "Intense political and terrorist thrillers",
                        "Riveting political and presidential drama",
                        "Dangerous technology and the apocalypse",
                        "Surreal and thought-provoking visions of life and death",
                        "Political drama, patriotism, and war"
                        ],
                        "nanogenres": [
                        "Intelligent, Thought-Provoking, Philosophical",
                        "Moving, Struggles, Riveting",
                        "Scientific, Thought-Provoking, Philosophy",
                        "Tear-Jerker, Breathtaking, Captivating",
                        "England, Civilian, Gripping",
                        "Touching, Historic, Nation",
                        "Reality, Revelation, Intellectual",
                        "Emotion, Humanity, Complexity",
                        "Thought-Provoking, Moral, Intellectual",
                        "Intense, Revelation, Fascinating"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-prestige",
                        "movie_title": "The Prestige",
                        "type": "movie",
                        "year_released": 2006,
                        "imdb_link": "http://www.imdb.com/title/tt0482571/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/1124/",
                        "imdb_id": "tt0482571",
                        "tmdb_id": "1124",
                        "lb_rating": "4.2",
                        "histogram": {
                        "1.0": 847,
                        "2.0": 2232,
                        "3.0": 1787,
                        "4.0": 10193,
                        "5.0": 12243,
                        "6.0": 63499,
                        "7.0": 95556,
                        "8.0": 275349,
                        "9.0": 187111,
                        "10.0": 227180,
                        "fans": 22000,
                        "lb_rating": "4.2",
                        "total": 875997
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/1/1/4/7/51147-the-prestige-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "Mystery", "Science Fiction"],
                        "production_countries": ["United Kingdom", "United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 80.535,
                        "overview": "A mysterious story of two magicians whose intense rivalry leads them on a life-long battle for supremacy -- full of obsession, deceit and jealousy with dangerous and deadly consequences.",
                        "runtime": 130,
                        "vote_average": 8.2,
                        "vote_count": 15386,
                        "release_date": "2006-10-19",
                        "original_language": "en",
                        "themes": [
                        "Thrillers and murder mysteries",
                        "Twisted dark psychological thriller",
                        "Intriguing and suspenseful murder mysteries",
                        "Intense political and terrorist thrillers"
                        ],
                        "nanogenres": [
                        "Dark, Storytelling, Captivating",
                        "Twist, Intriguing, Confusion",
                        "Twist, Sinister, Secret",
                        "Thriller, Climax, Riveting",
                        "Guessing, Thought-Provoking, Confusion",
                        "Tense, Mysterious, Solving",
                        "Suspense, Confused, Discover",
                        "Chemistry, Storytelling, Lover",
                        "Killing, Twist, Confused",
                        "Dark, Desire, Twisted"
                        ]
                    },
                    {
                        "movie_title_formatted": "mission-impossible-dead-reckoning-part-one",
                        "movie_title": "Mission: Impossible – Dead Reckoning Part One",
                        "type": "movie",
                        "year_released": 2023,
                        "imdb_link": "http://www.imdb.com/title/tt9603212/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/575264/",
                        "imdb_id": "tt9603212",
                        "tmdb_id": "575264",
                        "lb_rating": "3.7",
                        "histogram": {
                        "1.0": 1075,
                        "2.0": 2636,
                        "3.0": 2681,
                        "4.0": 11583,
                        "5.0": 17897,
                        "6.0": 62032,
                        "7.0": 95365,
                        "8.0": 162992,
                        "9.0": 62763,
                        "10.0": 39657,
                        "fans": 636,
                        "lb_rating": "3.7",
                        "total": 458681
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/0/3/4/0/2/503402-mission-impossible-dead-reckoning-part-one-0-230-0-345-crop.jpg",
                        "genres": ["Action", "Thriller"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["Français", "English", "Italiano", "Pусский"],
                        "popularity": 171.482,
                        "overview": "Ethan Hunt and his IMF team embark on their most dangerous mission yet: To track down a terrifying new weapon that threatens all of humanity before it falls into the wrong hands. With control of the future and the world's fate at stake and dark forces from Ethan's past closing in, a deadly race around the globe begins. Confronted by a mysterious, all-powerful enemy, Ethan must consider that nothing can matter more than his mission—not even the lives of those he cares about most.",
                        "runtime": 164,
                        "vote_average": 7.55,
                        "vote_count": 3342,
                        "release_date": "2023-07-08",
                        "original_language": "en",
                        "themes": [
                        "High speed and special ops",
                        "Epic heroes",
                        "Explosive and action-packed heroes vs. villains",
                        "Adrenaline-fueled action and fast cars",
                        "Superheroes in action-packed battles with villains",
                        "Exciting spy thrillers with tense intrigue",
                        "Heists and thrilling action"
                        ],
                        "nanogenres": [
                        "Action, Spy, Secret",
                        "Gadgets, Stunts, Agent",
                        "Fighting, Cool, Menacing",
                        "Thriller, Explosives, Danger",
                        "Jokes, Guns, Cool",
                        "Death, Stunts, Formulaic",
                        "Action, Thrills, Shootings",
                        "Thrills, Stunts, Villain",
                        "Stunts, Cars, Chasing",
                        "Villain, Cool, Chases"
                        ]
                    },
                    {
                        "movie_title_formatted": "avatar-the-way-of-water",
                        "movie_title": "Avatar: The Way of Water",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt1630029/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/76600/",
                        "imdb_id": "tt1630029",
                        "tmdb_id": "76600",
                        "lb_rating": "3.6",
                        "histogram": {
                        "1.0": 8013,
                        "2.0": 18840,
                        "3.0": 13763,
                        "4.0": 59089,
                        "5.0": 63137,
                        "6.0": 201025,
                        "7.0": 206460,
                        "8.0": 339319,
                        "9.0": 127502,
                        "10.0": 186852,
                        "fans": 6300,
                        "lb_rating": "3.6",
                        "total": 1224000
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/6/3/0/5/8/63058-avatar-the-way-of-water-0-230-0-345-crop.jpg",
                        "genres": ["Science Fiction", "Adventure", "Action"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 204.651,
                        "overview": "Set more than a decade after the events of the first film, learn the story of the Sully family (Jake, Neytiri, and their kids), the trouble that follows them, the lengths they go to keep each other safe, the battles they fight to stay alive, and the tragedies they endure.",
                        "runtime": 192,
                        "vote_average": 7.626,
                        "vote_count": 11200,
                        "release_date": "2022-12-14",
                        "original_language": "en",
                        "themes": [
                        "Monsters, aliens, sci-fi and the apocalypse",
                        "Epic heroes",
                        "Thought-provoking sci-fi action and future technology",
                        "Superheroes in action-packed battles with villains",
                        "Epic adventure and breathtaking battles",
                        "Emotional and captivating fantasy storytelling",
                        "Action-packed space and alien sagas"
                        ],
                        "nanogenres": [
                        "Emotional, Child, Wild",
                        "Tear-Jerker, Humans, Environment",
                        "Tear-Jerker, Magic, Captivating",
                        "Excitement, Engaging, Danger",
                        "Cry, Family, Environment",
                        "Touching, Breathtaking, Beauty",
                        "Touching, Tragic, Humanity",
                        "Action, Epic, Emotion",
                        "Action, Creature, Graphics",
                        "Adventure, Graphics, Fantasy"
                        ]
                    },
                    {
                        "movie_title_formatted": "creed-iii",
                        "movie_title": "Creed III",
                        "type": "movie",
                        "year_released": 2023,
                        "imdb_link": "http://www.imdb.com/title/tt11145118/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/677179/",
                        "imdb_id": "tt11145118",
                        "tmdb_id": "677179",
                        "lb_rating": "3.5",
                        "histogram": {
                        "1.0": 484,
                        "2.0": 1474,
                        "3.0": 1945,
                        "4.0": 9026,
                        "5.0": 16345,
                        "6.0": 54712,
                        "7.0": 69333,
                        "8.0": 74733,
                        "9.0": 19099,
                        "10.0": 14133,
                        "fans": 329,
                        "lb_rating": "3.5",
                        "total": 261284
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/6/0/1/6/2/4/601624-creed-iii-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "Action"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["Español", "English"],
                        "popularity": 128.241,
                        "overview": "After dominating the boxing world, Adonis Creed has thrived in his career and family life. When a childhood friend and former boxing prodigy, Damian Anderson, resurfaces after serving a long sentence in prison, he is eager to prove that he deserves his shot in the ring. The face-off between former friends is more than just a fight. To settle the score, Adonis must put his future on the line to battle Damian — a fighter with nothing to lose.",
                        "runtime": 116,
                        "vote_average": 7.125,
                        "vote_count": 2323,
                        "release_date": "2023-03-01",
                        "original_language": "en",
                        "themes": [
                        "Moving relationship stories",
                        "Underdog fighting and boxing stories"
                        ],
                        "nanogenres": [
                        "Boxing, Emotional, Sports",
                        "Fighter, Intense, Fought",
                        "Relationships, Dream, Desire",
                        "Predictable, Wins, Gorgeous",
                        "Compelling, Glory, Beloved",
                        "Fighter, Gritty, Wins",
                        "Cliche, Fighter, Flashy",
                        "Brutal, Battle, Fists",
                        "Feelings, Tragic, Anger",
                        "Touching, Storytelling, Flashy"
                        ]
                    },
                    {
                        "movie_title_formatted": "babylon-2022",
                        "movie_title": "Babylon",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt10640346/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/615777/",
                        "imdb_id": "tt10640346",
                        "tmdb_id": "615777",
                        "lb_rating": "3.8",
                        "histogram": {
                        "1.0": 3264,
                        "2.0": 7172,
                        "3.0": 5782,
                        "4.0": 21624,
                        "5.0": 24907,
                        "6.0": 69904,
                        "7.0": 88239,
                        "8.0": 165400,
                        "9.0": 99495,
                        "10.0": 109573,
                        "fans": 16000,
                        "lb_rating": "3.8",
                        "total": 595360
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/4/2/7/7/3/542773-babylon-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "Comedy"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["广州话 / 廣州話", "English", "Español"],
                        "popularity": 235.223,
                        "overview": "A tale of outsized ambition and outrageous excess, tracing the rise and fall of multiple characters in an era of unbridled decadence and depravity during Hollywood's transition from silent films to sound films in the late 1920s.",
                        "runtime": 189,
                        "vote_average": 7.411,
                        "vote_count": 2763,
                        "release_date": "2022-12-22",
                        "original_language": "en",
                        "themes": [
                        "Humanity and the world around us",
                        "Moving relationship stories",
                        "Emotional life of renowned artists"
                        ],
                        "nanogenres": [
                        "Emotion, Sexual, Passionate",
                        "Drugs, Depressing, Raw",
                        "Sexual, Weird, Genius",
                        "Hilarious, Sexual, Naked",
                        "Tear-Jerker, Beauty, Happiness",
                        "Emotion, Captivating, Desire",
                        "Chemistry, Gorgeous, Magic",
                        "Hilarious, Nudity, Fame",
                        "Emotion, Discover, Overcome",
                        "Predictable, Sadness, Crying"
                        ]
                    },
                    {
                        "movie_title_formatted": "mr-mme-adelman",
                        "movie_title": "Mr & Mme Adelman",
                        "type": "movie",
                        "year_released": 2017,
                        "imdb_link": "http://www.imdb.com/title/tt6095616/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/431937/",
                        "imdb_id": "tt6095616",
                        "tmdb_id": "431937",
                        "lb_rating": "3.7",
                        "histogram": {
                        "1.0": 27,
                        "2.0": 55,
                        "3.0": 46,
                        "4.0": 190,
                        "5.0": 290,
                        "6.0": 873,
                        "7.0": 1276,
                        "8.0": 2115,
                        "9.0": 696,
                        "10.0": 969,
                        "fans": 162,
                        "lb_rating": "3.7",
                        "total": 6537
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/3/6/5/0/7/0/365070-mr-mme-adelman-0-230-0-345-crop.jpg",
                        "themes": [],
                        "nanogenres": [],
                        "genres": ["Romance", "Drama", "Comedy"],
                        "production_countries": ["Belgium", "France"],
                        "spoken_languages": ["Français"],
                        "popularity": 19.138,
                        "overview": "How did Sarah and Victor get along for more than 45 years? Who was this enigmatic woman living in the shadow of her husband? Love, ambition, betrayals and secrets feed the story of this extraordinary couple, as they experience both the large and small moments of the last century's history.",
                        "runtime": 120,
                        "vote_average": 7.5,
                        "vote_count": 425,
                        "release_date": "2017-03-08",
                        "original_language": "fr"
                    },
                    {
                        "movie_title_formatted": "lord-of-war",
                        "movie_title": "Lord of War",
                        "type": "movie",
                        "year_released": 2005,
                        "imdb_link": "http://www.imdb.com/title/tt0399295/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/1830/",
                        "imdb_id": "tt0399295",
                        "tmdb_id": "1830",
                        "lb_rating": "3.6",
                        "histogram": {
                        "1.0": 277,
                        "2.0": 767,
                        "3.0": 984,
                        "4.0": 4348,
                        "5.0": 6981,
                        "6.0": 24575,
                        "7.0": 31914,
                        "8.0": 33542,
                        "9.0": 7693,
                        "10.0": 6359,
                        "fans": 379,
                        "lb_rating": "3.6",
                        "total": 117440
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/0/7/6/9/50769-lord-of-war-0-230-0-345-crop.jpg",
                        "genres": ["Crime", "Drama", "Thriller"],
                        "production_countries": ["France", "United States of America", "Germany"],
                        "spoken_languages": ["العربية", "Deutsch", "English", "Français", "Pусский", "Español", "Український", "Türkçe"],
                        "popularity": 29.464,
                        "overview": "Yuri Orlov is a globetrotting arms dealer and, through some of the deadliest war zones, he struggles to stay one step ahead of a relentless Interpol agent, his business rivals and even some of his customers who include many of the world's most notorious dictators. Finally, he must also face his own conscience.",
                        "runtime": 122,
                        "vote_average": 7.31,
                        "vote_count": 4544,
                        "release_date": "2005-09-16",
                        "original_language": "en",
                        "themes": [
                        "Politics and human rights",
                        "Crime, drugs and gangsters",
                        "Intense violence and sexual transgression",
                        "Intense political and terrorist thrillers",
                        "Gritty crime and ruthless gangsters",
                        "Riveting political and presidential drama",
                        "Violent crime and drugs",
                        "Racism and the powerful fight for justice"
                        ],
                        "nanogenres": [
                        "Addiction, Moral, Society",
                        "Drama, Morality, Cynical",
                        "Shootings, Firearms, Weapons",
                        "Violence, Guns, Dangerous",
                        "Crime, Government, Moving",
                        "Anti-War, Enemies, Fighter",
                        "Thriller, Guns, Exciting",
                        "Gangster, Class, Crazy",
                        "Gangster, Violence, Drama",
                        "Blood, Exciting, Deadly"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-menu-2022",
                        "movie_title": "The Menu",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt9764362/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/593643/",
                        "imdb_id": "tt9764362",
                        "tmdb_id": "593643",
                        "lb_rating": "3.5",
                        "histogram": {
                        "1.0": 4959,
                        "2.0": 16108,
                        "3.0": 13302,
                        "4.0": 73847,
                        "5.0": 84471,
                        "6.0": 323303,
                        "7.0": 344505,
                        "8.0": 515892,
                        "9.0": 134174,
                        "10.0": 155505,
                        "fans": 4700,
                        "lb_rating": "3.5",
                        "total": 1666066
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/2/1/3/2/3/521323-the-menu-0-230-0-345-crop.jpg",
                        "genres": ["Comedy", "Thriller", "Horror"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English", "Español"],
                        "popularity": 82.161,
                        "overview": "A young couple travels to a remote island to eat at an exclusive restaurant where the chef has prepared a lavish menu, with some shocking surprises.",
                        "runtime": 107,
                        "vote_average": 7.192,
                        "vote_count": 4342,
                        "release_date": "2022-11-17",
                        "original_language": "en",
                        "themes": [
                        "Intense violence and sexual transgression",
                        "Humanity and the world around us",
                        "Twisted dark psychological thriller",
                        "Terrifying, haunted, and supernatural horror"
                        ],
                        "nanogenres": [
                        "Twist, Psychopath, Madness",
                        "Humor, Eating, Mocking",
                        "Killing, Shock, Bizarre",
                        "Weird, Reality, Complicated",
                        "Terrifying, Extreme, Confused",
                        "Thrills, Guessing, Intriguing",
                        "Gory, Disturbing, Guessing",
                        "Guessing, Creepy, Shock",
                        "Eating, Friendship, Ensemble",
                        "Tense, Guessing, Mysterious"
                        ]
                    },
                    {
                        "movie_title_formatted": "glass-onion",
                        "movie_title": "Glass Onion",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt11564570/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/661374/",
                        "imdb_id": "tt11564570",
                        "tmdb_id": "661374",
                        "lb_rating": "3.5",
                        "histogram": {
                        "1.0": 6452,
                        "2.0": 21998,
                        "3.0": 16612,
                        "4.0": 91915,
                        "5.0": 96664,
                        "6.0": 343027,
                        "7.0": 320858,
                        "8.0": 448228,
                        "9.0": 122445,
                        "10.0": 120663,
                        "fans": 1500,
                        "lb_rating": "3.5",
                        "total": 1588862
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/8/6/7/2/3/586723-glass-onion-a-knives-out-mystery-0-230-0-345-crop.jpg",
                        "genres": ["Comedy", "Crime", "Mystery"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 84.356,
                        "overview": "World-famous detective Benoit Blanc heads to Greece to peel back the layers of a mystery surrounding a tech billionaire and his eclectic crew of friends.",
                        "runtime": 140,
                        "vote_average": 7.044,
                        "vote_count": 5093,
                        "release_date": "2022-11-12",
                        "original_language": "en",
                        "themes": [
                        "Thrillers and murder mysteries",
                        "Intriguing and suspenseful murder mysteries",
                        "Suspenseful crime thrillers"
                        ],
                        "nanogenres": [
                        "Murderer, Mysterious, Guessing",
                        "Killer, Crime, Suspects",
                        "Killer, Mysterious, Solving",
                        "Killing, Investigate, Twist",
                        "Humorous, Wit, Formulaic",
                        "Murderer, Clues, Convoluted",
                        "Delightful, Intelligent, Complicated",
                        "Victim, Investigate, Mysterious",
                        "Twist, Intriguing, Intrigue",
                        "Relationships, Mystery, Revelation"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-pale-blue-eye",
                        "movie_title": "The Pale Blue Eye",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt14138650/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/800815/",
                        "imdb_id": "tt14138650",
                        "tmdb_id": "800815",
                        "lb_rating": "3.1",
                        "histogram": {
                        "1.0": 523,
                        "2.0": 1803,
                        "3.0": 2647,
                        "4.0": 12901,
                        "5.0": 21118,
                        "6.0": 46108,
                        "7.0": 30395,
                        "8.0": 19265,
                        "9.0": 3331,
                        "10.0": 4400,
                        "fans": 131,
                        "lb_rating": "3.1",
                        "total": 142491
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/7/1/8/2/4/1/718241-the-pale-blue-eye-0-230-0-345-crop.jpg",
                        "genres": ["Thriller", "Crime", "Horror", "Mystery"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English", "Français", "Latin"],
                        "popularity": 25.209,
                        "overview": "West Point, New York, 1830. When a cadet at the burgeoning military academy is found hanged with his heart cut out, the top brass summons former New York City constable Augustus Landor to investigate. While attempting to solve this grisly mystery, the reluctant detective engages the help of one of the cadets: a strange but brilliant young fellow by the name of Edgar Allan Poe.",
                        "runtime": 128,
                        "vote_average": 6.847,
                        "vote_count": 1678,
                        "release_date": "2022-12-22",
                        "original_language": "en",
                        "themes": [
                        "Thrillers and murder mysteries",
                        "Intriguing and suspenseful murder mysteries",
                        "Suspenseful crime thrillers",
                        "Twisted dark psychological thriller",
                        "Noir and dark crime dramas",
                        "Terrifying, haunted, and supernatural horror"
                        ],
                        "nanogenres": [
                        "Killer, Detectives, Clues",
                        "Crime, Intriguing, Guilty",
                        "Tense, Mysterious, Solving",
                        "Spooky, Killer, Tense",
                        "Crime, Twist, Mysterious",
                        "Emotion, Complexity, Revelation",
                        "Suspense, Detective, Evidence",
                        "Death, Suspense, Dark",
                        "Investigate, Convoluted, Complicated",
                        "Murderer, Mysterious, Guessing"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-northman",
                        "movie_title": "The Northman",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt11138512/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/639933/",
                        "imdb_id": "tt11138512",
                        "tmdb_id": "639933",
                        "lb_rating": "3.8",
                        "histogram": {
                        "1.0": 2310,
                        "2.0": 5719,
                        "3.0": 4516,
                        "4.0": 19343,
                        "5.0": 23446,
                        "6.0": 75877,
                        "7.0": 107753,
                        "8.0": 197241,
                        "9.0": 88632,
                        "10.0": 62085,
                        "fans": 2500,
                        "lb_rating": "3.8",
                        "total": 586922
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/6/5/8/5/2/565852-the-northman-0-230-0-345-crop.jpg",
                        "genres": ["Action", "Adventure", "Fantasy"],
                        "production_countries": ["China", "United States of America"],
                        "spoken_languages": ["English", "Íslenska"],
                        "popularity": 138.858,
                        "overview": "Prince Amleth is on the verge of becoming a man when his father is brutally murdered by his uncle, who kidnaps the boy's mother. Two decades later, Amleth is now a Viking who's on a mission to save his mother, kill his uncle and avenge his father.",
                        "runtime": 137,
                        "vote_average": 7.066,
                        "vote_count": 3986,
                        "release_date": "2022-04-07",
                        "original_language": "en",
                        "themes": [
                        "Epic history and literature",
                        "Epic heroes",
                        "Humanity and the world around us",
                        "Fantasy adventure, heroism, and swordplay",
                        "Captivating vision and Shakespearean drama",
                        "Historical battles and epic heroism",
                        "Epic adventure and breathtaking battles",
                        "Bloody vampire horror"
                        ],
                        "nanogenres": [
                        "Hero, Evil, Complex",
                        "Fighting, Epic, Excitement",
                        "Swords, Mythology, Fantasy",
                        "Villain, Bloody, Battle",
                        "Voices, Battle, Action-Packed",
                        "Bloody, Action-Packed, Avenge",
                        "Death, Forest, Trip",
                        "Feelings, Complex, Captivating",
                        "Combat, Swords, Weapons",
                        "Myth, Imaginative, Quest"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-batman",
                        "movie_title": "The Batman",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt1877830/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/414906/",
                        "imdb_id": "tt1877830",
                        "tmdb_id": "414906",
                        "lb_rating": "4.0",
                        "histogram": {
                        "1.0": 4551,
                        "2.0": 15085,
                        "3.0": 8156,
                        "4.0": 55963,
                        "5.0": 47883,
                        "6.0": 240936,
                        "7.0": 255969,
                        "8.0": 685555,
                        "9.0": 359910,
                        "10.0": 482992,
                        "fans": 42000,
                        "lb_rating": "4.0",
                        "total": 2157000
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/3/4/8/9/1/4/348914-the-batman-0-230-0-345-crop.jpg",
                        "genres": ["Crime", "Mystery", "Thriller"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 184.755,
                        "overview": "In his second year of fighting crime, Batman uncovers corruption in Gotham City that connects to his own family while facing a serial killer known as the Riddler.",
                        "runtime": 177,
                        "vote_average": 7.685,
                        "vote_count": 9462,
                        "release_date": "2022-03-01",
                        "original_language": "en",
                        "themes": [
                        "Crime, drugs and gangsters",
                        "Epic heroes",
                        "High speed and special ops",
                        "Thrillers and murder mysteries",
                        "Superheroes in action-packed battles with villains",
                        "Explosive and action-packed heroes vs. villains",
                        "Violent action, guns, and crime",
                        "Noir and dark crime dramas",
                        "Intriguing and suspenseful murder mysteries"
                        ],
                        "nanogenres": [
                        "Comic-Book, Hero, Exciting",
                        "Fighting, Bullets, Exciting",
                        "Tense, Explosives, Bullets",
                        "Tense, Mysterious, Solving",
                        "Villain, Comic-Book, Campy",
                        "Hero, Evil, Complex",
                        "Villain, Stunts, Vengeance",
                        "Twist, Mysterious, Confusing",
                        "Criminal, Exciting, Climax",
                        "Explosives, Adventure, Predictable"
                        ]
                    }
                ]
    }

@app.get("/recommend/random", dependencies=[Depends(require_api_key)])
async def get_random_movies_endpoint():
    """
    Retrieves 24 random movies directly from MongoDB.
    """
    return {
        "movies": [
                    {
                        "movie_title_formatted": "sicario-day-of-the-soldado",
                        "movie_title": "Sicario: Day of the Soldado",
                        "type": "movie",
                        "year_released": 2018,
                        "imdb_link": "http://www.imdb.com/title/tt5052474/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/400535/",
                        "imdb_id": "tt5052474",
                        "tmdb_id": "400535",
                        "lb_rating": "3.2",
                        "histogram": {
                        "1.0": 492,
                        "2.0": 1368,
                        "3.0": 1940,
                        "4.0": 7368,
                        "5.0": 11509,
                        "6.0": 29427,
                        "7.0": 26942,
                        "8.0": 17475,
                        "9.0": 2922,
                        "10.0": 2512,
                        "fans": 68,
                        "lb_rating": "3.2",
                        "total": 101955
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/3/3/5/2/9/4/335294-sicario-day-of-the-soldado-0-230-0-345-crop.jpg",
                        "genres": ["Action", "Crime", "Thriller"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English", "Español"],
                        "popularity": 63.776,
                        "overview": "Agent Matt Graver teams up with operative Alejandro Gillick to prevent Mexican drug cartels from smuggling terrorists across the United States border.",
                        "runtime": 122,
                        "vote_average": 6.918,
                        "vote_count": 3393,
                        "release_date": "2018-06-27",
                        "original_language": "en",
                        "themes": [
                        "High speed and special ops",
                        "Politics and human rights",
                        "Crime, drugs and gangsters",
                        "Intense political and terrorist thrillers",
                        "Exciting spy thrillers with tense intrigue",
                        "Violent action, guns, and crime",
                        "Explosive and action-packed heroes vs. villains",
                        "Violent crime and drugs"
                        ],
                        "nanogenres": [
                        "Terrorism, Government, Cia",
                        "Thriller, Unpredictable, Unexpected",
                        "Powerful, Storytelling, Complexity",
                        "Violence, Dark, Unexpected",
                        "Friendship, Realism, Dangerous",
                        "Thriller, Terror, Dark",
                        "Villain, Bullets, Criminal",
                        "Terrorism, Attacks, Bombing",
                        "Villain, Cliche, Action-Packed",
                        "Killing, Shootings, Extreme"
                        ]
                    },
                    {
                        "movie_title_formatted": "mission-impossible-iii",
                        "movie_title": "Mission: Impossible III",
                        "type": "movie",
                        "year_released": 2006,
                        "imdb_link": "http://www.imdb.com/title/tt0317919/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/956/",
                        "imdb_id": "tt0317919",
                        "tmdb_id": "956",
                        "lb_rating": "3.3",
                        "histogram": {
                        "1.0": 530,
                        "2.0": 1894,
                        "3.0": 2340,
                        "4.0": 12349,
                        "5.0": 20584,
                        "6.0": 79300,
                        "7.0": 74869,
                        "8.0": 54423,
                        "9.0": 9461,
                        "10.0": 8497,
                        "fans": 136,
                        "lb_rating": "3.3",
                        "total": 264247
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/1/2/0/4/51204-mission-impossible-iii-0-230-0-345-crop.jpg",
                        "genres": ["Adventure", "Action", "Thriller"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["Deutsch", "English", "Italiano", "普通话", "Český", "广州话 / 廣州話"],
                        "popularity": 49.344,
                        "overview": "Retired from active duty, and training recruits for the Impossible Mission Force, agent Ethan Hunt faces the toughest foe of his career: Owen Davian, an international broker of arms and information, who is as cunning as he is ruthless. Davian emerges to threaten Hunt and all that he holds dear -- including the woman Hunt loves.",
                        "runtime": 126,
                        "vote_average": 6.7,
                        "vote_count": 6497,
                        "release_date": "2006-04-25",
                        "original_language": "en",
                        "themes": [
                        "High speed and special ops",
                        "Epic heroes",
                        "Explosive and action-packed heroes vs. villains",
                        "Adrenaline-fueled action and fast cars",
                        "Exciting spy thrillers with tense intrigue",
                        "Superheroes in action-packed battles with villains",
                        "Intense political and terrorist thrillers"
                        ],
                        "nanogenres": [
                        "Action, Spy, Secret",
                        "Tense, Explosives, Bullets",
                        "Fighting, Shootout, Mindless",
                        "Suspense, Slick, Stylish",
                        "Suspense, Guns, Action-Packed",
                        "Stunts, Bullets, Speed",
                        "Jokes, Guns, Cool",
                        "Thriller, Explosives, Danger",
                        "Thrills, Stunts, Villain",
                        "Fighting, Thrills, Violence"
                        ]
                    },
                    {
                        "movie_title_formatted": "dune-part-two",
                        "movie_title": "Dune: Part Two",
                        "type": "movie",
                        "year_released": 2024,
                        "imdb_link": "http://www.imdb.com/title/tt15239678/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/693134/",
                        "imdb_id": "tt15239678",
                        "tmdb_id": "693134",
                        "lb_rating": "4.5",
                        "histogram": {
                        "1.0": 1415,
                        "2.0": 2279,
                        "3.0": 1593,
                        "4.0": 7662,
                        "5.0": 10964,
                        "6.0": 44282,
                        "7.0": 76174,
                        "8.0": 264286,
                        "9.0": 321268,
                        "10.0": 613673,
                        "fans": 46000,
                        "lb_rating": "4.5",
                        "total": 1343596
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/6/1/7/4/4/3/617443-dune-part-two-0-230-0-345-crop.jpg",
                        "genres": ["Science Fiction", "Adventure"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 1618.076,
                        "overview": "Follow the mythic journey of Paul Atreides as he unites with Chani and the Fremen while on a path of revenge against the conspirators who destroyed his family. Facing a choice between the love of his life and the fate of the known universe, Paul endeavors to prevent a terrible future only he can foresee.",
                        "runtime": 167,
                        "vote_average": 8.3,
                        "vote_count": 3286,
                        "release_date": "2024-02-27",
                        "original_language": "en",
                        "themes": [
                        "Epic heroes",
                        "Humanity and the world around us",
                        "Superheroes in action-packed battles with villains",
                        "Action-packed space and alien sagas",
                        "Thought-provoking sci-fi action and future technology",
                        "Emotional and captivating fantasy storytelling",
                        "Historical battles and epic heroism"
                        ],
                        "nanogenres": [
                        "Space, Technology, Vision",
                        "Action, Epic, Emotion",
                        "Spaceship, Explosives, Destruction",
                        "Planet, Humanity, Future",
                        "Imaginative, Breathtaking, Technology",
                        "Future, Thought-Provoking, Philosophical",
                        "Suspense, Guns, Action-Packed",
                        "Fighting, Evil, Exciting",
                        "Hero, Future, Vision",
                        "Combat, Swords, Weapons"
                        ]
                    },
                    {
                        "movie_title_formatted": "dune-2021",
                        "movie_title": "Dune",
                        "type": "movie",
                        "year_released": 2021,
                        "imdb_link": "http://www.imdb.com/title/tt1160419/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/438631/",
                        "imdb_id": "tt1160419",
                        "tmdb_id": "438631",
                        "lb_rating": "3.9",
                        "histogram": {
                        "1.0": 7586,
                        "2.0": 21709,
                        "3.0": 10826,
                        "4.0": 65934,
                        "5.0": 57377,
                        "6.0": 252563,
                        "7.0": 281523,
                        "8.0": 695835,
                        "9.0": 333093,
                        "10.0": 382719,
                        "fans": 22000,
                        "lb_rating": "3.9",
                        "total": 2109165
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/sm/upload/nx/8b/vs/gc/cDbNAY0KM84cxXhmj8f0dLWza3t-0-230-0-345-crop.jpg",
                        "genres": ["Science Fiction", "Adventure"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["普通话", "English"],
                        "popularity": 535.213,
                        "overview": "Paul Atreides, a brilliant and gifted young man born into a great destiny beyond his understanding, must travel to the most dangerous planet in the universe to ensure the future of his family and his people. As malevolent forces explode into conflict over the planet's exclusive supply of the most precious resource in existence-a commodity capable of unlocking humanity's greatest potential-only those who can conquer their fear will survive.",
                        "runtime": 155,
                        "vote_average": 7.789,
                        "vote_count": 11363,
                        "release_date": "2021-09-15",
                        "original_language": "en",
                        "themes": [
                        "Epic heroes",
                        "Monsters, aliens, sci-fi and the apocalypse",
                        "Action-packed space and alien sagas",
                        "Thought-provoking sci-fi action and future technology",
                        "Superheroes in action-packed battles with villains",
                        "Imaginative space odysseys and alien encounters",
                        "Emotional and captivating fantasy storytelling"
                        ],
                        "nanogenres": [
                        "Space, Technology, Vision",
                        "Action, Epic, Emotion",
                        "Spaceship, Explosives, Destruction",
                        "Fighting, Killing, Evil",
                        "Explosives, Cool, Exciting",
                        "Cool, Monster, Darkness",
                        "Battle, Destruction, Weapons",
                        "Weird, Chilling, Mystery",
                        "Graphics, Anticipation, Creativity",
                        "Predictable, Wins, Gorgeous"
                        ]
                    },
                    {
                        "movie_title_formatted": "past-lives",
                        "movie_title": "Past Lives",
                        "type": "movie",
                        "year_released": 2023,
                        "imdb_link": "http://www.imdb.com/title/tt13238346/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/666277/",
                        "imdb_id": "tt13238346",
                        "tmdb_id": "666277",
                        "lb_rating": "4.2",
                        "histogram": {
                        "1.0": 1219,
                        "2.0": 2546,
                        "3.0": 2120,
                        "4.0": 10840,
                        "5.0": 14942,
                        "6.0": 59817,
                        "7.0": 93778,
                        "8.0": 259379,
                        "9.0": 180620,
                        "10.0": 248161,
                        "fans": 23000,
                        "lb_rating": "4.2",
                        "total": 873422
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/9/1/0/5/3/591053-past-lives-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "Romance"],
                        "production_countries": ["South Korea", "United States of America"],
                        "spoken_languages": ["English", "한국어/조선말"],
                        "popularity": 93.056,
                        "overview": "Nora and Hae Sung, two childhood friends, are reunited in New York for one fateful week as they confront notions of destiny, love, and the choices that make a life.",
                        "runtime": 106,
                        "vote_average": 7.798,
                        "vote_count": 1239,
                        "release_date": "2023-06-02",
                        "original_language": "en",
                        "themes": [
                        "Moving relationship stories",
                        "Touching and sentimental family stories",
                        "Powerful stories of heartbreak and suffering",
                        "Captivating relationships and charming romance",
                        "Tragic sadness and captivating beauty",
                        "Passion and romance"
                        ],
                        "nanogenres": [
                        "Feelings, Moving, Crying",
                        "Drama, Cry, Endearing",
                        "Touching, Chemistry, Marriage",
                        "Romance, Sympathy, Desire",
                        "Relationships, Storytelling, Complexity",
                        "Relationships, Friendship, Sweet",
                        "Touching, Beauty, Desire",
                        "Powerful, Loving, Sentimental",
                        "Cry, Confused, Child",
                        "Charming, Magic, Dream"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-talented-mr-ripley",
                        "movie_title": "The Talented Mr. Ripley",
                        "type": "movie",
                        "year_released": 1999,
                        "imdb_link": "http://www.imdb.com/title/tt0134119/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/1213/",
                        "imdb_id": "tt0134119",
                        "tmdb_id": "1213",
                        "lb_rating": "3.8",
                        "histogram": {
                        "1.0": 414,
                        "2.0": 1215,
                        "3.0": 1222,
                        "4.0": 6486,
                        "5.0": 9562,
                        "6.0": 41864,
                        "7.0": 65258,
                        "8.0": 108969,
                        "9.0": 37067,
                        "10.0": 32404,
                        "fans": 4800,
                        "lb_rating": "3.8",
                        "total": 304461
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/1/1/3/8/51138-the-talented-mr-ripley-0-230-0-345-crop.jpg",
                        "genres": ["Thriller", "Crime", "Drama"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English", "Italiano"],
                        "popularity": 37.922,
                        "overview": "Tom Ripley is a calculating young man who believes it's better to be a fake somebody than a real nobody. Opportunity knocks in the form of a wealthy U.S. shipbuilder who hires Tom to travel to Italy to bring back his playboy son, Dickie. Ripley worms his way into the idyllic lives of Dickie and his girlfriend, plunging into a daring scheme of duplicity, lies and murder.",
                        "runtime": 139,
                        "vote_average": 7.188,
                        "vote_count": 3482,
                        "release_date": "1999-12-25",
                        "original_language": "en",
                        "themes": [
                        "Intense violence and sexual transgression",
                        "Humanity and the world around us",
                        "Thrillers and murder mysteries",
                        "Twisted dark psychological thriller",
                        "Intriguing and suspenseful murder mysteries",
                        "Suspenseful crime thrillers",
                        "Captivating relationships and charming romance",
                        "Noir and dark crime dramas"
                        ],
                        "nanogenres": [
                        "Weird, Disturbing, Intriguing",
                        "Suspense, Unexpected, Engaging",
                        "Murderer, Compelling, Sympathy",
                        "Romance, Sensitive, Lonely",
                        "Thriller, Psychotic, Dark",
                        "Suspense, Criminal, Film-Noir",
                        "Victim, Tense, Detective",
                        "Drama, Gripping, Vulnerable",
                        "Murder, Frighten, Mysterious",
                        "Detective, Twisted, Disturbed"
                        ]
                    },
                    {
                        "movie_title_formatted": "joker-2019",
                        "movie_title": "Joker",
                        "type": "movie",
                        "year_released": 2019,
                        "imdb_link": "http://www.imdb.com/title/tt7286456/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/475557/",
                        "imdb_id": "tt7286456",
                        "tmdb_id": "475557",
                        "lb_rating": "3.8",
                        "histogram": {
                        "1.0": 9828,
                        "2.0": 25508,
                        "3.0": 16395,
                        "4.0": 86737,
                        "5.0": 73912,
                        "6.0": 334163,
                        "7.0": 306361,
                        "8.0": 822871,
                        "9.0": 298212,
                        "10.0": 596197,
                        "fans": 22000,
                        "lb_rating": "3.8",
                        "total": 2570184
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/4/0/6/7/7/5/406775-joker-0-230-0-345-crop.jpg",
                        "genres": ["Crime", "Thriller", "Drama"],
                        "production_countries": ["Canada", "United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 312.884,
                        "overview": "During the 1980s, a failed stand-up comedian is driven insane and turns to a life of crime and chaos in Gotham City while becoming an infamous psychopathic crime figure.",
                        "runtime": 122,
                        "vote_average": 8.161,
                        "vote_count": 24452,
                        "release_date": "2019-10-01",
                        "original_language": "en",
                        "themes": [
                        "Intense violence and sexual transgression",
                        "Moving relationship stories",
                        "Humanity and the world around us",
                        "Crime, drugs and gangsters",
                        "Powerful stories of heartbreak and suffering",
                        "Gripping, intense violent crime",
                        "Challenging or sexual themes & twists",
                        "Emotional and captivating fantasy storytelling",
                        "Graphic violence and brutal revenge"
                        ],
                        "nanogenres": [
                        "Comic-Book, Hero, Exciting",
                        "Gory, Brutal, Extreme",
                        "Terrifying, Disturbed, Troubled",
                        "Chilling, Fear, Extreme",
                        "Shootings, Troubled, Confused",
                        "Emotion, Insanity, Mentally",
                        "Tense, Captivating, Unpredictable",
                        "Bloody, Dark, Intense",
                        "Intense, Storytelling, Compelling",
                        "Emotional, Madness, Sympathy"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-social-network",
                        "movie_title": "The Social Network",
                        "type": "movie",
                        "year_released": 2010,
                        "imdb_link": "http://www.imdb.com/title/tt1285016/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/37799/",
                        "imdb_id": "tt1285016",
                        "tmdb_id": "37799",
                        "lb_rating": "4.0",
                        "histogram": {
                        "1.0": 2701,
                        "2.0": 9573,
                        "3.0": 5307,
                        "4.0": 44698,
                        "5.0": 36360,
                        "6.0": 226230,
                        "7.0": 197799,
                        "8.0": 480848,
                        "9.0": 200002,
                        "10.0": 306040,
                        "fans": 30000,
                        "lb_rating": "4.0",
                        "total": 1509558
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/sm/upload/nw/cm/pa/ai/sGQv3ZMZBDBnl3z42Q0mEQ5uiDe-0-230-0-345-crop.jpg",
                        "genres": ["Drama"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 53.328,
                        "overview": "In 2003, Harvard undergrad and computer genius Mark Zuckerberg begins work on a new concept that eventually turns into the global social network known as Facebook. Six years later, he is one of the youngest billionaires ever, but Zuckerberg finds that his unprecedented success leads to both personal and legal complications when he ends up on the receiving end of two lawsuits, one involving his former friend.",
                        "runtime": 121,
                        "vote_average": 7.364,
                        "vote_count": 11653,
                        "release_date": "2010-10-01",
                        "original_language": "en",
                        "themes": [
                        "Humanity and the world around us",
                        "Teen school antics and laughter",
                        "Student coming-of-age challenges",
                        "Fascinating, emotional stories and documentaries"
                        ],
                        "nanogenres": [
                        "Geeks, Technology, Excitement",
                        "Relationships, Geeks, Obsession",
                        "Emotional, Biography, Facts",
                        "Cliche, College, School",
                        "College, Nerds, Silly",
                        "College, Girlfriend, Lesson",
                        "Drama, Sympathy, Complicated",
                        "Humor, Geeks, Cool",
                        "Friendship, Captivating, Soul",
                        "Cool, Intelligent, Stereotype"
                        ]
                    },
                    {
                        "movie_title_formatted": "oppenheimer-2023",
                        "movie_title": "Oppenheimer",
                        "type": "movie",
                        "year_released": 2023,
                        "imdb_link": "http://www.imdb.com/title/tt15398776/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/872585/",
                        "imdb_id": "tt15398776",
                        "tmdb_id": "872585",
                        "lb_rating": "4.2",
                        "histogram": {
                        "1.0": 4333,
                        "2.0": 9102,
                        "3.0": 5467,
                        "4.0": 31577,
                        "5.0": 32688,
                        "6.0": 146631,
                        "7.0": 181551,
                        "8.0": 542159,
                        "9.0": 446328,
                        "10.0": 678678,
                        "fans": 31000,
                        "lb_rating": "4.2",
                        "total": 2078514
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/7/8/4/3/2/8/784328-oppenheimer-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "History"],
                        "production_countries": ["United Kingdom", "United States of America"],
                        "spoken_languages": ["Nederlands", "English"],
                        "popularity": 477.921,
                        "overview": "The story of J. Robert Oppenheimer's role in the development of the atomic bomb during World War II.",
                        "runtime": 181,
                        "vote_average": 8.108,
                        "vote_count": 7733,
                        "release_date": "2023-07-19",
                        "original_language": "en",
                        "themes": [
                        "Humanity and the world around us",
                        "Politics and human rights",
                        "Epic history and literature",
                        "Intense political and terrorist thrillers",
                        "Riveting political and presidential drama",
                        "Dangerous technology and the apocalypse",
                        "Surreal and thought-provoking visions of life and death",
                        "Political drama, patriotism, and war"
                        ],
                        "nanogenres": [
                        "Intelligent, Thought-Provoking, Philosophical",
                        "Moving, Struggles, Riveting",
                        "Scientific, Thought-Provoking, Philosophy",
                        "Tear-Jerker, Breathtaking, Captivating",
                        "England, Civilian, Gripping",
                        "Touching, Historic, Nation",
                        "Reality, Revelation, Intellectual",
                        "Emotion, Humanity, Complexity",
                        "Thought-Provoking, Moral, Intellectual",
                        "Intense, Revelation, Fascinating"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-prestige",
                        "movie_title": "The Prestige",
                        "type": "movie",
                        "year_released": 2006,
                        "imdb_link": "http://www.imdb.com/title/tt0482571/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/1124/",
                        "imdb_id": "tt0482571",
                        "tmdb_id": "1124",
                        "lb_rating": "4.2",
                        "histogram": {
                        "1.0": 847,
                        "2.0": 2232,
                        "3.0": 1787,
                        "4.0": 10193,
                        "5.0": 12243,
                        "6.0": 63499,
                        "7.0": 95556,
                        "8.0": 275349,
                        "9.0": 187111,
                        "10.0": 227180,
                        "fans": 22000,
                        "lb_rating": "4.2",
                        "total": 875997
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/1/1/4/7/51147-the-prestige-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "Mystery", "Science Fiction"],
                        "production_countries": ["United Kingdom", "United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 80.535,
                        "overview": "A mysterious story of two magicians whose intense rivalry leads them on a life-long battle for supremacy -- full of obsession, deceit and jealousy with dangerous and deadly consequences.",
                        "runtime": 130,
                        "vote_average": 8.2,
                        "vote_count": 15386,
                        "release_date": "2006-10-19",
                        "original_language": "en",
                        "themes": [
                        "Thrillers and murder mysteries",
                        "Twisted dark psychological thriller",
                        "Intriguing and suspenseful murder mysteries",
                        "Intense political and terrorist thrillers"
                        ],
                        "nanogenres": [
                        "Dark, Storytelling, Captivating",
                        "Twist, Intriguing, Confusion",
                        "Twist, Sinister, Secret",
                        "Thriller, Climax, Riveting",
                        "Guessing, Thought-Provoking, Confusion",
                        "Tense, Mysterious, Solving",
                        "Suspense, Confused, Discover",
                        "Chemistry, Storytelling, Lover",
                        "Killing, Twist, Confused",
                        "Dark, Desire, Twisted"
                        ]
                    },
                    {
                        "movie_title_formatted": "mission-impossible-dead-reckoning-part-one",
                        "movie_title": "Mission: Impossible – Dead Reckoning Part One",
                        "type": "movie",
                        "year_released": 2023,
                        "imdb_link": "http://www.imdb.com/title/tt9603212/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/575264/",
                        "imdb_id": "tt9603212",
                        "tmdb_id": "575264",
                        "lb_rating": "3.7",
                        "histogram": {
                        "1.0": 1075,
                        "2.0": 2636,
                        "3.0": 2681,
                        "4.0": 11583,
                        "5.0": 17897,
                        "6.0": 62032,
                        "7.0": 95365,
                        "8.0": 162992,
                        "9.0": 62763,
                        "10.0": 39657,
                        "fans": 636,
                        "lb_rating": "3.7",
                        "total": 458681
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/0/3/4/0/2/503402-mission-impossible-dead-reckoning-part-one-0-230-0-345-crop.jpg",
                        "genres": ["Action", "Thriller"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["Français", "English", "Italiano", "Pусский"],
                        "popularity": 171.482,
                        "overview": "Ethan Hunt and his IMF team embark on their most dangerous mission yet: To track down a terrifying new weapon that threatens all of humanity before it falls into the wrong hands. With control of the future and the world's fate at stake and dark forces from Ethan's past closing in, a deadly race around the globe begins. Confronted by a mysterious, all-powerful enemy, Ethan must consider that nothing can matter more than his mission—not even the lives of those he cares about most.",
                        "runtime": 164,
                        "vote_average": 7.55,
                        "vote_count": 3342,
                        "release_date": "2023-07-08",
                        "original_language": "en",
                        "themes": [
                        "High speed and special ops",
                        "Epic heroes",
                        "Explosive and action-packed heroes vs. villains",
                        "Adrenaline-fueled action and fast cars",
                        "Superheroes in action-packed battles with villains",
                        "Exciting spy thrillers with tense intrigue",
                        "Heists and thrilling action"
                        ],
                        "nanogenres": [
                        "Action, Spy, Secret",
                        "Gadgets, Stunts, Agent",
                        "Fighting, Cool, Menacing",
                        "Thriller, Explosives, Danger",
                        "Jokes, Guns, Cool",
                        "Death, Stunts, Formulaic",
                        "Action, Thrills, Shootings",
                        "Thrills, Stunts, Villain",
                        "Stunts, Cars, Chasing",
                        "Villain, Cool, Chases"
                        ]
                    },
                    {
                        "movie_title_formatted": "avatar-the-way-of-water",
                        "movie_title": "Avatar: The Way of Water",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt1630029/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/76600/",
                        "imdb_id": "tt1630029",
                        "tmdb_id": "76600",
                        "lb_rating": "3.6",
                        "histogram": {
                        "1.0": 8013,
                        "2.0": 18840,
                        "3.0": 13763,
                        "4.0": 59089,
                        "5.0": 63137,
                        "6.0": 201025,
                        "7.0": 206460,
                        "8.0": 339319,
                        "9.0": 127502,
                        "10.0": 186852,
                        "fans": 6300,
                        "lb_rating": "3.6",
                        "total": 1224000
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/6/3/0/5/8/63058-avatar-the-way-of-water-0-230-0-345-crop.jpg",
                        "genres": ["Science Fiction", "Adventure", "Action"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 204.651,
                        "overview": "Set more than a decade after the events of the first film, learn the story of the Sully family (Jake, Neytiri, and their kids), the trouble that follows them, the lengths they go to keep each other safe, the battles they fight to stay alive, and the tragedies they endure.",
                        "runtime": 192,
                        "vote_average": 7.626,
                        "vote_count": 11200,
                        "release_date": "2022-12-14",
                        "original_language": "en",
                        "themes": [
                        "Monsters, aliens, sci-fi and the apocalypse",
                        "Epic heroes",
                        "Thought-provoking sci-fi action and future technology",
                        "Superheroes in action-packed battles with villains",
                        "Epic adventure and breathtaking battles",
                        "Emotional and captivating fantasy storytelling",
                        "Action-packed space and alien sagas"
                        ],
                        "nanogenres": [
                        "Emotional, Child, Wild",
                        "Tear-Jerker, Humans, Environment",
                        "Tear-Jerker, Magic, Captivating",
                        "Excitement, Engaging, Danger",
                        "Cry, Family, Environment",
                        "Touching, Breathtaking, Beauty",
                        "Touching, Tragic, Humanity",
                        "Action, Epic, Emotion",
                        "Action, Creature, Graphics",
                        "Adventure, Graphics, Fantasy"
                        ]
                    },
                    {
                        "movie_title_formatted": "creed-iii",
                        "movie_title": "Creed III",
                        "type": "movie",
                        "year_released": 2023,
                        "imdb_link": "http://www.imdb.com/title/tt11145118/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/677179/",
                        "imdb_id": "tt11145118",
                        "tmdb_id": "677179",
                        "lb_rating": "3.5",
                        "histogram": {
                        "1.0": 484,
                        "2.0": 1474,
                        "3.0": 1945,
                        "4.0": 9026,
                        "5.0": 16345,
                        "6.0": 54712,
                        "7.0": 69333,
                        "8.0": 74733,
                        "9.0": 19099,
                        "10.0": 14133,
                        "fans": 329,
                        "lb_rating": "3.5",
                        "total": 261284
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/6/0/1/6/2/4/601624-creed-iii-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "Action"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["Español", "English"],
                        "popularity": 128.241,
                        "overview": "After dominating the boxing world, Adonis Creed has thrived in his career and family life. When a childhood friend and former boxing prodigy, Damian Anderson, resurfaces after serving a long sentence in prison, he is eager to prove that he deserves his shot in the ring. The face-off between former friends is more than just a fight. To settle the score, Adonis must put his future on the line to battle Damian — a fighter with nothing to lose.",
                        "runtime": 116,
                        "vote_average": 7.125,
                        "vote_count": 2323,
                        "release_date": "2023-03-01",
                        "original_language": "en",
                        "themes": [
                        "Moving relationship stories",
                        "Underdog fighting and boxing stories"
                        ],
                        "nanogenres": [
                        "Boxing, Emotional, Sports",
                        "Fighter, Intense, Fought",
                        "Relationships, Dream, Desire",
                        "Predictable, Wins, Gorgeous",
                        "Compelling, Glory, Beloved",
                        "Fighter, Gritty, Wins",
                        "Cliche, Fighter, Flashy",
                        "Brutal, Battle, Fists",
                        "Feelings, Tragic, Anger",
                        "Touching, Storytelling, Flashy"
                        ]
                    },
                    {
                        "movie_title_formatted": "babylon-2022",
                        "movie_title": "Babylon",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt10640346/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/615777/",
                        "imdb_id": "tt10640346",
                        "tmdb_id": "615777",
                        "lb_rating": "3.8",
                        "histogram": {
                        "1.0": 3264,
                        "2.0": 7172,
                        "3.0": 5782,
                        "4.0": 21624,
                        "5.0": 24907,
                        "6.0": 69904,
                        "7.0": 88239,
                        "8.0": 165400,
                        "9.0": 99495,
                        "10.0": 109573,
                        "fans": 16000,
                        "lb_rating": "3.8",
                        "total": 595360
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/4/2/7/7/3/542773-babylon-0-230-0-345-crop.jpg",
                        "genres": ["Drama", "Comedy"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["广州话 / 廣州話", "English", "Español"],
                        "popularity": 235.223,
                        "overview": "A tale of outsized ambition and outrageous excess, tracing the rise and fall of multiple characters in an era of unbridled decadence and depravity during Hollywood's transition from silent films to sound films in the late 1920s.",
                        "runtime": 189,
                        "vote_average": 7.411,
                        "vote_count": 2763,
                        "release_date": "2022-12-22",
                        "original_language": "en",
                        "themes": [
                        "Humanity and the world around us",
                        "Moving relationship stories",
                        "Emotional life of renowned artists"
                        ],
                        "nanogenres": [
                        "Emotion, Sexual, Passionate",
                        "Drugs, Depressing, Raw",
                        "Sexual, Weird, Genius",
                        "Hilarious, Sexual, Naked",
                        "Tear-Jerker, Beauty, Happiness",
                        "Emotion, Captivating, Desire",
                        "Chemistry, Gorgeous, Magic",
                        "Hilarious, Nudity, Fame",
                        "Emotion, Discover, Overcome",
                        "Predictable, Sadness, Crying"
                        ]
                    },
                    {
                        "movie_title_formatted": "mr-mme-adelman",
                        "movie_title": "Mr & Mme Adelman",
                        "type": "movie",
                        "year_released": 2017,
                        "imdb_link": "http://www.imdb.com/title/tt6095616/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/431937/",
                        "imdb_id": "tt6095616",
                        "tmdb_id": "431937",
                        "lb_rating": "3.7",
                        "histogram": {
                        "1.0": 27,
                        "2.0": 55,
                        "3.0": 46,
                        "4.0": 190,
                        "5.0": 290,
                        "6.0": 873,
                        "7.0": 1276,
                        "8.0": 2115,
                        "9.0": 696,
                        "10.0": 969,
                        "fans": 162,
                        "lb_rating": "3.7",
                        "total": 6537
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/3/6/5/0/7/0/365070-mr-mme-adelman-0-230-0-345-crop.jpg",
                        "themes": [],
                        "nanogenres": [],
                        "genres": ["Romance", "Drama", "Comedy"],
                        "production_countries": ["Belgium", "France"],
                        "spoken_languages": ["Français"],
                        "popularity": 19.138,
                        "overview": "How did Sarah and Victor get along for more than 45 years? Who was this enigmatic woman living in the shadow of her husband? Love, ambition, betrayals and secrets feed the story of this extraordinary couple, as they experience both the large and small moments of the last century's history.",
                        "runtime": 120,
                        "vote_average": 7.5,
                        "vote_count": 425,
                        "release_date": "2017-03-08",
                        "original_language": "fr"
                    },
                    {
                        "movie_title_formatted": "lord-of-war",
                        "movie_title": "Lord of War",
                        "type": "movie",
                        "year_released": 2005,
                        "imdb_link": "http://www.imdb.com/title/tt0399295/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/1830/",
                        "imdb_id": "tt0399295",
                        "tmdb_id": "1830",
                        "lb_rating": "3.6",
                        "histogram": {
                        "1.0": 277,
                        "2.0": 767,
                        "3.0": 984,
                        "4.0": 4348,
                        "5.0": 6981,
                        "6.0": 24575,
                        "7.0": 31914,
                        "8.0": 33542,
                        "9.0": 7693,
                        "10.0": 6359,
                        "fans": 379,
                        "lb_rating": "3.6",
                        "total": 117440
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/0/7/6/9/50769-lord-of-war-0-230-0-345-crop.jpg",
                        "genres": ["Crime", "Drama", "Thriller"],
                        "production_countries": ["France", "United States of America", "Germany"],
                        "spoken_languages": ["العربية", "Deutsch", "English", "Français", "Pусский", "Español", "Український", "Türkçe"],
                        "popularity": 29.464,
                        "overview": "Yuri Orlov is a globetrotting arms dealer and, through some of the deadliest war zones, he struggles to stay one step ahead of a relentless Interpol agent, his business rivals and even some of his customers who include many of the world's most notorious dictators. Finally, he must also face his own conscience.",
                        "runtime": 122,
                        "vote_average": 7.31,
                        "vote_count": 4544,
                        "release_date": "2005-09-16",
                        "original_language": "en",
                        "themes": [
                        "Politics and human rights",
                        "Crime, drugs and gangsters",
                        "Intense violence and sexual transgression",
                        "Intense political and terrorist thrillers",
                        "Gritty crime and ruthless gangsters",
                        "Riveting political and presidential drama",
                        "Violent crime and drugs",
                        "Racism and the powerful fight for justice"
                        ],
                        "nanogenres": [
                        "Addiction, Moral, Society",
                        "Drama, Morality, Cynical",
                        "Shootings, Firearms, Weapons",
                        "Violence, Guns, Dangerous",
                        "Crime, Government, Moving",
                        "Anti-War, Enemies, Fighter",
                        "Thriller, Guns, Exciting",
                        "Gangster, Class, Crazy",
                        "Gangster, Violence, Drama",
                        "Blood, Exciting, Deadly"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-menu-2022",
                        "movie_title": "The Menu",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt9764362/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/593643/",
                        "imdb_id": "tt9764362",
                        "tmdb_id": "593643",
                        "lb_rating": "3.5",
                        "histogram": {
                        "1.0": 4959,
                        "2.0": 16108,
                        "3.0": 13302,
                        "4.0": 73847,
                        "5.0": 84471,
                        "6.0": 323303,
                        "7.0": 344505,
                        "8.0": 515892,
                        "9.0": 134174,
                        "10.0": 155505,
                        "fans": 4700,
                        "lb_rating": "3.5",
                        "total": 1666066
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/2/1/3/2/3/521323-the-menu-0-230-0-345-crop.jpg",
                        "genres": ["Comedy", "Thriller", "Horror"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English", "Español"],
                        "popularity": 82.161,
                        "overview": "A young couple travels to a remote island to eat at an exclusive restaurant where the chef has prepared a lavish menu, with some shocking surprises.",
                        "runtime": 107,
                        "vote_average": 7.192,
                        "vote_count": 4342,
                        "release_date": "2022-11-17",
                        "original_language": "en",
                        "themes": [
                        "Intense violence and sexual transgression",
                        "Humanity and the world around us",
                        "Twisted dark psychological thriller",
                        "Terrifying, haunted, and supernatural horror"
                        ],
                        "nanogenres": [
                        "Twist, Psychopath, Madness",
                        "Humor, Eating, Mocking",
                        "Killing, Shock, Bizarre",
                        "Weird, Reality, Complicated",
                        "Terrifying, Extreme, Confused",
                        "Thrills, Guessing, Intriguing",
                        "Gory, Disturbing, Guessing",
                        "Guessing, Creepy, Shock",
                        "Eating, Friendship, Ensemble",
                        "Tense, Guessing, Mysterious"
                        ]
                    },
                    {
                        "movie_title_formatted": "glass-onion",
                        "movie_title": "Glass Onion",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt11564570/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/661374/",
                        "imdb_id": "tt11564570",
                        "tmdb_id": "661374",
                        "lb_rating": "3.5",
                        "histogram": {
                        "1.0": 6452,
                        "2.0": 21998,
                        "3.0": 16612,
                        "4.0": 91915,
                        "5.0": 96664,
                        "6.0": 343027,
                        "7.0": 320858,
                        "8.0": 448228,
                        "9.0": 122445,
                        "10.0": 120663,
                        "fans": 1500,
                        "lb_rating": "3.5",
                        "total": 1588862
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/8/6/7/2/3/586723-glass-onion-a-knives-out-mystery-0-230-0-345-crop.jpg",
                        "genres": ["Comedy", "Crime", "Mystery"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 84.356,
                        "overview": "World-famous detective Benoit Blanc heads to Greece to peel back the layers of a mystery surrounding a tech billionaire and his eclectic crew of friends.",
                        "runtime": 140,
                        "vote_average": 7.044,
                        "vote_count": 5093,
                        "release_date": "2022-11-12",
                        "original_language": "en",
                        "themes": [
                        "Thrillers and murder mysteries",
                        "Intriguing and suspenseful murder mysteries",
                        "Suspenseful crime thrillers"
                        ],
                        "nanogenres": [
                        "Murderer, Mysterious, Guessing",
                        "Killer, Crime, Suspects",
                        "Killer, Mysterious, Solving",
                        "Killing, Investigate, Twist",
                        "Humorous, Wit, Formulaic",
                        "Murderer, Clues, Convoluted",
                        "Delightful, Intelligent, Complicated",
                        "Victim, Investigate, Mysterious",
                        "Twist, Intriguing, Intrigue",
                        "Relationships, Mystery, Revelation"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-pale-blue-eye",
                        "movie_title": "The Pale Blue Eye",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt14138650/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/800815/",
                        "imdb_id": "tt14138650",
                        "tmdb_id": "800815",
                        "lb_rating": "3.1",
                        "histogram": {
                        "1.0": 523,
                        "2.0": 1803,
                        "3.0": 2647,
                        "4.0": 12901,
                        "5.0": 21118,
                        "6.0": 46108,
                        "7.0": 30395,
                        "8.0": 19265,
                        "9.0": 3331,
                        "10.0": 4400,
                        "fans": 131,
                        "lb_rating": "3.1",
                        "total": 142491
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/7/1/8/2/4/1/718241-the-pale-blue-eye-0-230-0-345-crop.jpg",
                        "genres": ["Thriller", "Crime", "Horror", "Mystery"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English", "Français", "Latin"],
                        "popularity": 25.209,
                        "overview": "West Point, New York, 1830. When a cadet at the burgeoning military academy is found hanged with his heart cut out, the top brass summons former New York City constable Augustus Landor to investigate. While attempting to solve this grisly mystery, the reluctant detective engages the help of one of the cadets: a strange but brilliant young fellow by the name of Edgar Allan Poe.",
                        "runtime": 128,
                        "vote_average": 6.847,
                        "vote_count": 1678,
                        "release_date": "2022-12-22",
                        "original_language": "en",
                        "themes": [
                        "Thrillers and murder mysteries",
                        "Intriguing and suspenseful murder mysteries",
                        "Suspenseful crime thrillers",
                        "Twisted dark psychological thriller",
                        "Noir and dark crime dramas",
                        "Terrifying, haunted, and supernatural horror"
                        ],
                        "nanogenres": [
                        "Killer, Detectives, Clues",
                        "Crime, Intriguing, Guilty",
                        "Tense, Mysterious, Solving",
                        "Spooky, Killer, Tense",
                        "Crime, Twist, Mysterious",
                        "Emotion, Complexity, Revelation",
                        "Suspense, Detective, Evidence",
                        "Death, Suspense, Dark",
                        "Investigate, Convoluted, Complicated",
                        "Murderer, Mysterious, Guessing"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-northman",
                        "movie_title": "The Northman",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt11138512/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/639933/",
                        "imdb_id": "tt11138512",
                        "tmdb_id": "639933",
                        "lb_rating": "3.8",
                        "histogram": {
                        "1.0": 2310,
                        "2.0": 5719,
                        "3.0": 4516,
                        "4.0": 19343,
                        "5.0": 23446,
                        "6.0": 75877,
                        "7.0": 107753,
                        "8.0": 197241,
                        "9.0": 88632,
                        "10.0": 62085,
                        "fans": 2500,
                        "lb_rating": "3.8",
                        "total": 586922
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/5/6/5/8/5/2/565852-the-northman-0-230-0-345-crop.jpg",
                        "genres": ["Action", "Adventure", "Fantasy"],
                        "production_countries": ["China", "United States of America"],
                        "spoken_languages": ["English", "Íslenska"],
                        "popularity": 138.858,
                        "overview": "Prince Amleth is on the verge of becoming a man when his father is brutally murdered by his uncle, who kidnaps the boy's mother. Two decades later, Amleth is now a Viking who's on a mission to save his mother, kill his uncle and avenge his father.",
                        "runtime": 137,
                        "vote_average": 7.066,
                        "vote_count": 3986,
                        "release_date": "2022-04-07",
                        "original_language": "en",
                        "themes": [
                        "Epic history and literature",
                        "Epic heroes",
                        "Humanity and the world around us",
                        "Fantasy adventure, heroism, and swordplay",
                        "Captivating vision and Shakespearean drama",
                        "Historical battles and epic heroism",
                        "Epic adventure and breathtaking battles",
                        "Bloody vampire horror"
                        ],
                        "nanogenres": [
                        "Hero, Evil, Complex",
                        "Fighting, Epic, Excitement",
                        "Swords, Mythology, Fantasy",
                        "Villain, Bloody, Battle",
                        "Voices, Battle, Action-Packed",
                        "Bloody, Action-Packed, Avenge",
                        "Death, Forest, Trip",
                        "Feelings, Complex, Captivating",
                        "Combat, Swords, Weapons",
                        "Myth, Imaginative, Quest"
                        ]
                    },
                    {
                        "movie_title_formatted": "the-batman",
                        "movie_title": "The Batman",
                        "type": "movie",
                        "year_released": 2022,
                        "imdb_link": "http://www.imdb.com/title/tt1877830/maindetails",
                        "tmdb_link": "https://www.themoviedb.org/movie/414906/",
                        "imdb_id": "tt1877830",
                        "tmdb_id": "414906",
                        "lb_rating": "4.0",
                        "histogram": {
                        "1.0": 4551,
                        "2.0": 15085,
                        "3.0": 8156,
                        "4.0": 55963,
                        "5.0": 47883,
                        "6.0": 240936,
                        "7.0": 255969,
                        "8.0": 685555,
                        "9.0": 359910,
                        "10.0": 482992,
                        "fans": 42000,
                        "lb_rating": "4.0",
                        "total": 2157000
                        },
                        "poster_url": "https://a.ltrbxd.com/resized/film-poster/3/4/8/9/1/4/348914-the-batman-0-230-0-345-crop.jpg",
                        "genres": ["Crime", "Mystery", "Thriller"],
                        "production_countries": ["United States of America"],
                        "spoken_languages": ["English"],
                        "popularity": 184.755,
                        "overview": "In his second year of fighting crime, Batman uncovers corruption in Gotham City that connects to his own family while facing a serial killer known as the Riddler.",
                        "runtime": 177,
                        "vote_average": 7.685,
                        "vote_count": 9462,
                        "release_date": "2022-03-01",
                        "original_language": "en",
                        "themes": [
                        "Crime, drugs and gangsters",
                        "Epic heroes",
                        "High speed and special ops",
                        "Thrillers and murder mysteries",
                        "Superheroes in action-packed battles with villains",
                        "Explosive and action-packed heroes vs. villains",
                        "Violent action, guns, and crime",
                        "Noir and dark crime dramas",
                        "Intriguing and suspenseful murder mysteries"
                        ],
                        "nanogenres": [
                        "Comic-Book, Hero, Exciting",
                        "Fighting, Bullets, Exciting",
                        "Tense, Explosives, Bullets",
                        "Tense, Mysterious, Solving",
                        "Villain, Comic-Book, Campy",
                        "Hero, Evil, Complex",
                        "Villain, Stunts, Vengeance",
                        "Twist, Mysterious, Confusing",
                        "Criminal, Exciting, Climax",
                        "Explosives, Adventure, Predictable"
                        ]
                    }
                ]
    }
    #return await run_in_threadpool(middleware_service.get_random_movies, 24)

@app.get("/recommend/top-picks", dependencies=[Depends(require_api_key)])
async def get_top_picks_endpoint():
    """
    Retrieve top picks from Redis, sorted by popularity (count), limited to 15.
    """
    return  [{"movie_title_formatted":"mission-impossible-iii","poster_url":"https://a.ltrbxd.com/resized/film-poster/5/1/2/0/4/51204-mission-impossible-iii-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"dune-part-two","poster_url":"https://a.ltrbxd.com/resized/film-poster/6/1/7/4/4/3/617443-dune-part-two-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"dune-2021","poster_url":"https://a.ltrbxd.com/resized/sm/upload/nx/8b/vs/gc/cDbNAY0KM84cxXhmj8f0dLWza3t-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"dune-part-two","poster_url":"https://a.ltrbxd.com/resized/film-poster/6/1/7/4/4/3/617443-dune-part-two-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"dune-2021","poster_url":"https://a.ltrbxd.com/resized/sm/upload/nx/8b/vs/gc/cDbNAY0KM84cxXhmj8f0dLWza3t-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"past-lives","poster_url":"https://a.ltrbxd.com/resized/film-poster/5/9/1/0/5/3/591053-past-lives-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"the-talented-mr-ripley","poster_url":"https://a.ltrbxd.com/resized/film-poster/5/1/1/3/8/51138-the-talented-mr-ripley-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"joker-2019","poster_url":"https://a.ltrbxd.com/resized/film-poster/4/0/6/7/7/5/406775-joker-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"the-social-network","poster_url":"https://a.ltrbxd.com/resized/sm/upload/nw/cm/pa/ai/sGQv3ZMZBDBnl3z42Q0mEQ5uiDe-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"oppenheimer-2023","poster_url":"https://a.ltrbxd.com/resized/film-poster/7/8/4/3/2/8/784328-oppenheimer-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"the-prestige","poster_url":"https://a.ltrbxd.com/resized/film-poster/5/1/1/4/7/51147-the-prestige-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"mission-impossible-dead-reckoning-part-one","poster_url":"https://a.ltrbxd.com/resized/film-poster/5/0/3/4/0/2/503402-mission-impossible-dead-reckoning-part-one-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"avatar-the-way-of-water","poster_url":"https://a.ltrbxd.com/resized/film-poster/6/3/0/5/8/63058-avatar-the-way-of-water-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"creed-iii","poster_url":"https://a.ltrbxd.com/resized/film-poster/6/0/1/6/2/4/601624-creed-iii-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"babylon-2022","poster_url":"https://a.ltrbxd.com/resized/film-poster/5/4/2/7/7/3/542773-babylon-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"mr-mme-adelman","poster_url":"https://a.ltrbxd.com/resized/film-poster/3/6/5/0/7/0/365070-mr-mme-adelman-0-230-0-345-crop.jpg","pick_count":0},{"movie_title_formatted":"lord-of-war","poster_url":"https://a.ltrbxd.com/resized/film-poster/5/0/7/6/9/50769-lord-of-war-0-230-0-345-crop.jpg","pick_count":0}]

    #return await run_in_threadpool(middleware_service.get_top_picks, 15)

@app.post("/recommend/add-top-pick", dependencies=[Depends(require_api_key)])
async def publish_top_pick_endpoint(movie: dict):
    """
    Publish a movie to top picks using 'movie_title_formatted' as the unique key.
    """
    #await run_in_threadpool(middleware_service.add_to_top_picks, movie)
    return {"status": "success", "message": "Movie added to top picks"}

@app.post("/recommend/remove-top-pick", dependencies=[Depends(require_api_key)])
async def remove_top_pick_endpoint(movie: dict):
    """
    Remove a movie from top picks using 'movie_title_formatted' as the unique key.
    """
    #await run_in_threadpool(middleware_service.remove_from_top_picks, movie)
    return {"status": "success", "message": "Movie removed from top picks"}

@app.get("/calendar/releases", dependencies=[Depends(require_api_key)])
async def get_calendar_releases_endpoint():
    """
    Fetches upcoming movie releases from Redis.
    """
    return {
        "streamingReleases": [
            {'2026-02-01': [{'title': 'Hurry Up Tomorrow',
                'slug': 'hurry-up-tomorrow-2025',
                'url': 'https://whentostream.com/hurry-up-tomorrow-2025/',
                'release_date': '2026-02-01',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Hurry-Up-Tomorrow-10.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'The Knife',
                'slug': 'the-knife-2024',
                'url': 'https://whentostream.com/the-knife-2024/',
                'release_date': '2026-02-01',
                'release_type': 'streaming',
                'year': '2024',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/The-Knife-1.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Love Brooklyn',
                'slug': 'love-brooklyn-2025',
                'url': 'https://whentostream.com/love-brooklyn-2025/',
                'release_date': '2026-02-01',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Love-Brooklyn-1.jpeg?resize=640%2C960&ssl=1'}],
                '2026-02-03': [{'title': 'The Dutchman',
                'slug': 'the-dutchman-2025',
                'url': 'https://whentostream.com/the-dutchman-2025/',
                'release_date': '2026-02-03',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/The-Dutchman-10-1.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Hamnet',
                'slug': 'hamnet-2025',
                'url': 'https://whentostream.com/hamnet-2025/',
                'release_date': '2026-02-03',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Hamnet-100.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'The Housemaid',
                'slug': 'the-housemaid-2025',
                'url': 'https://whentostream.com/the-housemaid-2025/',
                'release_date': '2026-02-03',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/The-Housemaid-100.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'The Plague',
                'slug': 'the-plague-2025',
                'url': 'https://whentostream.com/the-plague-2025/',
                'release_date': '2026-02-03',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/The-Plague-100.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'The Secret Agent',
                'slug': 'the-secret-agent-2025',
                'url': 'https://whentostream.com/the-secret-agent-2025/',
                'release_date': '2026-02-03',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/The-Secret-Agent-100.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'We Bury The Dead',
                'slug': 'we-bury-the-dead-2026',
                'url': 'https://whentostream.com/we-bury-the-dead-2026/',
                'release_date': '2026-02-03',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/We-Bury-the-Dead-10.jpeg?resize=640%2C960&ssl=1'}],
                '2026-02-04': [{'title': 'Relationship Goals',
                'slug': 'relationship-goals-2026',
                'url': 'https://whentostream.com/relationship-goals-2026/',
                'release_date': '2026-02-04',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Relationship-Goals-2.jpeg?resize=640%2C960&ssl=1'}],
                '2026-02-05': [{'title': 'Ella Mccay',
                'slug': 'ella-mccay-2025',
                'url': 'https://whentostream.com/ella-mccay-2025/',
                'release_date': '2026-02-05',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Ella-McCay-10.jpeg?resize=640%2C960&ssl=1'}],
                '2026-02-06': [{'title': 'Boys Go To Jupiter',
                'slug': 'boys-go-to-jupiter-2025',
                'url': 'https://whentostream.com/boys-go-to-jupiter-2025/',
                'release_date': '2026-02-06',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/11/Boys-Go-to-Jupiter-2.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'La Grazia',
                'slug': 'la-grazia-2025',
                'url': 'https://whentostream.com/la-grazia-2025/',
                'release_date': '2026-02-06',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/La-Grazia-10.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Obex',
                'slug': 'obex-2025',
                'url': 'https://whentostream.com/obex-2025/',
                'release_date': '2026-02-06',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Obex.jpeg?resize=640%2C946&ssl=1'},
                {'title': 'Queen Of Chess',
                'slug': 'queen-of-chess-2026',
                'url': 'https://whentostream.com/queen-of-chess-2026/',
                'release_date': '2026-02-06',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Queen-of-Chess-1-1.jpeg?resize=640%2C800&ssl=1'},
                {'title': 'Splitsville',
                'slug': 'splitsville-2025',
                'url': 'https://whentostream.com/splitsville-2025/',
                'release_date': '2026-02-06',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Splitsville-1.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Violent Ends',
                'slug': 'violent-ends-2025',
                'url': 'https://whentostream.com/violent-ends-2025/',
                'release_date': '2026-02-06',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/11/Violent-Ends-4.jpeg?resize=640%2C960&ssl=1'}],
                '2026-02-08': [{'title': 'Sarahs Oil',
                'slug': 'sarahs-oil-2025',
                'url': 'https://whentostream.com/sarahs-oil-2025/',
                'release_date': '2026-02-08',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Sarahs-Oil-10.jpeg?resize=640%2C960&ssl=1'}],
                '2026-02-10': [{'title': 'The Huntsman',
                'slug': 'the-huntsman-2026',
                'url': 'https://whentostream.com/the-huntsman-2026/',
                'release_date': '2026-02-10',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/The-Huntsman.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Is This Thing On',
                'slug': 'is-this-thing-on-2025',
                'url': 'https://whentostream.com/is-this-thing-on-2025/',
                'release_date': '2026-02-10',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Is-This-Thing-On-10.jpeg?resize=640%2C961&ssl=1'},
                {'title': 'Marty Supreme',
                'slug': 'marty-supreme-2025',
                'url': 'https://whentostream.com/marty-supreme-2025/',
                'release_date': '2026-02-10',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Marty-Supreme-10.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Night Patrol',
                'slug': 'night-patrol-2025',
                'url': 'https://whentostream.com/night-patrol-2025/',
                'release_date': '2026-02-10',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/02/NIght-Patrol-10.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Primate',
                'slug': 'primate-2026',
                'url': 'https://whentostream.com/primate-2026/',
                'release_date': '2026-02-10',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Primate-100.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Rosemead',
                'slug': 'rosemead-2025',
                'url': 'https://whentostream.com/rosemead-2025/',
                'release_date': '2026-02-10',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/11/Rosemead-2.jpeg?resize=640%2C987&ssl=1'}],
                '2026-02-12': [{'title': 'Predator Badlands',
                'slug': 'predator-badlands-2025',
                'url': 'https://whentostream.com/predator-badlands-2025/',
                'release_date': '2026-02-12',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Predator-Badlands-5.jpeg?resize=640%2C960&ssl=1'}],
                '2026-02-13': [{'title': 'Eternity',
                'slug': 'eternity-2025',
                'url': 'https://whentostream.com/eternity-2025/',
                'release_date': '2026-02-13',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/09/Eternity-1.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Honey Bunch',
                'slug': 'honey-bunch-2025',
                'url': 'https://whentostream.com/honey-bunch-2025/',
                'release_date': '2026-02-13',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Honey-Bunch.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Tyler Perrys Joes College Road Trip',
                'slug': 'tyler-perrys-joes-college-road-trip-2026',
                'url': 'https://whentostream.com/tyler-perrys-joes-college-road-trip-2026/',
                'release_date': '2026-02-13',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Tyler-Perrys-Joes-College-Road-Trip-.jpg?resize=640%2C948&ssl=1'}],
                '2026-02-14': [{'title': 'Blue Moon',
                'slug': 'blue-moon-2025',
                'url': 'https://whentostream.com/blue-moon-2025/',
                'release_date': '2026-02-14',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/11/Blue-Moon-10.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Good Fortune',
                'slug': 'good-fortune-2025',
                'url': 'https://whentostream.com/good-fortune-2025/',
                'release_date': '2026-02-14',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/10/Good-Fortune-100.jpeg?resize=640%2C960&ssl=1'}],
                '2026-02-17': [{'title': 'Mercy',
                'slug': 'mercy-2026',
                'url': 'https://whentostream.com/mercy-2026/',
                'release_date': '2026-02-17',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Mercy-10.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Urchin',
                'slug': 'urchin-2025',
                'url': 'https://whentostream.com/urchin-2025/',
                'release_date': '2026-02-17',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/11/Urchin-10.jpeg?resize=640%2C960&ssl=1'}],
                '2026-02-19': [{'title': 'East Of Wall',
                'slug': 'east-of-wall-2025',
                'url': 'https://whentostream.com/east-of-wall-2025/',
                'release_date': '2026-02-19',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/02/East-of-Wall-4.jpeg?resize=640%2C960&ssl=1'}],
                '2026-02-20': [{'title': 'The Astronaut',
                'slug': 'the-astronaut-2025',
                'url': 'https://whentostream.com/the-astronaut-2025/',
                'release_date': '2026-02-20',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/The-Astronaut-10.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Dead Of Winter',
                'slug': 'dead-of-winter-2025',
                'url': 'https://whentostream.com/dead-of-winter-2025/',
                'release_date': '2026-02-20',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Dead-of-Winter-11.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'The Dreadful',
                'slug': 'the-dreadful-2026',
                'url': 'https://whentostream.com/the-dreadful-2026/',
                'release_date': '2026-02-20',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/The-Dreadful.jpeg?resize=640%2C961&ssl=1'}],
                '2026-02-24': [{'title': 'Young Mothers',
                'slug': 'young-mothers-2025',
                'url': 'https://whentostream.com/young-mothers-2025/',
                'release_date': '2026-02-24',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Young-Mothers-10.jpeg?resize=640%2C960&ssl=1'}],
                '2026-02-25': [{'title': 'The Bluff',
                'slug': 'the-bluff-2026',
                'url': 'https://whentostream.com/the-bluff-2026/',
                'release_date': '2026-02-25',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/The-Bluff-.jpg?resize=640%2C960&ssl=1'}],
                '2026-02-27': [{'title': 'Crazy Old Lady',
                'slug': 'crazy-old-lady-2025',
                'url': 'https://whentostream.com/crazy-old-lady-2025/',
                'release_date': '2026-02-27',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/02/Crazy-Old-Lady-2025.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Father Mother Sister Brother',
                'slug': 'father-mother-sister-brother-2025',
                'url': 'https://whentostream.com/father-mother-sister-brother-2025/',
                'release_date': '2026-02-27',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/02/Father-Mother-Sister-Brother-10.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'In The Blink Of An Eye',
                'slug': 'in-the-blink-of-an-eye-2026',
                'url': 'https://whentostream.com/in-the-blink-of-an-eye-2026/',
                'release_date': '2026-02-27',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/In-the-Blink-of-an-Eye-683x1024.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Kiss Of The Spider Woman',
                'slug': 'kiss-of-the-spider-woman-2025',
                'url': 'https://whentostream.com/kiss-of-the-spider-woman-2025/',
                'release_date': '2026-02-27',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/10/Kiss-of-the-Spider-Woman-11.jpeg?resize=640%2C960&ssl=1'}],
                '2026-03-06': [{'title': '100 Nights Of Hero',
                'slug': '100-nights-of-hero-2025',
                'url': 'https://whentostream.com/100-nights-of-hero-2025/',
                'release_date': '2026-03-06',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/100-Nights-of-Hero-10.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Heel',
                'slug': 'heel-2025',
                'url': 'https://whentostream.com/heel-2025/',
                'release_date': '2026-03-06',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Heel.jpg?resize=640%2C948&ssl=1'},
                {'title': 'War Machine',
                'slug': 'war-machine-2026',
                'url': 'https://whentostream.com/war-machine-2026/',
                'release_date': '2026-03-06',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/02/War-Machine-.jpeg?resize=640%2C947&ssl=1'}],
                '2026-03-10': [{'title': 'The Voice Of Hind Rajab',
                'slug': 'the-voice-of-hind-rajab-2025',
                'url': 'https://whentostream.com/the-voice-of-hind-rajab-2025/',
                'release_date': '2026-03-10',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/The-Voice-of-Hind-Rajab-10.jpeg?resize=640%2C905&ssl=1'}],
                '2026-03-14': [{'title': 'I Wish You All The Best',
                'slug': 'i-wish-you-all-the-best-2024',
                'url': 'https://whentostream.com/i-wish-you-all-the-best-2024/',
                'release_date': '2026-03-14',
                'release_type': 'streaming',
                'year': '2024',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/09/I-Wish-You-All-the-Best-1.jpeg?resize=640%2C960&ssl=1'}],
                '2026-03-20': [{'title': 'Peaky Blinders The Immortal Man',
                'slug': 'peaky-blinders-the-immortal-man-2026',
                'url': 'https://whentostream.com/peaky-blinders-the-immortal-man-2026/',
                'release_date': '2026-03-20',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Peaky-Blinders-The-Immortal-Man.jpeg?resize=640%2C800&ssl=1'},
                {'title': 'Wicked For Good',
                'slug': 'wicked-for-good-2025',
                'url': 'https://whentostream.com/wicked-for-good-2025/',
                'release_date': '2026-03-20',
                'release_type': 'streaming',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Wicked-For-Good-100.jpeg?resize=640%2C960&ssl=1'}],
                '2026-03-27': [{'title': 'Mike Nick Nick Alice',
                'slug': 'mike-nick-nick-alice-2026',
                'url': 'https://whentostream.com/mike-nick-nick-alice-2026/',
                'release_date': '2026-03-27',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Mike-and-Nick-and-Nick-and-Alice-2.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Wardriver',
                'slug': 'wardriver-2026',
                'url': 'https://whentostream.com/wardriver-2026/',
                'release_date': '2026-03-27',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Wardriver.jpeg?resize=640%2C946&ssl=1'}],
                '2026-04-10': [{'title': 'Outcome',
                'slug': 'outcome-2026',
                'url': 'https://whentostream.com/outcome-2026/',
                'release_date': '2026-04-10',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/02/Outcome-Horizontal-1-1-e1770145227465-884x1024.jpg?resize=640%2C741&ssl=1'}],
                '2026-04-24': [{'title': 'Apex',
                'slug': 'apex-2026',
                'url': 'https://whentostream.com/apex-2026/',
                'release_date': '2026-04-24',
                'release_type': 'streaming',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Apex-2026.jpeg?resize=640%2C943&ssl=1'}]}


                        ],
                        "theatricalReleases": [
                            {'2026-02-06': [{'title': 'Dracula A Love Tale',
                'slug': 'dracula-a-love-tale-2025',
                'url': 'https://whentostream.com/dracula-a-love-tale-2025/',
                'release_date': '2026-02-06',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Dracula-2026-2.jpeg?resize=640%2C948&ssl=1'},
                {'title': 'Kokuho',
                'slug': 'kokuho-2025',
                'url': 'https://whentostream.com/kokuho-2025/',
                'release_date': '2026-02-06',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Kokuho.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Pillion',
                'slug': 'pillion-2025',
                'url': 'https://whentostream.com/pillion-2025/',
                'release_date': '2026-02-06',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/11/Pillion-1.jpg?resize=640%2C948&ssl=1'},
                {'title': 'The Presidents Cake',
                'slug': 'the-presidents-cake-2025',
                'url': 'https://whentostream.com/the-presidents-cake-2025/',
                'release_date': '2026-02-06',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/The-Presidents-Cake.jpeg?resize=640%2C800&ssl=1'},
                {'title': 'Scarlet',
                'slug': 'scarlet-2025',
                'url': 'https://whentostream.com/scarlet-2025/',
                'release_date': '2026-02-06',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/09/Scarlet.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Sirat',
                'slug': 'sirat-2025',
                'url': 'https://whentostream.com/sirat-2025/',
                'release_date': '2026-02-06',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/02/Sirat-100.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'The Strangers Chapter 3',
                'slug': 'the-strangers-chapter-3-2026',
                'url': 'https://whentostream.com/the-strangers-chapter-3-2026/',
                'release_date': '2026-02-06',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/02/The-Strangers-Chapter-3-3.jpg?resize=640%2C960&ssl=1'},
                {'title': 'Whistle',
                'slug': 'whistle-2026',
                'url': 'https://whentostream.com/whistle-2026/',
                'release_date': '2026-02-06',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/10/Whistle-2.jpeg?resize=640%2C960&ssl=1'}],
                '2026-02-13': [{'title': 'Cold Storage',
                'slug': 'cold-storage-2026',
                'url': 'https://whentostream.com/cold-storage-2026/',
                'release_date': '2026-02-13',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/10/Cold-Storage.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Crime 101',
                'slug': 'crime-101-2026',
                'url': 'https://whentostream.com/crime-101-2026/',
                'release_date': '2026-02-13',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Crime-101-3.jpeg?resize=640%2C948&ssl=1'},
                {'title': 'Goat',
                'slug': 'goat-2026',
                'url': 'https://whentostream.com/goat-2026/',
                'release_date': '2026-02-13',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/10/GOAT.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Good Luck Have Fun Dont Die',
                'slug': 'good-luck-have-fun-dont-die-2026',
                'url': 'https://whentostream.com/good-luck-have-fun-dont-die-2026/',
                'release_date': '2026-02-13',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Good-Luck-Have-Fun-Dont-Die-4.jpeg?resize=640%2C947&ssl=1'},
                {'title': 'Nirvanna The Band The Show The Movie',
                'slug': 'nirvanna-the-band-the-show-the-movie-2025',
                'url': 'https://whentostream.com/nirvanna-the-band-the-show-the-movie-2025/',
                'release_date': '2026-02-13',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/10/Nirvanna-the-Band-The-Show-The-Movie.jpeg?resize=640%2C947&ssl=1'},
                {'title': 'Wuthering Heights',
                'slug': 'wuthering-heights-2026',
                'url': 'https://whentostream.com/wuthering-heights-2026/',
                'release_date': '2026-02-13',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Wuthering-Heights-4.jpg?resize=640%2C800&ssl=1'}],
                '2026-02-20': [{'title': 'Epic Elvis Presley In Concert',
                'slug': 'epic-elvis-presley-in-concert-2025',
                'url': 'https://whentostream.com/epic-elvis-presley-in-concert-2025/',
                'release_date': '2026-02-20',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Epic-Elvis-Presley-in-Concert.jpeg?resize=640%2C961&ssl=1'},
                {'title': 'How To Make A Killing',
                'slug': 'how-to-make-a-killing-2026',
                'url': 'https://whentostream.com/how-to-make-a-killing-2026/',
                'release_date': '2026-02-20',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/11/How-to-Make-a-Killing-2.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Midwinter Break',
                'slug': 'midwinter-break-2026',
                'url': 'https://whentostream.com/midwinter-break-2026/',
                'release_date': '2026-02-20',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Midwinter-Break-1.jpeg?resize=640%2C948&ssl=1'},
                {'title': 'I Can Only Imagine 2',
                'slug': 'i-can-only-imagine-2-2026',
                'url': 'https://whentostream.com/i-can-only-imagine-2-2026/',
                'release_date': '2026-02-20',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/10/I-Can-Only-Imagine-2-.jpg?resize=640%2C948&ssl=1'},
                {'title': 'Psycho Killer',
                'slug': 'psycho-killer-2026',
                'url': 'https://whentostream.com/psycho-killer-2026/',
                'release_date': '2026-02-20',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/10/Psycho-Killer-2.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'This Is Not A Test',
                'slug': 'this-is-not-a-test-2025',
                'url': 'https://whentostream.com/this-is-not-a-test-2025/',
                'release_date': '2026-02-20',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/This-is-Not-a-Test-2.jpeg?resize=640%2C960&ssl=1'}],
                '2026-02-27': [{'title': 'Dreams',
                'slug': 'dreams-2025',
                'url': 'https://whentostream.com/dreams-2025/',
                'release_date': '2026-02-27',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Dreams.jpeg?resize=640%2C946&ssl=1'},
                {'title': 'The Napa Boys',
                'slug': 'the-napa-boys-2025',
                'url': 'https://whentostream.com/the-napa-boys-2025/',
                'release_date': '2026-02-27',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/The-Napa-Boys.jpeg?resize=640%2C948&ssl=1'},
                {'title': 'Scream 7',
                'slug': 'scream-7-2026',
                'url': 'https://whentostream.com/scream-7-2026/',
                'release_date': '2026-02-27',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Scream-7-3.jpeg?resize=640%2C800&ssl=1'}],
                '2026-03-06': [{'title': 'The Bride',
                'slug': 'the-bride-2026',
                'url': 'https://whentostream.com/the-bride-2026/',
                'release_date': '2026-03-06',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/02/The-Bride-4.jpg?resize=640%2C948&ssl=1'},
                {'title': 'Dolly',
                'slug': 'dolly-2025',
                'url': 'https://whentostream.com/dolly-2025/',
                'release_date': '2026-03-06',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Dolly.jpeg?resize=640%2C800&ssl=1'},
                {'title': 'Hoppers',
                'slug': 'hoppers-2026',
                'url': 'https://whentostream.com/hoppers-2026/',
                'release_date': '2026-03-06',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/10/Hoppers-2.jpeg?resize=640%2C960&ssl=1'}],
                '2026-03-13': [{'title': 'Reminders Of Him',
                'slug': 'reminders-of-him-2026',
                'url': 'https://whentostream.com/reminders-of-him-2026/',
                'release_date': '2026-03-13',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/10/Reminders-of-Him-2.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Undertone',
                'slug': 'undertone-2025',
                'url': 'https://whentostream.com/undertone-2025/',
                'release_date': '2026-03-13',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/11/The-Undertone.jpeg?resize=640%2C960&ssl=1'}],
                '2026-03-20': [{'title': 'Project Hail Mary',
                'slug': 'project-hail-mary-2026',
                'url': 'https://whentostream.com/project-hail-mary-2026/',
                'release_date': '2026-03-20',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/10/Project-Hail-Mary-3.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Marc By Sofia',
                'slug': 'marc-by-sofia-2025',
                'url': 'https://whentostream.com/marc-by-sofia-2025/',
                'release_date': '2026-03-20',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/Marc-by-Sofia.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Miroirs No 3',
                'slug': 'miroirs-no-3-2025',
                'url': 'https://whentostream.com/miroirs-no-3-2025/',
                'release_date': '2026-03-20',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Miroirs-No-3-2.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Ready Or Not 2 Here I Come',
                'slug': 'ready-or-not-2-here-i-come-2026',
                'url': 'https://whentostream.com/ready-or-not-2-here-i-come-2026/',
                'release_date': '2026-03-20',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/02/Ready-or-Not-2-Here-I-Come-3-1.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'Tow',
                'slug': 'tow-2025',
                'url': 'https://whentostream.com/tow-2025/',
                'release_date': '2026-03-20',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/02/Tow-2.jpg?resize=640%2C948&ssl=1'}],
                '2026-03-27': [{'title': 'Alpha',
                'slug': 'alpha-2025',
                'url': 'https://whentostream.com/alpha-2025/',
                'release_date': '2026-03-27',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Alpha-3.jpeg?resize=640%2C948&ssl=1'},
                {'title': 'Kontinental 25',
                'slug': 'kontinental-25-2025',
                'url': 'https://whentostream.com/kontinental-25-2025/',
                'release_date': '2026-03-27',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Kontinental-25.jpeg?resize=640%2C960&ssl=1'},
                {'title': 'They Will Kill You',
                'slug': 'they-will-kill-you-2026',
                'url': 'https://whentostream.com/they-will-kill-you-2026/',
                'release_date': '2026-03-27',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/They-Will-Kill-You-2.jpeg?resize=640%2C800&ssl=1'}],
                '2026-04-01': [{'title': 'The Super Mario Galaxy Movie',
                'slug': 'the-super-mario-galaxy-movie-2026',
                'url': 'https://whentostream.com/the-super-mario-galaxy-movie-2026/',
                'release_date': '2026-04-01',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/The-Super-Mario-Galaxy-Movie-5.jpeg?resize=640%2C800&ssl=1'}],
                '2026-04-03': [{'title': 'The Drama',
                'slug': 'the-drama-2026',
                'url': 'https://whentostream.com/the-drama-2026/',
                'release_date': '2026-04-03',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/02/The-Drama-7.jpeg?resize=640%2C960&ssl=1'}],
                '2026-04-10': [{'title': 'Exit 8',
                'slug': 'exit-8-2025',
                'url': 'https://whentostream.com/exit-8-2025/',
                'release_date': '2026-04-10',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/02/Exit-8.jpeg?resize=640%2C948&ssl=1'},
                {'title': 'You Me Tuscany',
                'slug': 'you-me-tuscany-2026',
                'url': 'https://whentostream.com/you-me-tuscany-2026/',
                'release_date': '2026-04-10',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/11/You-Me-Tuscany.jpeg?resize=640%2C800&ssl=1'}],
                '2026-04-17': [{'title': 'Lee Cronins The Mummy',
                'slug': 'lee-cronins-the-mummy-2026',
                'url': 'https://whentostream.com/lee-cronins-the-mummy-2026/',
                'release_date': '2026-04-17',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/01/The-Mummy-2.jpeg?resize=640%2C948&ssl=1'},
                {'title': 'Normal',
                'slug': 'normal-2025',
                'url': 'https://whentostream.com/normal-2025/',
                'release_date': '2026-04-17',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Normal-2.jpeg?resize=640%2C948&ssl=1'}],
                '2026-04-24': [{'title': 'Michael',
                'slug': 'michael-2026',
                'url': 'https://whentostream.com/michael-2026/',
                'release_date': '2026-04-24',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2026/02/Michael-4.jpg?resize=640%2C948&ssl=1'},
                {'title': 'Mother Mary',
                'slug': 'mother-mary-2026',
                'url': 'https://whentostream.com/mother-mary-2026/',
                'release_date': '2026-04-24',
                'release_type': 'in-theaters',
                'year': '2026',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Mother-Mary-2.jpg?resize=640%2C948&ssl=1'},
                {'title': 'Omaha',
                'slug': 'omaha-2025',
                'url': 'https://whentostream.com/omaha-2025/',
                'release_date': '2026-04-24',
                'release_type': 'in-theaters',
                'year': '2025',
                'poster_url': 'https://i0.wp.com/whentostream.com/wp-content/uploads/2025/12/Omaha.jpeg?resize=640%2C960&ssl=1'}]}
        ]
    }
    
    #return await middleware_service.fetch_from_redis("upcoming_releases")

@app.get("/announcements", response_model=List[Dict[str, Any]], dependencies=[Depends(require_api_key)])
async def get_announcements():
    """
    Returns a list of new announcements.
    """
    return [
        {
            "title": "New Feature Released",
            "description": "You can now customize your dashboard layout in settings.",
            "date": "2025-10-30T10:00:00Z",
        },
        {
            "title": "System Maintenance",
            "description": "Scheduled downtime on Sunday 01/02/2026 at 2 AM UTC for backend upgrades.",
            "date": "2025-10-25T02:00:00Z",
        },
        {
            "title": "Account Verification",
            "description": "Please verify your email to unlock advanced features.",
            "date": "2025-10-10T09:00:00Z",
        }
    ]
    
    #return await middleware_service.fetch_from_redis("announcements")


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
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
    