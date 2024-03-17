import uuid

import requests
from bs4 import BeautifulSoup


class ScrapingUserReviews:

    def __init__(self):
        self.popular_users_url = "https://letterboxd.com/members/popular/this/week/page/{}/"
        self.user_page_url = "https://letterboxd.com/{}/"
        self.users_diary_page_number_url = "https://letterboxd.com/mistat/films/diary/by/added/"
        self.users_diary_pages_url = "https://letterboxd.com/mistat/films/diary/by/added/page/{}/"
        self.users_grid_page_number_url = "https://letterboxd.com/{}/films/by/date/"
        self.users_grid_pages_url = "https://letterboxd.com/{}/films/by/date/page/{}/"
        self.num_top_users_pages = 100
        self.num_user_ratings_pages = 3

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

    def get_user(self, username):

        r = requests.get(self.user_page_url.format(username))
        page = BeautifulSoup(r.text, "html.parser")

        user_id = str(uuid.uuid4())
        display_name = page.find("span", attrs={"class": "displayname tooltip"}).text.strip()
        num_reviews = page.find("h4", attrs={"class": "profile-statistic statistic"}).find("span", attrs={"class": "value"}).text
        user = {"user_id": user_id, "username": username, "display_name": display_name,
                "num_reviews": num_reviews}

        return user

    def get_diary_reviews_page_count(self, username):

        response = requests.get(self.users_diary_page_number_url.format(username))
        soup = BeautifulSoup(response.text, features="html.parser")
        body = soup.find("body")

        if "error" in body["class"]:
            return -1, None

        try:
            page_link = soup.findAll("li", attrs={"class", "paginate-page"})[-1]
            num_pages = int(page_link.find("a").text.replace(",", ""))
        except IndexError:
            num_pages = self.num_user_ratings_pages

        return num_pages

    def get_grid_reviews_page_count(self, username):

        response = requests.get(self.users_grid_page_number_url.format(username))
        soup = BeautifulSoup(response.text, features="html.parser")
        body = soup.find("body")

        if "error" in body["class"]:
            return -1, None

        try:
            page_link = soup.findAll("li", attrs={"class", "paginate-page"})[-1]
            num_pages = int(page_link.find("a").text.replace(",", ""))
        except IndexError:
            num_pages = self.num_user_ratings_pages

        return num_pages

    def get_ratings_data(self, response, user_id, return_unrated=False):

        ratings = []
        reviews = response.select('tr[class*="diary-entry-row viewing-poster-container"]')

        for review in reviews:

            date_element = review.find('td', class_='td-day diary-day center').find("a")["href"].split("/")
            date = date_element[-4] + "-" + date_element[-5] + "-" + date_element[-6]

            movie_title = review.find("div", attrs={"class", "film-poster"})["data-film-slug"]

            try:
                rating_val = review.find('td', class_='td-rating rating-green').find('span')['class'][-1].split("rated-")[-1]
            except:
                rating_val = 0

            try :
                rewatch_element = review.find('td', class_='td-rewatch center').find("span")
                is_rewatch = rewatch_element.has_attr('class') and 'icon-rewatch' in rewatch_element['class']

            except:
                is_rewatch = False

            try:
                review_element = review.find('td', class_='td-review center').find("a")
                is_reviewed = True

            except:
                is_reviewed = False

            rating_object = {"movie_title": movie_title, "rating_date": date, "rating_val": rating_val, "user_id": user_id, "is_rewatch" : is_rewatch, "is_review" : is_reviewed}
            ratings.append(rating_object)

        return ratings

    def get_ratings_data_likes(self, username):

        likes = []

        for i in range(self.num_user_ratings_pages):

            page = requests.get(self.users_grid_pages_url.format(username, i + 1), {"username": username})
            response = BeautifulSoup(page.text, features="html.parser")

            reviews = response.findAll("li", attrs={"class": "poster-container"})
            for review in reviews:
                try:
                    like_element = review.find('p', class_='poster-viewingdata').find("span", class_='like liked-micro has-icon icon-liked icon-16').find('span')
                    is_liked = True

                except:
                    is_liked = False

                likes.append({"is_liked": is_liked})

        return likes

    def get_user_ratings(self, username, user_id, store_in_db=True, return_unrated=False):

        ratings = []
        all_likes = []
        combined_rating = []
        nb_diary_pages = self.get_diary_reviews_page_count(username)
        nb_grid_pages = self.get_grid_reviews_page_count(username)

        for i in range(nb_diary_pages):
            page = requests.get(self.users_diary_pages_url.format(username, i + 1), {"username": username})
            response = BeautifulSoup(page.text, features="html.parser")
            rating = self.get_ratings_data(response, user_id, return_unrated=return_unrated)
            ratings.extend(rating)

        for i in range(nb_grid_pages):
            likes = self.get_ratings_data_likes(username)
            all_likes.extend(likes)

        for i in range(min(len(ratings), len(all_likes))):
            combined_rating.append({**ratings[i], **all_likes[i]})

        return combined_rating

    def get_all_ratings(self, username, data_opt_out=False):

        store_in_db = True
        num_pages = self.get_diary_reviews_page_count(username)

        if num_pages == -1:
            return [], "user_not_found"

        if data_opt_out:
            store_in_db = False

        result = self.get_user_ratings(username, store_in_db, return_unrated=True)
        user_ratings = [x for x in result[0] if x["rating_val"] >= 0]

        return user_ratings
