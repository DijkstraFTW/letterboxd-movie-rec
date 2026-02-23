import sys
import math
import asyncio
from datetime import datetime, timedelta

from database.mongodb_client import MongoDBClient
from processing.scraping.movies_scraping import MoviesScraping
from processing.scraping.user_reviews_scraping import UserReviewsScraping
from middleware.middleware import MiddlewareService
from airflow.decorators import dag, task
from dotenv import load_dotenv
from app_logger.app_logger import setup_logger

sys.path.insert(0, "/home/ubuntu/app/")

load_dotenv()

default_args = {
    'owner': 'DijkstraFTW',
    'start_date': datetime(2024, 1, 1),
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

logger = setup_logger("../logs/bulk_dag.log", "BulkScrapingDAG")


@dag(
    'letterboxd_bulk_scraping_dag',
    default_args=default_args,
    schedule='0 3 1 * *',
    catchup=False,
    concurrency=4,
    description='Scraping Letterboxd data and storing it in MongoDB'
)
def letterboxd_bulk_scraping():

    @task
    def scraping_users_reviews():
        logger.info("Starting scraping_users_reviews task.")
        try:
            user_reviews_scraping = UserReviewsScraping()
            top_users = user_reviews_scraping.get_popular_users()
            logger.info(f"Fetched {len(top_users)} popular users.")

            mongodb = MongoDBClient()
            logger.info("Connected to MongoDB for user scraping.")

            mongodb.delete_all_users()
            mongodb.delete_all_ratings()
            mongodb.insert_users(top_users)
            logger.info("Replaced all users and ratings in MongoDB with new top users data.")

            for user in top_users:
                ratings = user_reviews_scraping.get_user_ratings(user['username'], user['user_id'])
                mongodb.insert_ratings(ratings)
                logger.info(f"Inserted ratings for user: {user['username']}")

            logger.info("MongoDB operations completed successfully for scraping_users_reviews.")
        except Exception as e:
            logger.error(f"Error in scraping_users_reviews: {e}", exc_info=True)
            raise

    @task
    def batching_movies_shows(batch_size=100):
        logger.info(f"Starting batching_movies_shows with batch_size={batch_size}.")
        try:
            mongodb = MongoDBClient()
            logger.info("Connected to MongoDB for batching movies and shows.")

            movies_list = mongodb.read_all_rated_movies()
            existing_movies_set = set(mongodb.read_all_movies_title_formatted())
            updated_movies_set = set(movies_list)
            movies_to_scrap_list = list(updated_movies_set.difference(existing_movies_set))
            logger.info(f"Found {len(movies_to_scrap_list)} new movies to scrape.")

            num_batches = math.ceil(len(movies_to_scrap_list) / batch_size)
            batches = [movies_to_scrap_list[i*batch_size:(i+1)*batch_size] for i in range(num_batches)]
            logger.info(f"Created {num_batches} batches for scraping.")
            return batches
        except Exception as e:
            logger.error(f"Error in batching_movies_shows: {e}", exc_info=True)
            raise

    @task
    def scraping_movies_shows(batch):
        logger.info(f"Starting scraping_movies_shows for batch of size {len(batch)}.")
        async def scrape_movies_async():
            try:
                mongodb = MongoDBClient()
                logger.info("Connected to MongoDB for scraping movies and shows.")

                movies_scraping = MoviesScraping(batch, max_concurrent=4, requests_per_second=2)
                async with movies_scraping:
                    logger.info("Initialized MoviesScraping session.")
                    letterboxd_movies = await movies_scraping.get_rated_movies()
                    logger.info(f"Retrieved {len(letterboxd_movies)} rated movies from Letterboxd.")

                    tasks = []
                    for movie in letterboxd_movies:
                        tasks.append(movies_scraping.fetch_movie_posters(movie))
                        if movie["type"] != "none" and movie.get("tmdb_id"):
                            tasks.append(movies_scraping.fetch_themoviedb_data(movie, movie["type"]))
                        tasks.append(movies_scraping.fetch_movies_genres(movie, "themes"))
                        tasks.append(movies_scraping.fetch_movies_genres(movie, "nanogenres"))

                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    logger.info(f"Fetched additional metadata for {len(letterboxd_movies)} movies.")

                    result_index = 0
                    for movie in letterboxd_movies:
                        posters = results[result_index] if not isinstance(results[result_index], Exception) else {}
                        result_index += 1

                        themoviedb = {}
                        if movie["type"] != "none" and movie.get("tmdb_id"):
                            themoviedb = results[result_index] if not isinstance(results[result_index], Exception) else {}
                            result_index += 1

                        themes = results[result_index] if not isinstance(results[result_index], Exception) else {"themes": []}
                        result_index += 1

                        nanogenres = results[result_index] if not isinstance(results[result_index], Exception) else {"nanogenres": []}
                        result_index += 1

                        combined_movie_item = {**movie, **posters, **themoviedb, **themes, **nanogenres}

                        if combined_movie_item["type"] != "none":
                            mongodb.insert_movies(combined_movie_item)
                            logger.info(f"Inserted movie: {combined_movie_item.get('movie_title', 'Unknown Title')}")

                logger.info("MongoDB operations completed successfully after movie scraping.")
            except Exception as e:
                logger.error(f"Error in scraping_movies_shows batch: {e}", exc_info=True)
                raise

        asyncio.run(scrape_movies_async())

    @task
    def cleanup_redis():
        logger.info("Starting cleanup_redis task.")
        try:
            keys_to_trim = ["recently_recommended", "popular_movies", "top_picks"]
            middleware = MiddlewareService()

            for key in keys_to_trim:
                if key == "top_picks":
                    top_picks_data = middleware.redis_db.get("top_picks", {})
                    sorted_items = dict(
                        sorted(top_picks_data.items(), key=lambda item: item[1]["count"], reverse=True)[:20]
                    )
                    middleware.redis_db[key] = sorted_items
                    logger.info(f"Trimmed 'top_picks' to top 20 entries.")
                else:
                    current_list = middleware.redis_db.get(key, [])
                    middleware.redis_db[key] = current_list[-20:]
                    logger.info(f"Trimmed Redis list '{key}' to last 20 entries.")

            logger.info("Redis cleanup completed successfully.")
        except Exception as e:
            logger.error(f"Error in cleanup_redis: {e}", exc_info=True)
            raise

    scrape_users_reviews_task = scraping_users_reviews()
    batch_movies_shows_task = batching_movies_shows()
    scrape_movies_shows_task = scraping_movies_shows()
    scrape_movies_shows_task.expand(batch=batch_movies_shows_task.output)
    cleanup_task = cleanup_redis()

    scrape_users_reviews_task >> batch_movies_shows_task >> scrape_movies_shows_task >> cleanup_task


letterboxd_bulk_scraping = letterboxd_bulk_scraping()
