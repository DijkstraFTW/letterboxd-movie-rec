import sys
sys.path.insert(0, "/root/letterboxd-movie-rec")

import json
from dotenv import load_dotenv
from airflow.decorators import dag, task
from datetime import datetime, timedelta
from app_logger.app_logger import setup_logger

load_dotenv("/root/letterboxd-movie-rec/.env")

from database.mongodb_client import MongoDBClient
from messaging.redis_client import RedisClient

default_args = {
    'owner': 'DijkstraFTW',
    'start_date': datetime(2024, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

logger = setup_logger("/root/letterboxd-movie-rec/logs/update_dag.log", "PopularMoviesDAG")

@dag('update_popular_movies', default_args=default_args, schedule='0 6 * * *', catchup=False, description='Updates popular movies in Redis weekly')
def update_popular_movies_dag():

    @task
    def fetch_top_reviewed_movies(limit: int = 24):
        logger.info(f"Starting fetch_top_reviewed_movies with limit={limit}")
        try:
            mongo = MongoDBClient()
            top_movies = mongo.get_weekly_popular_movies(limit=limit)
            logger.info(f"Fetched {len(top_movies)} movies successfully")
            return top_movies
        except Exception as e:
            logger.error(f"Error fetching top reviewed movies: {e}", exc_info=True)
            raise

    @task
    def write_to_redis(movies):
        logger.info("Starting write_to_redis task")
        try:
            redis_client = RedisClient()
            redis_client.client.set("popular_movies", json.dumps(movies[:24]))
            logger.info(f"Successfully wrote {len(movies[:24])} movies to Redis under key 'popular_movies'")
        except Exception as e:
            logger.error(f"Error writing movies to Redis: {e}", exc_info=True)
            raise

    movies = fetch_top_reviewed_movies()
    write_to_redis(movies)

update_popular_movies_dag = update_popular_movies_dag()