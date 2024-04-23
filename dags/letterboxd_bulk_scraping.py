import sys

sys.path.insert(0, "/home/ubuntu/app/")

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from dotenv import load_dotenv

from database.MongoDBClient import MongoDBClient
from processing.scraping.ScrapingMovies import ScrapingMovies
from processing.scraping.ScrapingUserReviews import ScrapingUserReviews

load_dotenv()

default_args = {
    'owner': 'DijkstraFTW',
    'start_date': datetime(2024, 1, 1),
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}


@dag('letterboxd_bulk_scraping_dag', default_args=default_args, schedule='0 3 1 * *', catchup=False,
     description='Scraping Letterboxd data and storing it in MongoDB')
def letterboxd_bulk_scraping():
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
        existing_movies_set = set(mongodb.read_all_movies_title_formatted(client))
        updated_movies_set = set([item["movie_title"] for item in movies_list])
        movies_to_scrap_list = list(existing_movies_set.difference(updated_movies_set))

        scraping_movies = ScrapingMovies(movies_to_scrap_list)
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

    scrape_users_reviews_task = scraping_users_reviews()
    scrape_movies_shows_task = scraping_movies_shows()

    scrape_users_reviews_task >> scrape_movies_shows_task


letterboxd_bulk_scraping = letterboxd_bulk_scraping()
