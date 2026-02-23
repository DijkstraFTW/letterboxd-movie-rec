import sys
sys.path.insert(0, "/root/letterboxd-movie-rec")

import asyncio

from messaging.redis_client import RedisClient
from prediction.recommendation_engine import RecommendationEngine
from processing.analytics.user_analytics import UserAnalytics
from processing.utils.utils import load_latest_model

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.operators.python import get_current_context
from dotenv import load_dotenv
from app_logger.app_logger import setup_logger

from processing.scraping.user_reviews_scraping import UserReviewsScraping
from database.mongodb_client import MongoDBClient

logger = setup_logger("/root/letterboxd-movie-rec/logs/rec_dag.log", "UserScrapingDAG")

load_dotenv("/root/letterboxd-movie-rec/.env")

def on_dag_failure(context):
    username = context.get('dag_run').conf.get('letterboxd_username') or context.get('dag_run').conf.get('username', '')
    if username:
        try:
            from messaging.redis_client import RedisClient
            RedisClient().publish_recs_error(username, reason="dag_failed")
            logger.error(f"DAG failure callback: wrote error marker for '{username}'")
        except Exception as e:
            logger.error(f"DAG failure callback: could not write error marker: {e}")


default_args = {
    'owner': 'DijkstraFTW',
    'start_date': datetime(2024, 1, 1),
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'provide_context': True,
    'on_failure_callback': on_dag_failure,
}


@dag('letterboxd_user_scraping', default_args=default_args, schedule=None,
     description='Provides recommendations for a user based on a pre-trained model.')
