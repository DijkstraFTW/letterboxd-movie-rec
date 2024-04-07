from datetime import timedelta

from airflow import DAG
from airflow.operators.python_operator import PythonOperator

from database.MongoDBClient import *
from processing.scraping.ScrapingMovies import *
from processing.scraping.ScrapingUserReviews import *

load_dotenv()

default_args = {'owner': 'airflow', 'start_date': datetime.datetime(2024, 1, 1), 'depends_on_past': False, 'retries': 1,
                'retry_delay': timedelta(minutes=5)}

dag = DAG(
    'letterboxd_scrapping_dag',
    default_args=default_args,
    schedule_interval='0 3 1 * *'
)

# TODO decompose each dag extract - transf - loading

# Scraping the user's Reviews

# request args
username = "cuqui"
data_opt_out = False
user_reviews = []


def scraping_user_reviews():

    # check if user exists already
    mongodb = MongoDBClient()
    client = mongodb.open_conn_to_db()
    user_found = mongodb.find_user(client, username)

    # user doesn't exist
    if user_found <= 0:
        scraping_user_reviews = ScrapingUserReviews()

        user_id = str(uuid.uuid4())
        user = scraping_user_reviews.get_user(username)
        ratings = scraping_user_reviews.get_user_ratings(username, user_id, data_opt_out)

        if not data_opt_out:
            mongodb.insert_users(client, user)
            mongodb.insert_ratings(client, ratings)

        return user, ratings

    mongodb.close_conn_to_db(client)
    return None


task_scraping_user_reviews = PythonOperator(task_id='scraping_user_reviews', python_callable=scraping_user_reviews,
                                             dag=dag, )


# Scraping Movies and Shows
def scraping_user_movies_shows():

    mongodb = MongoDBClient()
    client = mongodb.open_conn_to_db()

    movies_scraped_set = set(mongodb.read_all_movies(client))
    movies_list_set = set([item["movie_title"] for item in user_reviews])

    common_movies_list = list(movies_scraped_set.intersection(movies_list_set))

    scraping_movies = ScrapingMovies(common_movies_list)
    letterboxd_movies = scraping_movies.get_rated_movies()

    for movie in letterboxd_movies:
        posters = scraping_movies.get_movie_posters(movie)
        themes = scraping_movies.get_movie_themes(movie)
        nanogenres = scraping_movies.get_movie_nanogenres(movie)
        themoviedb = scraping_movies.get_themoviedb_data(movie, movie["type"])
        combined_movie_item = {**movie, **posters, **themes, **nanogenres, **themoviedb}
        if combined_movie_item["type"] != "none":
            mongodb.insert_movies(client, combined_movie_item)

    mongodb.close_conn_to_db(client)


task_scraping_user_movies_shows = PythonOperator(task_id='scraping_movies_shows', python_callable=scraping_user_movies_shows,
                                            dag=dag)

# Task dependencies
task_scraping_user_reviews >> task_scraping_user_movies_shows
