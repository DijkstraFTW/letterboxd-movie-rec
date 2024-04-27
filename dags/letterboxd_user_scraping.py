import sys
import uuid

from airflow.models import DagRun

sys.path.insert(0, "/home/ubuntu/app/")

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from dotenv import load_dotenv

from database.MongoDBClient import MongoDBClient
from messaging.RedisClient import RedisClient
from prediction.CollaborativeFilteringModel import CollaborativeFilteringModel
from processing.analytics.UserAnalytics import UserAnalytics
from processing.scraping.ScrapingMovies import ScrapingMovies
from processing.scraping.ScrapingUserReviews import ScrapingUserReviews

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
     description='Scrapes user reviews from Letterboxd and provides recommendations based on '
                 'stored users watch history.')
def letterboxd_user_recommendation():
    # Setting up the context
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

    # Scraping the user's reviews
    @task(multiple_outputs=True)
    def scraping_user_reviews(username: str, data_opt_out: bool):

        # check if user exists already
        mongodb = MongoDBClient()
        client = mongodb.open_conn_to_db()
        user_found = mongodb.find_user(client, username) == 1

        # user doesn't exist
        if not user_found:
            scraping_user_reviews = ScrapingUserReviews()
            user_id = str(uuid.uuid4())
            ratings = scraping_user_reviews.get_user_ratings(username, user_id, data_opt_out)

            if not data_opt_out:
                user = scraping_user_reviews.get_user(username)
                mongodb.insert_users(client, user)
                mongodb.insert_ratings(client, ratings)

            user_reviews = ratings

        # user exists
        else:
            user_id = mongodb.get_user_custom_id(client, username)
            user_reviews = mongodb.get_reviews_by_user_id(client, user_id)

        mongodb.close_conn_to_db(client)
        return dict(user_reviews=user_reviews, user_id=user_id)

    # Scraping the user's movies and shows
    @task
    def scraping_user_movies_shows(user_reviews: list):

        mongodb = MongoDBClient()
        client = mongodb.open_conn_to_db()

        user_movies = [item["movie_title"] for item in user_reviews]
        movies_scraped_set = set(mongodb.read_all_movies_title_formatted(client))
        user_movies_set = set(user_movies)
        new_movies_list = list(user_movies_set.difference(movies_scraped_set))

        print("Adding {} movies to database !".format(len(new_movies_list)))

        if len(new_movies_list) != 0:

            scraping_movies = ScrapingMovies(new_movies_list)
            new_movies = scraping_movies.get_rated_movies()

            for movie in new_movies:
                posters = scraping_movies.get_movie_posters(movie)
                themes = scraping_movies.get_movie_themes(movie)
                nanogenres = scraping_movies.get_movie_nanogenres(movie)
                themoviedb = scraping_movies.get_themoviedb_data(movie, movie["type"])
                combined_movie_item = {**movie, **posters, **themes, **nanogenres, **themoviedb}
                if combined_movie_item["type"] != "none":
                    mongodb.insert_movies(client, combined_movie_item)

        mongodb.close_conn_to_db(client)
        return user_movies

    # Getting user recommendations
    @task
    def get_user_recommendations(user_reviews: list, user_id: str, type: str = "new"):
        user_recs = []

        mongodb = MongoDBClient()
        client = mongodb.open_conn_to_db()
        reviews = mongodb.read_all_ratings(client)
        movies = mongodb.read_all_movies_title_formatted(client)
        reviews = user_reviews + reviews

        collaborative_filtering = CollaborativeFilteringModel(reviews, movies)
        trainset, testset = collaborative_filtering.prepare_dataset()
        collaborative_filtering.train_model(trainset, testset)

        if type == "letterboxd":
            user_recs = collaborative_filtering.generate_recommendation(user_id, 20)
        elif type == "new":
            user_recs = collaborative_filtering.get_weighted_recommendations(40)

        return user_recs

    # Getting user analytics
    @task
    def get_user_analytics(username: str, user_reviews: list, user_movies: list, type: str):

        if type == "letterboxd":
            user_analytics = UserAnalytics("/users_cache/" + str(username), user_reviews, user_movies)
            user_analytics.set_user_history_movies()
            user_analytics.set_user_history_reviews()
            user_analytics_data = user_analytics.get_basic_metrics()
            return user_analytics_data
        return {}

    # Writing to Redis
    @task
    def write_to_redis(username: str, user_recommendation: list, user_analytics: dict):
        redis_client = RedisClient()
        redis_client.publish_recs_analytics(username, user_recommendation, user_analytics)

    context_output = setup_context()
    reviews_output = scraping_user_reviews(context_output["username"], context_output["data_opt_out"])
    user_movies_shows = scraping_user_movies_shows(reviews_output["user_reviews"])
    user_recommendation = get_user_recommendations(reviews_output["user_reviews"], reviews_output["user_id"],
                                                   context_output["type"])
    user_analytics = get_user_analytics(context_output["username"], reviews_output["user_reviews"],
                                        user_movies_shows, context_output["type"])
    write_to_redis(context_output["username"], user_recommendation, user_analytics)


letterboxd_user_recommendation = letterboxd_user_recommendation()
