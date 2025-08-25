import sys
import uuid
import asyncio

sys.path.insert(0, "/home/ubuntu/app/")

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.models import DagRun
from dotenv import load_dotenv

from database.MongoDBClient import MongoDBClient
from messaging.RedisClient import RedisClient
from prediction.RecommendationEngine import RecommendationEngine
from processing.analytics.UserAnalytics import UserAnalytics
from processing.utils import load_latest_model

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
        dag_run = context['dag_run']
        if dag_run and dag_run.conf:
            username = dag_run.conf['username']
            type = dag_run.conf['type']
            data_opt_out = dag_run.conf['data_opt_out']
        else:
            username = 'default_username'
            type = 'default_type'
            data_opt_out = True

        return dict(username=username, type=type, data_opt_out=data_opt_out)

    @task(multiple_outputs=True)
    def scraping_user_reviews(username: str, data_opt_out: bool):
        async def scrape_user_data():
            async with UserReviewsScraping() as scraper:
                mongodb = MongoDBClient()
                client = mongodb.open_conn_to_db()
                user_found = mongodb.find_user(client, username) == 1

                if not user_found:
                    print("User not found in database, scraping data...")
                    user_data = await scraper.get_user(username)
                    if not user_data:
                        return dict(user_reviews=[], user_id=None)
                    
                    user_id = user_data["user_id"]
                    ratings = await scraper.get_user_ratings(username, user_id, return_unrated=True)
                    ratings = [x for x in ratings if x["rating_val"] >= 0]

                    if not data_opt_out:
                        print("Inserting user data into database...")
                        mongodb.insert_users(client, user_data)
                        mongodb.insert_ratings(client, ratings)

                    user_reviews = ratings

                else:
                    print("User found in database, fetching data...")
                    user_id = mongodb.get_user_custom_id(client, username)
                    user_reviews = mongodb.get_reviews_by_user_id(client, user_id)

                mongodb.close_conn_to_db(client)
                return dict(user_reviews=user_reviews, user_id=user_id)

        return asyncio.run(scrape_user_data())

    @task
    def load_pre_trained_model():
        """
        Task to load the pre-trained model bundle into memory.
        """

        print("Loading pre-trained recommendation model...")
        engine = RecommendationEngine()
        engine.load_bundle(load_latest_model())
        return engine

    @task
    def get_user_recommendations(engine, user_reviews: list, user_id: str, type: str = "new"):
        """
        Uses the pre-trained model to generate recommendations for the new user.
        """
        print(f"Generating recommendations for user {user_id}...")
        
        user_ratings_tuples = [(review['movie_title'], review['rating_val']) for review in user_reviews]
        
        
        if type == "letterboxd":
            recommendations_df = engine.generate_recommendations(user_ratings_tuples, n=20, hybrid_weight=0.9)
        elif type == "new":
            recommendations_df = engine.generate_recommendations(user_ratings_tuples, n=40, hybrid_weight=0.7)
        else:
            recommendations_df = engine.generate_recommendations(user_ratings_tuples, n=20, hybrid_weight=0.7)
        
        recommendations_list = recommendations_df.to_dict('records')
        return recommendations_list

    @task
    def get_user_analytics(user_reviews: list, type: str):
        if type == "letterboxd":
            user_analytics = UserAnalytics("", user_reviews, [])
            user_analytics.set_user_history_movies()
            user_analytics.set_user_history_reviews()
            user_analytics_data = user_analytics.get_basic_metrics()
            return user_analytics_data
        return {}

    @task
    def write_to_redis(username: str, user_recommendation: list, user_analytics: dict):
        redis_client = RedisClient()
        redis_client.publish_recs_analytics(username, user_recommendation, user_analytics)

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

