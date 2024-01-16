from processing.scraping.scraping_user_reviews import ScrapingUserReviews

if __name__ == "__main__":

    scraping_user_reviews = ScrapingUserReviews()
    top_users = scraping_user_reviews.get_popular_users()

    print(top_users[0:4])

    user_ratings = []

    for user in top_users[0:2] :
        user_ratings.append(scraping_user_reviews.get_user_ratings(user['username'], user['user_id']))

    print(user_ratings)

    # TODO persist user and user ratings in users and ratings collections


