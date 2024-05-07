import json
import os

import redis

from processing.utils.utils import default_converter


class RedisClient:
    def __init__(self):
        self.URL = os.getenv('REDIS_URL')
        self.PORT = os.getenv('REDIS_PORT')
        self.DB = os.getenv('REDIS_DB')
        self.RECS_QUEUE = os.getenv('REDIS_QUEUE_RECS')
        self.client = redis.Redis(host=self.URL, port=self.PORT, db=self.DB)

    def publish_recs_analytics(self, username: str, user_recommendation: list, user_analytics: dict):
        """
        Publishes the user recommendation and analytics to the Redis queue
        :param username:
        :param user_recommendation: list of recommended items
        :param user_analytics: dictionary of user analytics
        """
        print(f'Publishing recommendation and analytics to Redis queue {self.RECS_QUEUE}: \n',
              user_recommendation, user_analytics)
        self.client.publish(self.RECS_QUEUE,
                            json.dumps({
                                'username': username,
                                'user_recommendation': user_recommendation,
                                'user_analytics': user_analytics
                            }, default=default_converter)
                            )

