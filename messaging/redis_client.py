import json
import os
import redis

from processing.utils.utils import default_converter
from app_logger.app_logger import setup_logger

logger = setup_logger("../logs/redis_client.log", "RedisClient")


class RedisClient:
    def __init__(self):
        try:
            self.URL = os.getenv('REDIS_HOST')
            self.PORT = os.getenv('REDIS_PORT')
            self.DB = os.getenv('REDIS_DB')
            self.RECS_QUEUE = os.getenv('REDIS_QUEUE_RECS')
            self.client = redis.Redis(host=self.URL, port=self.PORT, db=self.DB)
            logger.info(f"Initialized Redis client with host={self.URL}, port={self.PORT}, db={self.DB}")
        except Exception as e:
            logger.error(f"Error initializing Redis client: {e}", exc_info=True)
            raise

    def publish_recs_analytics(self, username: str, user_recommendation: list, user_analytics: dict):
        """
        Publishes the user recommendation and analytics to the Redis queue
        """
        try:
            message = {
                'username': username,
                'user_recommendation': user_recommendation,
                'user_analytics': user_analytics
            }

            logger.info(f"Publishing recommendation and analytics to Redis queue '{self.RECS_QUEUE}' for user '{username}'.")
            json_message = json.dumps(message, default=default_converter)
            self.client.publish(self.RECS_QUEUE, json_message)
            logger.info(f"Successfully published data to Redis queue '{self.RECS_QUEUE}'.")
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error while publishing to queue '{self.RECS_QUEUE}': {e}", exc_info=True)
            raise
        except TypeError as e:
            logger.error(f"Serialization error for user '{username}' data: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error publishing to Redis queue '{self.RECS_QUEUE}': {e}", exc_info=True)
            raise
