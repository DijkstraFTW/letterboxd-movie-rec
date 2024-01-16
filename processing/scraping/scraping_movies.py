import datetime
import requests
from bs4 import BeautifulSoup
import os

class ScrapingMovies:

    def __init__(self, movies_list):
        self.movies_url = "https://letterboxd.com/film/{}/"
        self.posters_url = "https://letterboxd.com/ajax/poster/film/{}/hero/230x345"
        self.themoviedb_url = "https://api.themoviedb.org/3/movie/{}?api_key={}"
        self.themoviedb_key = os.getenv("THEMOVIEDB_KEY")
        self.empty_image_url_prefix = "https://s.ltrbxd.com/static/img/empty-poster"
        self.movies_list = movies_list

    def fetch_letterboxd(self, url, input_data={}):

        response = requests.get(url)
        soup = BeautifulSoup(response.text)
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
        except:
            themoviedb_link = ""
            themoviedb_id = ""

        movie_object = {"movie_id": 'input_data["movie_id"]', "movie_title": movie_title, "year_released": year,
            "imdb_link": imdb_link, "tmdb_link": themoviedb_link, "imdb_id": imdb_id, "tmdb_id": themoviedb_id}

        return movie_object

    def get_movies(self):
        tasks = []
        for movie in self.movies_list:
            task = self.fetch_letterboxd(self.movies_url.format(movie), {"movie_id": movie})
            tasks.append(task)
        return tasks

    def fetch_poster(self, input_data={}):

        response = requests.get(self.posters_url)
        soup = BeautifulSoup(response.text)

        try:
            image_url = soup.find('div', attrs={'class': 'film-poster'}).find('img')['processing'].split('?')[0]
            if self.empty_image_url_prefix in image_url:
                image_url = ''
        except AttributeError:
            image_url = ''

        movie_object = {"movie_id": input_data["movie_id"], }

        if image_url != '':
            movie_object["image_url"] = image_url

        movie_object['last_updated'] = datetime.datetime.now()

        return movie_object

    def get_movie_posters(self):
        tasks = []
        for movie in self.movies_list:
            task = self.fetch_poster(self.posters_url.format(movie), {"movie_id": movie})
            tasks.append(task)
        return tasks

    def fetch_themoviedb_data(self, input_data={}):

        response = requests.get(self.themoviedb_url)
        soup = BeautifulSoup(response.text)

        movie_object = {}

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

    def get_rich_data(self):
        tasks = []
        movie_list = [x for x in self.movies_list if x['tmdb_id']]

        for movie in movie_list:
            task = self.fetch_themoviedb_data(self.themoviedb_url.format(movie["tmdb_id"], self.themoviedb_key),
                                              {"movie_id": movie["movie_id"]})
            tasks.append(task)

        return tasks
