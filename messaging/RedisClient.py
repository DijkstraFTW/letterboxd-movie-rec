import json
import os
import redis


class RedisClient:
    def __init__(self):
        self.URL = os.getenv('REDIS_URL')
        self.PORT = os.getenv('REDIS_PORT')
        self.DB = os.getenv('REDIS_DB')
        self.RECS_QUEUE = os.getenv('REDIS_QUEUE_RECS')
        self.client = redis.Redis(host=self.URL, port=self.PORT, db=self.DB)

    def publish_recs_analytics(self, user_recommendation, user_analytics):
        self.client.publish(self.RECS_QUEUE,
                            json.dumps({'user_recommendation': user_recommendation, 'user_analytics': user_analytics}))
