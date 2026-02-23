from airflow.decorators import dag, task
from datetime import datetime, timedelta
from app_logger.app_logger import setup_logger

from database.mongodb_client import MongoDBClient
from middleware.middleware import MiddlewareService

default_args = {
    'owner': 'DijkstraFTW',
    'start_date': datetime(2024, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

logger = setup_logger("../logs/update_dag.log", "PopularMoviesDAG")

dag('update_popular_movies', default_args=default_args, schedule='0 6 * * *', catchup=False, description='Updates popular movies in Redis weekly')
def update_popular_movies_dag():

    @task
    def fetch_top_reviewed_movies(limit: int = 20):
        logger.info(f"Starting fetch_top_reviewed_movies with limit={limit}")
        try:
            mongo = MongoDBClient()
            logger.info("Connected to MongoDB successfully")

            collection = mongo.client[mongo.database].movies
            logger.info("Fetching top reviewed movies from MongoDB")

            top_movies_cursor = collection.find().sort([("histogram.total", -1)]).limit(limit)
            top_movies = []
            for m in top_movies_cursor:
                top_movies.append({
                    "id": m.get("movie_title_formatted", m["movie_title"]),
                    "title": m["movie_title"],
                    "year": m.get("year", 0),
                    "rating": float(m.get("lb_rating", 0.0)),
                    "genres": m.get("genres", []),
                    "source": "Popular"
                })

            logger.info(f"Fetched {len(top_movies)} movies successfully")
            return top_movies

        except Exception as e:
            logger.error(f"Error fetching top reviewed movies: {e}", exc_info=True)
            raise

    @task
    def write_to_redis(movies):
        logger.info("Starting write_to_redis task")
        try:
            middleware_service = MiddlewareService()
            middleware_service.redis_db["popular_movies"] = movies[:20]
            logger.info(f"Successfully wrote {len(movies[:20])} movies to Redis under key 'popular_movies'")
        except Exception as e:
            logger.error(f"Error writing movies to Redis: {e}", exc_info=True)
            raise

    movies = fetch_top_reviewed_movies()
    write_to_redis(movies)

update_popular_movies_dag = update_popular_movies_dag()