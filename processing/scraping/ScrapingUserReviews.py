import uuid

import requests
from bs4 import BeautifulSoup


class ScrapingUserReviews:

    def __init__(self):
        self.popular_users_url = "https://letterboxd.com/members/popular/this/week/page/{}/"
        self.users_page_number_url = "https://letterboxd.com/{}/films/by/date"
        self.users_pages_url = "https://letterboxd.com/{}/films/by/date/page/{}/"
        self.num_top_users_pages = 100
        self.num_user_ratings_pages = 10

    def get_popular_users(self):
        users = []

        for page in range(self.num_top_users_pages):

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
                user = {"user_id": user_id, "username": username, "display_name": display_name,
                        "num_reviews": num_reviews}
                users.append(user)

        return users

    def get_reviews_page_count(self, username):

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

    def get_rating_data(self, response, user_id, return_unrated=False):

        ratings = []

        reviews = response.findAll("li", attrs={"class": "poster-container"})

        for review in reviews:
            movie_title = review.find("div", attrs={"class", "film-poster"})["data-film-slug"]

            rating = review.find("span", attrs={"class": "rating"})
            if not rating:
                if not return_unrated:
                    continue
                else:
                    rating_val = -1
            else:
                rating_class = rating["class"][-1]
                rating_val = int(rating_class.split("-")[-1])

            rating_object = {"movie_title": movie_title, "rating_val": rating_val, "user_id": user_id}
            ratings.append(rating_object)

        return ratings

    def get_user_ratings(self, username, user_id, store_in_db=True, return_unrated=False):

        ratings = []

        for i in range(self.num_user_ratings_pages):
            page = requests.get(self.users_pages_url.format(username, i + 1), {"username": username})
            response = BeautifulSoup(page.text, features="html.parser")
            rating = self.get_rating_data(response, user_id, return_unrated=return_unrated)
            ratings.append(rating)

        return ratings

    def get_all_ratings(self, username, data_opt_out=False):

        store_in_db = True
        num_pages, display_name = self.get_reviews_page_count(username)

        if num_pages == -1:
            return [], "user_not_found"

        if data_opt_out:
            store_in_db = False

        result = self.get_user_ratings(username, store_in_db, return_unrated=True)
        user_ratings = [x for x in result[0] if x["rating_val"] >= 0]

        return user_ratings
