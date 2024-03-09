import datetime
import os

import requests
from bs4 import BeautifulSoup


class ScrapingMovies:

    def __init__(self, movies_list):
        self.movies_url = "https://letterboxd.com/film/{}/"
        self.posters_url = "https://letterboxd.com/ajax/poster/film/{}/hero/230x345"
        self.themoviedb_url = "https://api.themoviedb.org/3/{}/{}"
        self.themoviedb_key = os.getenv("THEMOVIEDB_KEY")
        self.empty_image_url_prefix = "https://s.ltrbxd.com/static/img/empty-poster"
        self.movies_themes_url = "https://letterboxd.com/film/{}/themes/"
        self.movies_nanogenres_url = "https://letterboxd.com/film/{}/nanogenres/"
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
            type = "movie"
        except:
            try:
                themoviedb_link = soup.find("a", attrs={"data-track-action": "TMDb"})['href']
                themoviedb_id = themoviedb_link.split('/tv')[1].strip('/').split('/')[0]
                type = "tv"
            except:
                themoviedb_link = ""
                themoviedb_id = ""
                type = "none"

        movie_object = {"movie_title_formatted": movie_title_format, "movie_title": movie_title, "type": type,
                        "year_released": year, "imdb_link": imdb_link, "tmdb_link": themoviedb_link, "imdb_id": imdb_id,
                        "tmdb_id": themoviedb_id}

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

    def get_movie_themes(self, movie):
        return dict(self.get_movie_themes(movie["movie_title_formatted"]))

    def get_movie_nanogenres(self, movie):
        return dict(self.get_movie_nanogenres(movie["movie_title_formatted"]))

    def get_rich_data(self, movie, type):
        if type != "none":
            return dict(
                self.fetch_themoviedb_data(self.themoviedb_url.format(type, movie["tmdb_id"], self.themoviedb_key)))
        return {}
