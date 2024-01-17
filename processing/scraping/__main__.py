from dotenv import load_dotenv

from processing.database.database import MongoDBClient
from processing.scraping.scraping_user_reviews import ScrapingUserReviews

if __name__ == "__main__":

    load_dotenv()

    # Reviews & Users Scraping

    scraping_user_reviews = ScrapingUserReviews()
    top_users = scraping_user_reviews.get_popular_users()

    mongodb = MongoDBClient()
    client = mongodb.open_conn_to_db()

    mongodb.insert_users(client, top_users)

    for user in top_users:
        mongodb.insert_ratings(client, scraping_user_reviews.get_user_ratings(user['username'], user['user_id']))

    mongodb.close_conn_to_db(client)

    # Movies Scraping

    scraping_user_reviews = ScrapingUserReviews()
    top_users = scraping_user_reviews.get_popular_users()

    mongodb = MongoDBClient()
    client = mongodb.open_conn_to_db()

    mongodb.insert_users(client, top_users)

    for user in top_users:
        mongodb.insert_ratings(client, scraping_user_reviews.get_user_ratings(user['username'], user['user_id']))

    mongodb.close_conn_to_db(client)


