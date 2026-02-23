import sys
import asyncio

from messaging.redis_client import RedisClient
from prediction.recommendation_engine import RecommendationEngine
from processing.analytics.user_analytics import UserAnalytics
from processing.utils.utils import load_latest_model

sys.path.insert(0, "/home/ubuntu/app/")

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.models import DagRun
from dotenv import load_dotenv
from app_logger.app_logger import setup_logger

from processing.scraping.user_reviews_scraping import UserReviewsScraping
from database.mongodb_client import MongoDBClient

logger = setup_logger("../logs/rec_dag.log", "UserScrapingDAG")

load_dotenv()

default_args = {
    'owner': 'DijkstraFTW',
    'start_date': datetime(2024, 1, 1),
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'provide_context': True
}


@dag('letterboxd_recommendation_dag', default_args=default_args, schedule=None,
     description='Provides recommendations for a user based on a pre-trained model.')
def letterboxd_user_recommendation():

    @task(multiple_outputs=True, provide_context=True)
    def setup_context(**context):
        logger.info("Setting up context for DAG run.")
        try:
            dag_run = context['dag_run']
            if dag_run and dag_run.conf:
                username = dag_run.conf['username']
                type_ = dag_run.conf['type']
                data_opt_out = dag_run.conf['data_opt_out']
            else:
                username = 'default_username'
                type_ = 'default_type'
                data_opt_out = False

            logger.info(f"Context initialized with username={username}, type={type_}, data_opt_out={data_opt_out}")
            return dict(username=username, type=type_, data_opt_out=data_opt_out)
        except Exception as e:
            logger.error(f"Error in setup_context: {e}", exc_info=True)
            raise

    @task(multiple_outputs=True)
    def scraping_user_reviews(username: str, data_opt_out: bool):
        logger.info(f"Starting scraping_user_reviews for username={username}, data_opt_out={data_opt_out}")
        async def scrape_user_data():
            try:
                async with UserReviewsScraping() as scraper:
                    if username == 'default_username':
                        logger.warning("Default username detected, returning empty user reviews.")
                        return dict(user_reviews=[], user_id=None)

                    mongodb = MongoDBClient()
                    logger.info("Connected to MongoDB for user scraping.")

                    user_found = mongodb.find_user(username) == 1

                    if not user_found:
                        logger.info("User not found in database. Starting scraping process.")
                        user_data = await scraper.get_user(username)
                        if not user_data:
                            logger.warning("No user data found during scraping.")
                            return dict(user_reviews=[], user_id=None)

                        user_id = user_data["user_id"]
                        ratings = await scraper.get_user_ratings(username, user_id, return_unrated=True)
                        ratings = [x for x in ratings if x["rating_val"] >= 0]

                        if not data_opt_out:
                            logger.info("Inserting scraped user data into MongoDB.")
                            mongodb.insert_users([user_data])
                            mongodb.insert_ratings(ratings)

                        user_reviews = ratings
                        logger.info(f"Scraped and inserted {len(user_reviews)} user reviews for {username}.")
                    else:
                        logger.info("User found in database. Fetching existing data.")
                        user_id = mongodb.get_user_custom_id(username)
                        user_reviews = mongodb.get_reviews_by_user_id(user_id)
                        logger.info(f"Fetched {len(user_reviews)} existing reviews for user {username}.")

                    logger.info("MongoDB operations completed successfully.")
                    return dict(user_reviews=user_reviews, user_id=user_id)

            except Exception as e:
                logger.error(f"Error during user scraping for {username}: {e}", exc_info=True)
                raise

        return asyncio.run(scrape_user_data())

    @task
    def load_pre_trained_model():
        logger.info("Loading pre-trained recommendation model.")
        try:
            engine = RecommendationEngine()
            engine.load_bundle(load_latest_model())
            logger.info("Pre-trained model loaded successfully.")
            return engine
        except Exception as e:
            logger.error(f"Error loading pre-trained model: {e}", exc_info=True)
            raise

    @task
    def get_user_recommendations(engine, user_reviews: list, user_id: str, type_: str = "new"):
        logger.info(f"Generating recommendations for user_id={user_id} with type={type_}")
        try:
            user_ratings_tuples = [(review['movie_title'], review['rating_val']) for review in user_reviews]

            if type_ == "letterboxd":
                recommendations_df = engine.generate_recommendations(user_ratings_tuples, n=24, hybrid_weight=0.9)
            elif type_ == "new":
                recommendations_df = engine.generate_recommendations(user_ratings_tuples, n=48, hybrid_weight=0.7)
            else:
                recommendations_df = engine.generate_recommendations(user_ratings_tuples, n=24, hybrid_weight=0.7)

            recommendations_list = recommendations_df.to_dict('records')
            logger.info(f"Generated {len(recommendations_list)} recommendations for user_id={user_id}")
            return recommendations_list
        except Exception as e:
            logger.error(f"Error generating recommendations for user_id={user_id}: {e}", exc_info=True)
            raise

    @task
    def get_user_analytics(user_reviews: list, type_: str):
        logger.info(f"Generating analytics for user, type={type_}")
        try:
            if type_ == "letterboxd":
                user_analytics = UserAnalytics("", user_reviews, [])
                user_analytics.set_user_history_movies()
                user_analytics.set_user_history_reviews()
                analytics_data = user_analytics.get_basic_metrics()
                logger.info("User analytics generated successfully.")
                return analytics_data
            logger.info("Type not 'letterboxd', skipping analytics generation.")
            return {}
        except Exception as e:
            logger.error(f"Error generating user analytics: {e}", exc_info=True)
            raise

    @task
    def write_to_redis(username: str, user_recommendation: list, user_analytics: dict):
        logger.info(f"Writing recommendations and analytics to Redis for username={username}")
        try:
            redis_client = RedisClient()
            redis_client.publish_recs_analytics(username, user_recommendation, user_analytics)
            logger.info(f"Successfully wrote data to Redis for username={username}")
        except Exception as e:
            logger.error(f"Error writing to Redis for username={username}: {e}", exc_info=True)
            raise

    context_output = setup_context()
    reviews_output = scraping_user_reviews(context_output["username"], context_output["data_opt_out"])
    pre_trained_engine = load_pre_trained_model()
    user_recommendation = get_user_recommendations(
        pre_trained_engine, 
        reviews_output["user_reviews"], 
        reviews_output["user_id"],
        context_output["type"]
    )
    user_analytics = get_user_analytics(reviews_output["user_reviews"], context_output["type"])
    write_to_redis(context_output["username"], user_recommendation, user_analytics)


letterboxd_user_recommendation = letterboxd_user_recommendation()
