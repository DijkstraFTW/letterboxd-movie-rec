from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from dotenv import load_dotenv

from include.database.database import *
from include.processing.scraping.scraping_movies import *
from include.processing.scraping.scraping_user_reviews import *

load_dotenv()

default_args = {'owner': 'airflow', 'start_date': datetime.datetime(2024, 1, 1), 'depends_on_past': False, 'retries': 1, 'retry_delay': timedelta(minutes=5)}

dag = DAG(
    'letterboxd_scrapping_dag',
    default_args=default_args,
    schedule_interval='0 3 1 * *'
)

# Scraping Users and Reviews
def scraping_users_reviews():
    scraping_user_reviews = ScrapingUserReviews()
    top_users = scraping_user_reviews.get_popular_users()

    mongodb = MongoDBClient()
    client = mongodb.open_conn_to_db()

    mongodb.insert_users(client, top_users)

    for user in top_users:
        mongodb.insert_ratings(client, scraping_user_reviews.get_user_ratings(user['username'], user['user_id']))

    mongodb.close_conn_to_db(client)


task_scraping_users_reviews = PythonOperator(task_id='scraping_users_reviews', python_callable=scraping_users_reviews,
    dag=dag, )


# Scraping Movies and Shows
def scraping_movies_shows():
    mongodb = MongoDBClient()
    client = mongodb.open_conn_to_db()

    movies_list = mongodb.read_all_rated_movies(client)

    scraping_movies = ScrapingMovies(movies_list)
    letterboxd_movies = scraping_movies.get_movies()

    movies_data = []

    for movie in letterboxd_movies:
        posters = scraping_movies.get_movie_posters(movie)
        themoviedb = scraping_movies.get_rich_data(movie, movie["type"])
        combined_movie_item = {**movie, **posters, **themoviedb}
        if (combined_movie_item["type"] != "none"):
            movies_data.append(combined_movie_item)

    mongodb.insert_movies(client, movies_data)
    mongodb.close_conn_to_db(client)


task_scraping_movies_shows = PythonOperator(task_id='scraping_movies_shows', python_callable=scraping_movies_shows,
    dag=dag)

# Task dependencies
task_scraping_users_reviews >> task_scraping_movies_shows
