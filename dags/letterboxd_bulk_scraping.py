import sys
sys.path.insert(0, "/root/letterboxd-movie-rec")

import math
import asyncio
from datetime import datetime, timedelta

from database.mongodb_client import MongoDBClient
from processing.scraping.movies_scraping import MoviesScraping
from processing.scraping.user_reviews_scraping import UserReviewsScraping
from processing.data.data_loader import DataLoader
from prediction.recommendation_engine import RecommendationEngine
from middleware.middleware import MiddlewareService
from airflow.decorators import dag, task
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from dotenv import load_dotenv
from app_logger.app_logger import setup_logger

load_dotenv("/root/letterboxd-movie-rec/.env")

default_args = {
    'owner': 'DijkstraFTW',
    'start_date': datetime(2024, 1, 1),
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

logger = setup_logger("/root/letterboxd-movie-rec/logs/bulk_dag.log", "BulkScrapingDAG")


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
    def scraping_users_reviews(full_scrape=False):
        logger.info(f"Starting scraping_users_reviews task (full_scrape={full_scrape}).")
        async def _run():
            try:
                async with UserReviewsScraping() as user_reviews_scraping:
                    top_users = await user_reviews_scraping.get_popular_users()
                    logger.info(f"Fetched {len(top_users)} popular users.")

                    mongodb = MongoDBClient()
                    logger.info("Connected to MongoDB for user scraping.")

                    if full_scrape:
                        since_date = None
                        logger.info("Full scrape mode: fetching all ratings.")
                    else:
                        since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                        logger.info(f"Fetching ratings since {since_date}.")

                    for user in top_users:
                        user_id = mongodb.upsert_user(user)
                        user['user_id'] = user_id
                        await user_reviews_scraping.reset_session()
                        ratings = await user_reviews_scraping.get_user_ratings(user['username'], user_id, since_date=since_date)
                        mongodb.insert_ratings(ratings)
                        logger.info(f"Inserted ratings for user: {user['username']}")

                    logger.info("MongoDB operations completed successfully for scraping_users_reviews.")
            except Exception as e:
                logger.error(f"Error in scraping_users_reviews: {e}", exc_info=True)
                raise
        asyncio.run(_run())

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

                movies_scraping = MoviesScraping(batch, max_concurrent=2, requests_per_second=1)
                async with movies_scraping:
                    logger.info("Initialized MoviesScraping session.")
                    letterboxd_movies = await movies_scraping.get_rated_movies()
                    logger.info(f"Retrieved {len(letterboxd_movies)} rated movies from Letterboxd.")

                    letterboxd_movies = [m for m in letterboxd_movies if m.get("type")]

                    tasks = []
                    for movie in letterboxd_movies:
                        if movie["type"] != "none" and movie.get("tmdb_id"):
                            tasks.append(movies_scraping.fetch_themoviedb_data(movie, movie["type"]))
                        tasks.append(movies_scraping.fetch_movies_genres(movie, "themes"))
                        tasks.append(movies_scraping.fetch_movies_genres(movie, "nanogenres"))

                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    logger.info(f"Fetched additional metadata for {len(letterboxd_movies)} movies.")

                    result_index = 0
                    for movie in letterboxd_movies:
                        themoviedb = {}
                        if movie["type"] != "none" and movie.get("tmdb_id"):
                            themoviedb = results[result_index] if not isinstance(results[result_index], Exception) else {}
                            result_index += 1

                        themes = results[result_index] if not isinstance(results[result_index], Exception) else {"themes": []}
                        result_index += 1

                        nanogenres = results[result_index] if not isinstance(results[result_index], Exception) else {"nanogenres": []}
                        result_index += 1

                        combined_movie_item = {**movie, **themoviedb, **themes, **nanogenres}

                        if combined_movie_item["type"] != "none":
                            mongodb.insert_movies(combined_movie_item)

                logger.info("MongoDB operations completed successfully after movie scraping.")
            except Exception as e:
                logger.error(f"Error in scraping_movies_shows batch: {e}", exc_info=True)
                raise

        asyncio.run(scrape_movies_async())

    @task
    def cleanup_redis():
        logger.info("Starting cleanup_redis task.")
        try:
            middleware = MiddlewareService()
            client = middleware.client

            for key in ["recently_recommended", "popular_movies"]:
                key_type = client.type(key)
                if key_type == b"list":
                    client.ltrim(key, -20, -1)
                elif key_type == b"string":
                    raw = client.get(key)
                    if raw:
                        import json
                        data = json.loads(raw)
                        if isinstance(data, list):
                            client.set(key, json.dumps(data[-20:]))
                logger.info(f"Trimmed Redis key '{key}' to last 20 entries.")

            keys = client.hkeys("top_picks")
            movie_ids = list(set(k.decode().split(":")[0] for k in keys))
            movie_counts = []
            for movie_id in movie_ids:
                count_bytes = client.hget("top_picks", f"{movie_id}:count")
                count = int(count_bytes) if count_bytes else 0
                movie_counts.append((movie_id, count))
            movie_counts.sort(key=lambda x: x[1], reverse=True)
            for movie_id, _ in movie_counts[20:]:
                client.hdel("top_picks", f"{movie_id}:info", f"{movie_id}:count")
            logger.info(f"Trimmed 'top_picks' to top 20 entries.")

            logger.info("Redis cleanup completed successfully.")
        except Exception as e:
            logger.error(f"Error in cleanup_redis: {e}", exc_info=True)
            raise

    @task
    def train_recommendation_model():
        now = datetime.now()
        week = now.isocalendar()[1]
        bundle_path = f'/root/letterboxd-movie-rec/prediction/models/svd_model_{week}_{now.month}_{now.year}.pkl'
        logger.info("Starting train_recommendation_model task.")
        try:
            data_loader = DataLoader()

            df_ratings = data_loader.load_ratings(include_engagement_features=True)
            logger.info(f"Loaded {len(df_ratings)} ratings.")

            df_ratings = data_loader.apply_engagement_weights(df_ratings)
            logger.info("Applied engagement weights to ratings.")

            df_movies = data_loader.load_movies()
            logger.info(f"Loaded {len(df_movies)} movies.")

            engine = RecommendationEngine()
            engine.build_and_train_model(
                ratings_df=df_ratings,
                movies_df=df_movies,
                bundle_path=bundle_path,
                perform_grid_search=True,
                use_weighted_ratings=True,
            )
            logger.info(f"Model training complete. Bundle saved to {bundle_path}.")
        except Exception as e:
            logger.error(f"Error in train_recommendation_model: {e}", exc_info=True)
            raise

    scrape_users_reviews_task = scraping_users_reviews(full_scrape=False)
    batch_movies_shows_task = batching_movies_shows()
    scrape_movies_shows_task = scraping_movies_shows.expand(batch=batch_movies_shows_task)
    cleanup_task = cleanup_redis()
    train_model_task = train_recommendation_model()
    trigger_storage_watchdog = TriggerDagRunOperator(
        task_id="trigger_storage_watchdog",
        trigger_dag_id="storage_watchdog_dag",
        wait_for_completion=False,
    )

    scrape_users_reviews_task >> batch_movies_shows_task >> scrape_movies_shows_task >> cleanup_task >> train_model_task >> trigger_storage_watchdog


letterboxd_bulk_scraping = letterboxd_bulk_scraping()
