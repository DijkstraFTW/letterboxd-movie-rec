from dotenv import load_dotenv

from astronomer.include.database.MongoDBClient import MongoDBClient
from processing.scraping.ScrapingMovies import ScrapingMovies
from astronomer.include.processing.scraping.ScrapingUserReviews import ScrapingUserReviews

if __name__ == "__main__":

    load_dotenv()

    # Reviews & Users Scraping

    scraping_user_reviews = ScrapingUserReviews()
    top_users = scraping_user_reviews.get_popular_users()[0:2]

    mongodb = MongoDBClient()
    client = mongodb.open_conn_to_db()

    mongodb.insert_users(client, top_users)

    for user in top_users:
        mongodb.insert_ratings(client, scraping_user_reviews.get_user_ratings(user['username'], user['user_id']))

    mongodb.close_conn_to_db(client)

    # Movies & Shows Scraping

    mongodb = MongoDBClient()
    client = mongodb.open_conn_to_db()

    movies_list = mongodb.read_all_rated_movies(client)

    scraping_movies = ScrapingMovies(movies_list)
    letterboxd_movies = scraping_movies.get_movies()[0:2]

    movies_data = []

    for movie in letterboxd_movies:
        posters = scraping_movies.get_movie_posters(movie)
        themoviedb = scraping_movies.get_rich_data(movie, movie["type"])
        combined_movie_item = {**movie, **posters, **themoviedb}
        movies_data.append(combined_movie_item)

    mongodb.insert_movies(client, movies_data)
    mongodb.close_conn_to_db(client)