def letterboxd_user_recommendation():

    @task(multiple_outputs=True)
    def setup_context():
        logger.info("Setting up context for DAG run.")
        try:
            dag_run = get_current_context()['dag_run']
            if dag_run and dag_run.conf:
                username = dag_run.conf.get('letterboxd_username') or dag_run.conf.get('username', 'default_username')
                type_ = dag_run.conf.get('type', 'new')
                data_opt_out = not dag_run.conf.get('data_opt_in', True)
                genres = dag_run.conf.get('genres', [])
                minimum_rating = dag_run.conf.get('minimum_rating', 0.0)
                run_id = dag_run.conf.get('run_id', '')
            else:
                username = 'default_username'
                type_ = 'new'
                data_opt_out = False
                genres = []
                minimum_rating = 0.0
                run_id = ''

            logger.info(f"Context initialized with username={username}, type={type_}, data_opt_out={data_opt_out}, genres={genres}, minimum_rating={minimum_rating}, run_id={run_id}")
            return dict(username=username, type=type_, data_opt_out=data_opt_out, genres=genres, minimum_rating=minimum_rating, run_id=run_id)
        except Exception as e:
            logger.error(f"Error in setup_context: {e}", exc_info=True)
            raise

    @task(multiple_outputs=True)
    def scraping_user_reviews(username: str, data_opt_out: bool, request_run_id: str = ""):
        logger.info(f"Starting scraping_user_reviews for username={username}, data_opt_out={data_opt_out}")
        async def scrape_user_data():
            try:
                async with UserReviewsScraping() as scraper:
                    if username == 'default_username':
                        logger.warning("Default username detected, returning empty user reviews.")
                        return dict(user_reviews=[], user_id=None, scrape_failed=False)

                    mongodb = MongoDBClient()
                    logger.info("Connected to MongoDB for user scraping.")

                    user_found = mongodb.find_user(username) == 1

                    if not user_found:
                        logger.info("User not found in database. Starting scraping process.")
                        user_data = await scraper.get_user(username)
                        if not user_data:
                            logger.warning("No user data found during scraping.")
                            RedisClient().publish_scrape_warning(username, request_run_id)
                            return dict(user_reviews=[], user_id=None, scrape_failed=True)

                        user_id = user_data["user_id"]
                        ratings = await scraper.get_user_ratings(username, user_id, return_unrated=True, pages_limit=50)
                        ratings = [x for x in ratings if x["rating_val"] >= 0]

                        if not ratings:
                            logger.warning(f"Scraping returned 0 reviews for {username}.")
                            RedisClient().publish_scrape_warning(username, request_run_id)
                            return dict(user_reviews=[], user_id=user_id, scrape_failed=True)

                        if not data_opt_out:
                            logger.info("Inserting scraped user data into MongoDB.")
                            mongodb.insert_users([user_data])
                            mongodb.insert_ratings(ratings)
                            logger.info(f"Successfully inserted {len(ratings)} user reviews for {username}.")

                        user_reviews = ratings
                        logger.info(f"Successfully scraped {len(user_reviews)} user reviews for {username}.")
                    else:
                        logger.info("User found in database. Fetching existing data.")
                        user_id = mongodb.get_user_custom_id(username)
                        user_reviews = mongodb.get_reviews_by_user_id(user_id)
                        logger.info(f"Fetched {len(user_reviews)} existing reviews for user {username}.")

                    logger.info("MongoDB operations completed successfully.")
                    return dict(user_reviews=user_reviews, user_id=user_id, scrape_failed=False)

            except Exception as e:
                logger.error(f"Error during user scraping for {username}: {e}", exc_info=True)
                raise

        return asyncio.run(scrape_user_data())

    @task
    def get_user_recommendations(user_reviews: list, user_id: str, type_: str = "new", username: str = "", request_run_id: str = ""):
        logger.info(f"Generating recommendations for user_id={user_id} with type={type_}")
        try:
            engine = RecommendationEngine()
            engine.load_bundle(load_latest_model("/root/letterboxd-movie-rec/prediction/models"))
            logger.info("Pre-trained model loaded successfully.")

            def _weighted_rating(review: dict) -> float:
                rating = float(review.get('rating_val') or 0.0)
                boost = 0.0
                if review.get('is_review'):
                    boost += 0.5 if rating > 5.0 else -0.5
                if review.get('is_liked'):
                    boost += 0.3
                if review.get('is_rewatch'):
                    boost += 0.7
                return max(0.0, min(10.0, rating + boost))

            user_ratings_tuples = [(review['movie_title'], _weighted_rating(review)) for review in user_reviews]

            if type_ == "letterboxd":
                recommendations_df = engine.generate_recommendations(user_ratings_tuples, n=24, hybrid_weight=0.9, user_id=user_id)
            elif type_ == "new":
                recommendations_df = engine.generate_recommendations(user_ratings_tuples, n=200, hybrid_weight=0.7)

            recommendations_list = recommendations_df.to_dict('records')

            mongo = MongoDBClient()
            slugs = [r['movie_title'] for r in recommendations_list]
            movies_data = mongo.read_movies_by_titles(slugs)
            movies_map = {m['movie_title_formatted']: m for m in movies_data}

            for rec in recommendations_list:
                db_movie = movies_map.get(rec['movie_title'], {})
                rec['movie_title_formatted'] = db_movie.get('movie_title_formatted')
                rec['movie_title'] = db_movie.get('movie_title', rec['movie_title'])
                rec['poster_url'] = db_movie.get('poster_url')
                rec['lb_rating'] = db_movie.get('lb_rating')
                rec['genres'] = db_movie.get('genres', [])
                rec['histogram'] = db_movie.get('histogram', {})
                rec['runtime'] = db_movie.get('runtime')

            logger.info(f"Generated and enriched {len(recommendations_list)} recommendations for user_id={user_id}")
            return recommendations_list
        except Exception as e:
            logger.error(f"Error generating recommendations for user_id={user_id}: {e}", exc_info=True)
            RedisClient().publish_recs_error(username, reason="rec_failed", run_id=request_run_id)
            raise

    @task
    def get_user_analytics(user_reviews: list, type_: str):
        logger.info(f"Generating analytics for user, type={type_}")
        try:
            if type_ == "letterboxd" and len(user_reviews) == 0:
                logger.info("No reviews found, skipping analytics generation.")
                return {}
            if type_ == "letterboxd":
                movie_titles = [r['movie_title'] for r in user_reviews]
                user_movies = MongoDBClient().read_movies_by_titles(movie_titles)
                user_analytics = UserAnalytics(reviews=user_reviews, movies=user_movies)
                user_analytics.set_user_history_movies()
                user_analytics.set_user_history_reviews()
                analytics_data = user_analytics.get_basic_metrics()
                logger.info("User analytics generated successfully.")
                advanced_analytics_data = user_analytics.get_advanced_metrics()
                return {**analytics_data, **advanced_analytics_data}
            logger.info("Type not 'letterboxd', skipping analytics generation.")
            return {}
        except Exception as e:
            logger.error(f"Error generating user analytics: {e}", exc_info=True)
            raise

    @task
    def write_to_redis(username: str, rec_run_id: str, user_recommendation: list, user_analytics: dict, scrape_failed: bool = False):
        logger.info(f"Writing recommendations and analytics to Redis for username={username}, rec_run_id={rec_run_id}")
        try:
            redis_client = RedisClient()
            redis_client.publish_recs_analytics(username, rec_run_id, user_recommendation, user_analytics, scrape_failed=scrape_failed)
            redis_client.publish_recently_recommended(user_recommendation)
            logger.info(f"Successfully wrote data to Redis for username={username}, rec_run_id={rec_run_id}")
        except Exception as e:
            logger.error(f"Error writing to Redis for username={username}: {e}", exc_info=True)
            raise

    context_output = setup_context()
    reviews_output = scraping_user_reviews(context_output["username"], context_output["data_opt_out"], request_run_id=context_output["run_id"])
    user_recommendation = get_user_recommendations(
        reviews_output["user_reviews"],
        reviews_output["user_id"],
        context_output["type"],
        context_output["username"],
        request_run_id=context_output["run_id"],
    )
    user_analytics = get_user_analytics(reviews_output["user_reviews"], context_output["type"])
    write_to_redis(context_output["username"], context_output["run_id"], user_recommendation, user_analytics, reviews_output["scrape_failed"])


letterboxd_user_recommendation = letterboxd_user_recommendation()
