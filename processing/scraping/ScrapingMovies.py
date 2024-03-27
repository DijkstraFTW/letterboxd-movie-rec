import datetime
import os
import re

import requests
from bs4 import BeautifulSoup


def val2stars(index):
    return f"{index * 2}"


class ScrapingMovies:

    def __init__(self, movies_list):
        self.movies_url = "https://letterboxd.com/film/{}/"
        self.posters_url = "https://letterboxd.com/ajax/poster/film/{}/hero/230x345"
        self.themoviedb_url = "https://api.themoviedb.org/3/{}/{}"
        self.themoviedb_key = os.getenv("THEMOVIEDB_KEY")
        self.empty_image_url_prefix = "https://s.ltrbxd.com/static/img/empty-poster"
        self.movies_themes_url = "https://letterboxd.com/film/{}/themes/"
        self.movies_nanogenres_url = "https://letterboxd.com/film/{}/nanogenres/"
        self.movie_reviews_url = "https://letterboxd.com/film/{}/reviews/by/added-earliest/page/{}/"
        self.rating_histograms_url = "https://letterboxd.com/csi/film/{}/rating-histogram/"
        self.movies_list = movies_list

    def get_letterboxd_movies(self, url, movie_title_format):

        response = requests.get(url)
        soup = BeautifulSoup(response.text, features="html.parser")
        movie_header = soup.find('section', attrs={'id': 'featured-film-header'})

        try:
            movie_title = movie_header.find('h1').text
        except AttributeError:
            movie_title = ''

        try:
            year = int(movie_header.find('small', attrs={'class': 'number'}).find('a').text)
        except AttributeError:
            year = None

        soup.find("span", attrs={"class": "rating"})

        try:
            imdb_link = soup.find("a", attrs={"data-track-action": "IMDb"})['href']
            imdb_id = imdb_link.split('/title')[1].strip('/').split('/')[0]
        except:
            imdb_link = ""
            imdb_id = ""

        try:
            themoviedb_link = soup.find("a", attrs={"data-track-action": "TMDb"})['href']
            themoviedb_id = themoviedb_link.split('/movie')[1].strip('/').split('/')[0]
            type_ = "movie"
        except:
            try:
                themoviedb_link = soup.find("a", attrs={"data-track-action": "TMDb"})['href']
                themoviedb_id = themoviedb_link.split('/tv')[1].strip('/').split('/')[0]
                type_ = "tv"
            except:
                themoviedb_link = ""
                themoviedb_id = ""
                type_ = "none"

        response = requests.get("https://letterboxd.com/csi/film/{}/rating-histogram/".format(movie_title_format))
        hist_soup = BeautifulSoup(response.text, features="html.parser")
        ratings = hist_soup.find_all("li", {'class': 'rating-histogram-bar'})

        tot_ratings = 0
        film_hist = {}

        try:
            fans = hist_soup.find('a', {'class': 'all-link more-link'}).text
            fans = re.findall(r'\d+.\d+K?|\d+K?', fans)[0]
            if "." and "K" in fans:
                fans = int(float(fans[:-1]) * 1000)
            elif "K" in fans:
                fans = int(fans[-1]) * 1000
            else:
                fans = int(fans)
        except:
            fans = 0

        try:
            lb_rating = hist_soup.find('span', {'class': 'average-rating'}).find('a').text
        except:
            lb_rating = 0

        try:
            for i, r in enumerate(ratings):
                string = r.text.strip(" ")
                stars = val2stars((i + 1) / 2)
                if string == "":
                    film_hist[f"{stars}"] = 0
                else:
                    Nratings = re.findall(r'\d+', string)[:-1]
                    Nratings = int(''.join(Nratings))
                    film_hist[f"{stars}"] = Nratings
                    tot_ratings += Nratings
        except:
            tot_ratings = ""

        film_hist["fans"] = fans
        film_hist["lb_rating"] = lb_rating
        film_hist["total"] = tot_ratings

        movie_object = {"movie_title_formatted": movie_title_format, "movie_title": movie_title, "type": type_,
                        "year_released": year, "imdb_link": imdb_link, "tmdb_link": themoviedb_link, "imdb_id": imdb_id,
                        "tmdb_id": themoviedb_id, "lb_rating": lb_rating, "histogram": film_hist}

        return movie_object

    def get_movie_poster(self, movie_title_format):

        response = requests.get(self.posters_url.format(movie_title_format))
        soup = BeautifulSoup(response.text, features="html.parser")

        try:
            image_url = soup.find('div', attrs={'class': 'film-poster'}).find('img')['src'].split('?')[0]
            if self.empty_image_url_prefix in image_url:
                image_url = ''
        except AttributeError:
            image_url = ''

        return dict({"poster_url": image_url})

    def get_movie_themes(self, movie_title_format):

        response = requests.get(self.movies_themes_url.format(movie_title_format))
        soup = BeautifulSoup(response.text, features="html.parser")
        sections = soup.find_all('section', attrs={'class': 'section genre-group'})
        themes = []

        try:
            for i in range(len(sections)):
                theme = sections[i].find('h2').find('a').find('span', attrs={'class': 'label'}).text
                print(theme)
                themes.append(theme)
        except:
            themes = []

        return dict({"themes": themes})

    def get_movie_nanogenres(self, movie_title_format):

        response = requests.get(self.movies_nanogenres_url.format(movie_title_format))
        soup = BeautifulSoup(response.text, features="html.parser")
        sections = soup.find_all('section', attrs={'class': 'section genre-group'})
        nanogenres = []

        try:
            for i in range(len(sections)):
                nanogenre = sections[i].find('h2').find('a').find('span', attrs={'class': 'label'}).text
                print(nanogenre)
                nanogenres.append(nanogenre)
        except:
            nanogenres = []

        return dict({"nanogenres": nanogenres})

    def fetch_themoviedb_data(self, url):

        movie_object = {}
        nested_fields = ["genres", "production_countries", "spoken_languages"]
        simple_fields = ["popularity", "overview", "runtime", "vote_average", "vote_count", "release_date",
                         "original_language"]

        headers = {"accept": "application/json", "Authorization": "Bearer " + str(self.themoviedb_key)}
        response = requests.get(url, headers=headers).json()

        for field_name in nested_fields:
            try:
                movie_object[field_name] = [x["name"] for x in response[field_name]]
            except:
                movie_object[field_name] = None

        for field_name in simple_fields:
            try:
                movie_object[field_name] = response[field_name]
            except:
                movie_object[field_name] = None

        movie_object['last_updated'] = datetime.datetime.now()

        return movie_object

    def get_rated_movies(self):
        result = []
        for movie in self.movies_list:
            movie_data = self.get_letterboxd_movies(self.movies_url.format(movie), movie)
            result.append(movie_data)
        return result

    def get_movie_posters(self, movie):
        return dict(self.get_movie_poster(movie["movie_title_formatted"]))

    def get_movies_themes(self, movie):
        return dict(self.get_movie_themes(movie["movie_title_formatted"]))

    def get_movies_nanogenres(self, movie):
        return dict(self.get_movie_nanogenres(movie["movie_title_formatted"]))

    def get_rich_data(self, movie, type):
        if type != "none":
            return dict(
                self.fetch_themoviedb_data(self.themoviedb_url.format(type, movie["tmdb_id"], self.themoviedb_key)))
        return {}

    def get_movie_reviews(self, movie_title_format, num_pages):

        reviews = []

        for page_number in range(num_pages):
            response = requests.get(self.movie_reviews_url.format(movie_title_format, page_number + 1))
            soup = BeautifulSoup(response.text, features="html.parser")

            reviews_list = soup.find_all('div', attrs={'class': 'film-detail-content'})

            for review in reviews_list:

                # TODO : add reviews number of likes

                try:
                    review_date = review.find('span', attrs={'class': '_nobr'}).text
                except:
                    review_date = ""

                try:
                    review_content = review.find('div', attrs={'class': 'body-text -prose collapsible-text'}).find(
                        "p").text
                except:
                    review_content = ""

                try:
                    review_author = review.find('strong', attrs={'class': 'name'}).text
                except:
                    review_author = ""

                try:
                    review_note = \
                        review.find('p', attrs={'class': 'attribution'}).find('span')["class"][-1].split("rated-")[-1]
                except:
                    review_note = ""

                try:
                    review_comments = review.find('p', attrs={'class': 'attribution'}).find('a', attrs={
                        'class': 'has-icon icon-comment icon-16 comment-count'}).text
                except:
                    review_comments = ""

                reviews.append(
                    {"review_date": review_date, "review_content": review_content, "review_author": review_author,
                     "review_note": review_note, "review_comments": review_comments})

        return reviews
