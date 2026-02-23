import datetime
import json
import time
import os
import re
import asyncio
import random
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

from processing.utils.utils import val2stars
from app_logger.app_logger import setup_logger

logger = setup_logger("/root/letterboxd-movie-rec/logs/movies_scraping.log", "MoviesScraping")


class MoviesScraping:

    def __init__(self, movies_list, max_concurrent=4, requests_per_second=2):
        self.movies_url = "https://letterboxd.com/film/{}/"
        self.themoviedb_url = "https://api.themoviedb.org/3/{}/{}"
        self.themoviedb_key = os.getenv("THEMOVIEDB_KEY")
        self.empty_image_url_prefix = "https://s.ltrbxd.com/static/img/empty-poster"
        self.movies_themes_url = "https://letterboxd.com/film/{}/themes/"
        self.movies_nanogenres_url = "https://letterboxd.com/film/{}/nanogenres/"
        self.movie_reviews_url = "https://letterboxd.com/film/{}/reviews/by/added-earliest/page/{}/"
        self.rating_histograms_url = "https://letterboxd.com/csi/film/{}/rating-histogram/"
        self.movies_list = movies_list

        # Concurrency settings
        self.max_concurrent = max_concurrent
        self.requests_per_second = requests_per_second
        self.delay_between_requests = 1.0 / requests_per_second
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.last_request_time = 0
        self.session = None

    async def __aenter__(self):
        proxy_url = os.getenv("PROXY_URL")
        proxies = {"https": proxy_url, "http": proxy_url} if proxy_url else None
        self.session = AsyncSession(impersonate="chrome120", timeout=30, proxies=proxies, verify=False)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    async def rate_limited_request(self, url, _retries=0):
        """
        Rate limited request with concurrency control and exponential backoff
        """
        max_retries = 3
        status = None
        text = None
        retry_after = None
        connection_error = None

        async with self.semaphore:
            now = time.time()
            elapsed = now - self.last_request_time
            delay = self.delay_between_requests + random.uniform(0.5, 2.0)
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)

            self.last_request_time = time.time()

            try:
                response = await self.session.get(url)
                status = response.status_code
                text = response.text if status == 200 else None
                retry_after = response.headers.get('Retry-After')
            except Exception as e:
                connection_error = e

        # All retries and sleeps happen outside the semaphore to avoid deadlocks
        if connection_error is not None:
            logger.error(f"Error fetching {url}: {connection_error}")
            if _retries < max_retries:
                wait = 2 ** _retries
                logger.warning(f"Retrying {url} in {wait}s (attempt {_retries + 1}/{max_retries})")
                await asyncio.sleep(wait)
                return await self.rate_limited_request(url, _retries + 1)
            return ""

        if status == 200:
            return text

        if status == 404:
            logger.warning(f"404 Not Found: {url}")
            return ""

        if _retries >= max_retries:
            logger.error(f"HTTP {status} for {url} after {max_retries} retries")
            return ""

        if status == 429:
            wait = max(int(retry_after) if retry_after else 30, 30)
            logger.warning(f"Rate limited on {url}. Waiting {wait}s")
        elif status == 403:
            wait = 10 * (2 ** _retries)
            logger.warning(f"403 Forbidden for {url}. Backing off {wait}s (attempt {_retries + 1}/{max_retries})")
        else:
            wait = 2 ** _retries
            logger.error(f"HTTP {status} for {url}. Backing off {wait}s (attempt {_retries + 1}/{max_retries})")

        await asyncio.sleep(wait)
        return await self.rate_limited_request(url, _retries + 1)

    async def fetch_html(self, url):
        """
        Async HTTP GET request with rate limiting
        """
        return await self.rate_limited_request(url)

    async def get_rated_movies_batch(self, batch_size=10):
        """
        Process movies in batches
        """
        logger.info(f"Getting {len(self.movies_list)} rated movies in batches of {batch_size}")
        
        all_results = []
        
        for i in range(0, len(self.movies_list), batch_size):
            batch = self.movies_list[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(self.movies_list)-1)//batch_size + 1}")
            
            tasks = [
                self.get_letterboxd_movies(self.movies_url.format(movie), movie)
                for movie in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            all_results.extend([
                result if not isinstance(result, Exception) else {}
                for result in batch_results
            ])
            
            await asyncio.sleep(1)
        
        return all_results

    async def get_letterboxd_movies(self, url, movie_title_format):
        """
        Get movie data from letterboxd asynchronously
        """
        html = await self.fetch_html(url)
        if not html:
            return {}

        soup = BeautifulSoup(html, features="html.parser")
        movie_header = soup.find('section', attrs={'class': 'production-masthead -shadowed -productionscreen -film'})

        try:
            movie_title = movie_header.find('span', attrs={'class': 'name js-widont prettify'}).text
        except AttributeError:
            movie_title = ''

        try:
            year = int(movie_header.find('span', attrs={'class': 'releasedate'}).find('a').text)
        except AttributeError:
            year = None

        try:
            imdb_link = soup.find("a", attrs={"data-track-action": "IMDb"})['href']
            imdb_id = imdb_link.split('/title')[1].strip('/').split('/')[0]
        except:
            imdb_link = ""
            imdb_id = ""

        try:
            themoviedb_link = soup.find("a", attrs={"data-track-action": "TMDB"})['href']
            themoviedb_id = themoviedb_link.split('/movie')[1].strip('/').split('/')[0]
            type_ = "movie"
        except:
            try:
                themoviedb_link = soup.find("a", attrs={"data-track-action": "TMDB"})['href']
                themoviedb_id = themoviedb_link.split('/tv')[1].strip('/').split('/')[0]
                type_ = "tv"
            except:
                themoviedb_link = ""
                themoviedb_id = ""
                type_ = "none"

        hist_html = await self.fetch_html(self.rating_histograms_url.format(movie_title_format))
        hist_soup = BeautifulSoup(hist_html, features="html.parser") if hist_html else BeautifulSoup("", "html.parser")
        ratings = hist_soup.find_all("li", {'class': 'rating-histogram-bar'})

        tot_ratings = 0
        film_hist = {}

        try:
            fans = hist_soup.find('a', {'class': 'all-link more-link'}).text
            fans = re.findall(r'\d+.\d+K?|\d+K?', fans)[0]
            if "." in fans and "K" in fans:
                fans = int(float(fans[:-1]) * 1000)
            elif "K" in fans:
                fans = int(fans[-1]) * 1000
            else:
                fans = int(fans)
        except:
            fans = 0

        lb_rating = 0
        image_url = ''
        try:
            data_script = soup.find('script', {'type': 'application/ld+json'})
            raw_json = data_script.string.strip().replace("/* <![CDATA[ */", "").replace("/* ]]> */", "").strip()
            ld_data = json.loads(raw_json)
            lb_rating = ld_data.get("aggregateRating", {}).get("ratingValue", 0)
            image_url = ld_data.get("image", "")
        except:
            pass

        try:
            for i, r in enumerate(ratings):
                string = r.text.strip(" ")
                stars = val2stars((i + 1) / 2)
                if string == "":
                    film_hist[f"{stars}"] = 0
                else:
                    num_ratings = re.findall(r'\d+', string)[:-1]
                    num_ratings = int(''.join(num_ratings))
                    film_hist[f"{stars}"] = num_ratings
                    tot_ratings += num_ratings
        except:
            tot_ratings = ""

        film_hist["fans"] = fans
        film_hist["total"] = tot_ratings

        return {
            "movie_title_formatted": movie_title_format, 
            "movie_title": movie_title, 
            "type": type_,
            "year_released": year, 
            "imdb_link": imdb_link, 
            "tmdb_link": themoviedb_link, 
            "imdb_id": imdb_id,
            "tmdb_id": themoviedb_id, 
            "lb_rating": lb_rating, 
            "histogram": film_hist,
            "poster_url": image_url
        }

    async def get_movie_genres(self, movie_title_format, key_name):
        """
        Get movie themes or nanogenres from Letterboxd asynchronously
        """
        url = self.movies_themes_url if key_name == "themes" else self.movies_nanogenres_url
        html = await self.fetch_html(url.format(movie_title_format))
        if not html:
            return {key_name: []}

        soup = BeautifulSoup(html, features="html.parser")
        sections = soup.find_all('section', attrs={'class': 'section genre-group'})
        items = [
            section.find('h2').find('a').find('span', attrs={'class': 'label'}).text
            for section in sections
            if section.find('h2') and section.find('h2').find('a')
        ]

        return {key_name: items}

    async def get_themoviedb_data(self, url):
        """
        Fetch movie data from themoviedb asynchronously
        """
        headers = {
            "accept": "application/json", 
            "Authorization": f"Bearer {self.themoviedb_key}"
        }

        try:
            response = await self.session.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"Error fetching TMDb data: {e}")
            return {}

        movie_object = {}
        nested_fields = ["genres", "production_countries", "spoken_languages"]
        simple_fields = ["popularity", "overview", "runtime", "vote_average", "vote_count", "release_date",
                         "original_language"]

        for field_name in nested_fields:
            try:
                movie_object[field_name] = [x["name"] for x in data[field_name]]
            except:
                movie_object[field_name] = None

        for field_name in simple_fields:
            try:
                movie_object[field_name] = data[field_name]
            except:
                movie_object[field_name] = None

        movie_object['last_updated'] = datetime.datetime.now()

        return movie_object

    async def get_rated_movies(self):
        """
        Get rated movies from letterboxd asynchronously
        """
        print(f"Getting {len(self.movies_list)} rated movies")
        
        tasks = [
            self.get_letterboxd_movies(self.movies_url.format(movie), movie)
            for movie in self.movies_list
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [
            result if not isinstance(result, Exception) else {}
            for result in results
        ]

    async def get_movie_reviews(self, movie_title_format, num_pages):
        """
        Get movie reviews from letterboxd asynchronously
        """
        reviews = []
        
        tasks = [
            self.fetch_html(self.movie_reviews_url.format(movie_title_format, page_number + 1))
            for page_number in range(num_pages)
        ]
        
        pages_html = await asyncio.gather(*tasks)
        
        for html in pages_html:
            if not html:
                continue
                
            soup = BeautifulSoup(html, features="html.parser")
            reviews_list = soup.find_all('div', attrs={'class': 'film-detail-content'})

            for review in reviews_list:
                try:
                    review_date = review.find('span', attrs={'class': '_nobr'}).text
                except:
                    review_date = ""

                try:
                    review_content = review.find('div', attrs={'class': 'body-text -prose collapsible-text'}).find("p").text
                except:
                    review_content = ""

                try:
                    review_author = review.find('strong', attrs={'class': 'name'}).text
                except:
                    review_author = ""

                try:
                    review_note = review.find('p', attrs={'class': 'attribution'}).find('span')["class"][-1].split("rated-")[-1]
                except:
                    review_note = ""

                try:
                    review_comments = review.find('p', attrs={'class': 'attribution'}).find('a', attrs={
                        'class': 'has-icon icon-comment icon-16 comment-count'}).text
                except:
                    review_comments = ""

                reviews.append({
                    "review_date": review_date, 
                    "review_content": review_content, 
                    "review_author": review_author,
                    "review_note": review_note, 
                    "review_comments": review_comments
                })

        return reviews

    async def fetch_movies_genres(self, movie, key_name):
        """
        Fetch movie genres asynchronously
        """
        return await self.get_movie_genres(movie["movie_title_formatted"], key_name)

    async def fetch_themoviedb_data(self, movie, type):
        """
        Fetch data from themoviedb asynchronously
        """
        if type != "none" and movie.get("tmdb_id"):
            url = self.themoviedb_url.format(type, movie["tmdb_id"])
            return await self.get_themoviedb_data(url)
        return {}
