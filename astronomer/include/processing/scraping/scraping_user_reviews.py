import uuid

import requests
from bs4 import BeautifulSoup

class ScrapingUserReviews:

    def __init__(self):
        self.popular_users_url = "https://letterboxd.com/members/popular/this/week/page/{}/"
        self.users_page_number_url = "https://letterboxd.com/{}/films/by/date"
        self.users_pages_url = "https://letterboxd.com/{}/films/by/date/page/{}/"

    def get_popular_users(self):

        total_pages = 50
        users = []

        for page in range(total_pages):

            r = requests.get(self.popular_users_url.format(page))
            soup = BeautifulSoup(r.text, "html.parser")
            table = soup.find("table", attrs={"class": "person-table"})
            rows = table.findAll("td", attrs={"class": "table-person"})

            for row in rows:
                user_id = str(uuid.uuid4())
                link = row.find("a")["href"]
                username = link.strip('/')
                display_name = row.find("a", attrs={"class": "name"}).text.strip()
                num_reviews = int(row.find("small").find("a").text.replace('\xa0', ' ').split()[0].replace(',', ''))
                user = {"user_id": user_id, "username": username, "display_name": display_name, "num_reviews": num_reviews}
                users.append(user)

        return users

    def generate_ratings_operations(self, response, user_id, return_unrated=False):

        # Parse ratings page response for each rating/review, use lxml parser for speed
        reviews = response.findAll("li", attrs={"class": "poster-container"})

        # Create empty array to store list of bulk operations or rating objects
        ratings = []

        # For each review, parse data from scraped page and append an UpdateOne operation for bulk execution or a rating object
        for review in reviews:
            movie_title = review.find("div", attrs={"class", "film-poster"})["data-target-link"].split("/")[-2]

            rating = review.find("span", attrs={"class": "rating"})
            if not rating:
                if return_unrated == False:
                    continue
                else:
                    rating_val = -1
            else:
                rating_class = rating["class"][-1]
                rating_val = int(rating_class.split("-")[-1])

            rating_object = {"movie_title": movie_title, "rating_val": rating_val, "user_id": user_id}
            ratings.append(rating_object)

            # We're going to eventually send a bunch of upsert operations for movies with just IDs
            # For movies already in the database, this won't impact anything
            # But this will allow us to easily figure out which movies we need to scraped data on later,
            # Rather than scraping data for hundreds of thousands of movies everytime there's a broader data update

        return ratings

    def get_user_ratings(self, username, user_id, store_in_db=True, num_pages=4, return_unrated=False):
        scrape_responses = []

        for i in range(num_pages):
            task = requests.get(self.users_pages_url.format(username, i + 1), {"username": username})
            soup = BeautifulSoup(task.text, features="html.parser")
            scrape_responses.append(soup)

        # Process each ratings page response, converting it into bulk upsert operations or output dicts
        ratings = []
        for response in scrape_responses:
            task = self.generate_ratings_operations(response, user_id, return_unrated=return_unrated)
            ratings += task

        return ratings

    def get_page_count(self, username):

        response = requests.get(self.users_page_number_url.format(username))
        soup = BeautifulSoup(response.text, features="html.parser")
        body = soup.find("body")

        if "error" in body["class"]:
            return -1, None

        try:
            page_link = soup.findAll("li", attrs={"class", "paginate-page"})[-1]
            num_pages = int(page_link.find("a").text.replace(",", ""))
            display_name = (body.find("section", attrs={"class": "profile-header"}).find("h1", attrs={
                "class": "title-3"}).text.strip())
        except IndexError:
            num_pages = 1
            display_name = None

        return num_pages, display_name

    def get_user_data(self, username, data_opt_in=False):
        num_pages, display_name = self.get_page_count(username)

        if num_pages == -1:
            return [], "user_not_found"

        result = self.get_user_ratings(username, store_in_db=False, num_pages=num_pages, return_unrated=True)
        user_ratings = [x for x in result[0] if x["rating_val"] >= 0]

        return user_ratings


if __name__ == "__main__":

    # Reviews & Users Scraping

    scraping_user_reviews = ScrapingUserReviews()
    top_users = scraping_user_reviews.get_popular_users()[0:2]

    for user in top_users:
        print(scraping_user_reviews.get_user_ratings(user['username'], user['user_id']))
