import json
import os
import redis

from processing.utils.utils import default_converter
from app_logger.app_logger import setup_logger

logger = setup_logger("/root/letterboxd-movie-rec/logs/redis_client.log", "RedisClient")


class RedisClient:
    def __init__(self):
        try:
            self.URL = os.getenv('REDIS_HOST')
            self.PORT = os.getenv('REDIS_PORT')
            self.DB = os.getenv('REDIS_DB')
            self.PASSWORD = os.getenv('REDIS_PASSWORD')
            self.RECS_QUEUE = os.getenv('REDIS_QUEUE_RECS')
            self.client = redis.Redis(host=self.URL, port=self.PORT, db=self.DB, password=self.PASSWORD)
            logger.info(f"Initialized Redis client with host={self.URL}, port={self.PORT}, db={self.DB}")
        except Exception as e:
            logger.error(f"Error initializing Redis client: {e}", exc_info=True)
            raise

    def publish_recs_analytics(self, username: str, run_id: str, user_recommendation: list, user_analytics: dict, scrape_failed: bool = False):
        """
        Publishes the user recommendation and analytics to a per-user, per-run Redis key with TTL.
        """
        try:
            message = {
                'username': username,
                'user_recommendation': user_recommendation,
                'user_analytics': user_analytics,
                'scrape_failed': scrape_failed,
            }

            key = f"recs:{username}:{run_id}" if run_id else f"recs:{username}"
            logger.info(f"Writing recommendation and analytics to Redis key '{key}'.")
            json_message = json.dumps(message, default=default_converter)
            self.client.setex(key, 300, json_message)  # 5 min TTL
            logger.info(f"Successfully wrote data to Redis key '{key}'.")
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error while publishing to queue '{self.RECS_QUEUE}': {e}", exc_info=True)
            raise
        except TypeError as e:
            logger.error(f"Serialization error for user '{username}' data: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error publishing to Redis queue '{self.RECS_QUEUE}': {e}", exc_info=True)
            raise

    def publish_scrape_warning(self, username: str, run_id: str = ""):
        """
        Writes a scrape_failed warning to Redis early so the frontend can show it while still polling for results.
        """
        key = f"recs:{username}:{run_id}" if run_id else f"recs:{username}"
        message = json.dumps({"scrape_failed": True, "user_recommendation": [], "user_analytics": {}})
        self.client.setex(key, 300, message)
        logger.info(f"Wrote scrape warning to Redis key '{key}' for user '{username}'.")

    def publish_recs_error(self, username: str, reason: str = "dag_failed", run_id: str = ""):
        """
        Writes an error marker to the per-user Redis key so the frontend can stop polling.
        """
        key = f"recs:{username}:{run_id}" if run_id else f"recs:{username}"
        message = json.dumps({"error": reason, "user_recommendation": [], "user_analytics": {}})
        self.client.setex(key, 120, message)  # 2 min TTL
        logger.info(f"Wrote error marker to Redis key '{key}' for user '{username}'.")

    def publish_recently_recommended(self, recommendations: list, max_size: int = 24):
        """
        Pushes recommendations into the 'recently_recommended' Redis list,
        deduplicating by movie_title_formatted and capping the list at max_size.
        """
        RECENTLY_RECOMMENDED_KEY = "recently_recommended"
        FIELDS = ("movie_title", "movie_title_formatted", "poster_url", "lb_rating", "genres", "histogram", "runtime")
        try:
            # Read existing entries to deduplicate
            existing_raw = self.client.lrange(RECENTLY_RECOMMENDED_KEY, 0, -1)
            existing_slugs = set()
            for raw in existing_raw:
                try:
                    item = json.loads(raw)
                    slug = item.get("movie_title_formatted") or item.get("movie_title")
                    if slug:
                        existing_slugs.add(slug)
                except Exception:
                    continue

            pushed = 0
            for movie in recommendations:
                slug = movie.get("movie_title_formatted") or movie.get("movie_title")
                if not slug or slug in existing_slugs:
                    continue
                entry = {k: movie.get(k) for k in FIELDS}
                self.client.rpush(RECENTLY_RECOMMENDED_KEY, json.dumps(entry, default=default_converter))
                existing_slugs.add(slug)
                pushed += 1

            # Trim to keep only the latest max_size entries
            self.client.ltrim(RECENTLY_RECOMMENDED_KEY, -max_size, -1)
            logger.info(f"Pushed {pushed} new movies to '{RECENTLY_RECOMMENDED_KEY}' (capped at {max_size}).")
        except Exception as e:
            logger.error(f"Error publishing to '{RECENTLY_RECOMMENDED_KEY}': {e}", exc_info=True)
