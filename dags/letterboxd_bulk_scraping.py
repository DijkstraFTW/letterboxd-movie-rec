from datetime import timedelta

from airflow.decorators import dag, task
from dotenv import load_dotenv

from database.MongoDBClient import *
from processing.scraping.ScrapingMovies import *
from processing.scraping.ScrapingUserReviews import *

load_dotenv()

default_args = {'owner': 'DijkstraFTW', 'start_date': datetime.datetime(2024, 1, 1), 'depends_on_past': False,
                'retries': 1, 'retry_delay': timedelta(minutes=5)}


@dag('letterboxd_scraping_dag', default_args=default_args, schedule='0 3 1 * *', catchup=False,
     description='Scraping Letterboxd data and storing it in MongoDB')
def letterboxd_scraping_dag():
    # Scraping Users and Reviews
    @task
    def scraping_users_reviews():
        scraping_user_reviews = ScrapingUserReviews()
        top_users = scraping_user_reviews.get_popular_users()

        mongodb = MongoDBClient()
        client = mongodb.open_conn_to_db()

        mongodb.insert_users(client, top_users)

        for user in top_users:
            mongodb.insert_ratings(client, scraping_user_reviews.get_user_ratings(user['username'], user['user_id']))

        mongodb.close_conn_to_db(client)

    # Scraping Movies and Shows
    @task
    def scraping_movies_shows():
        mongodb = MongoDBClient()
        client = mongodb.open_conn_to_db()

        movies_list = mongodb.read_all_rated_movies(client)

        scraping_movies = ScrapingMovies(movies_list)
        letterboxd_movies = scraping_movies.get_rated_movies()

        for movie in letterboxd_movies:
            posters = scraping_movies.get_movie_posters(movie)
            themoviedb = scraping_movies.get_themoviedb_data(movie, movie["type"])
            themes = scraping_movies.get_movies_themes(movie)
            nanogenres = scraping_movies.get_movies_nanogenres(movie)
            combined_movie_item = {**movie, **posters, **themoviedb, **themes, **nanogenres}
            if combined_movie_item["type"] != "none":
                mongodb.insert_movies(client, combined_movie_item)

        mongodb.close_conn_to_db(client)

    scraping_users_reviews()
    scraping_movies_shows()


letterboxd_scraping = letterboxd_scraping_dag()
