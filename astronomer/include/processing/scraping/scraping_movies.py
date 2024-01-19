import datetime
import requests
from bs4 import BeautifulSoup
import os

class ScrapingMovies:

    def __init__(self, movies_list):
        self.movies_url = "https://letterboxd.com/film/{}/"
        self.posters_url = "https://letterboxd.com/ajax/poster/film/{}/hero/230x345"
        self.themoviedb_url = "https://api.themoviedb.org/3/{}/{}"
        self.themoviedb_key = os.getenv("THEMOVIEDB_KEY")
        self.empty_image_url_prefix = "https://s.ltrbxd.com/static/img/empty-poster"
        self.movies_list = movies_list

    def fetch_letterboxd(self, url, movie_title_format):

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
            type = "movie"
        except:
            try:
                themoviedb_link = soup.find("a", attrs={"data-track-action": "TMDb"})['href']
                themoviedb_id = themoviedb_link.split('/tv')[1].strip('/').split('/')[0]
                type = "tv"
            except TypeError :
                themoviedb_link = ""
                themoviedb_id = ""
                type = "none"

        movie_object = {"movie_title_formatted": movie_title_format, "movie_title": movie_title, "type": type, "year_released": year,
            "imdb_link": imdb_link, "tmdb_link": themoviedb_link, "imdb_id": imdb_id, "tmdb_id": themoviedb_id}

        return movie_object

    def get_movies(self):
        tasks = []
        for movie in self.movies_list:
            task = self.fetch_letterboxd(self.movies_url.format(movie), movie)
            tasks.append(task)
        tasks = list(set(tasks))
        return tasks

    def fetch_poster(self, url):

        response = requests.get(url)
        soup = BeautifulSoup(response.text, features="html.parser")

        try:
            image_url = soup.find('div', attrs={'class': 'film-poster'}).find('img')['src'].split('?')[0]
            if self.empty_image_url_prefix in image_url:
                image_url = ''
        except AttributeError:
            image_url = ''

        return dict({"poster_url": image_url})

    def get_movie_posters(self, movie):
        return dict(self.fetch_poster(self.posters_url.format(movie["movie_title_formatted"])))

    def fetch_themoviedb_data(self, url):

        movie_object = {}

        headers = {
            "accept": "application/json",
            "Authorization": "Bearer " + str(self.themoviedb_key)
        }

        response = requests.get(url, headers=headers).json()

        object_fields = ["genres", "production_countries", "spoken_languages"]
        for field_name in object_fields:
            try:
                movie_object[field_name] = [x["name"] for x in response[field_name]]
            except:
                movie_object[field_name] = None

        simple_fields = ["popularity", "overview", "runtime", "vote_average", "vote_count", "release_date",
                         "original_language"]
        for field_name in simple_fields:
            try:
                movie_object[field_name] = response[field_name]
            except:
                movie_object[field_name] = None

        movie_object['last_updated'] = datetime.datetime.now()

        return movie_object

    def get_rich_data(self, movie, type):
        if type != "none":
            return dict(self.fetch_themoviedb_data(self.themoviedb_url.format(type, movie["tmdb_id"], self.themoviedb_key)))
        return {}