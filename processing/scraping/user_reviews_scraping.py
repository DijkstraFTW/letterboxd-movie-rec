import uuid
import asyncio
import time
import os
import random
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
from app_logger.app_logger import setup_logger

logger = setup_logger("/root/letterboxd-movie-rec/logs/user_reviews_scraping.log", "UserReviewsScraping")


class UserReviewsScraping:

    def __init__(self, max_concurrent=2, requests_per_second=1):
        self.popular_users_url = "https://letterboxd.com/members/popular/this/month/page/{}/"
        self.user_page_url = "https://letterboxd.com/{}/"
        self.users_diary_page_number_url = "https://letterboxd.com/{}/diary/"
        self.users_diary_pages_url = "https://letterboxd.com/{}/diary/films/page/{}/"
        self.users_grid_page_number_url = "https://letterboxd.com/{}/films/by/date/"
        self.users_grid_pages_url = "https://letterboxd.com/{}/films/by/date/page/{}/"
        self.num_top_users_pages = 67 # 30 users per page, 2010 in total
        self.num_user_ratings_pages = 3
        
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

    async def reset_session(self):
        """
        Close current session and open a fresh one (clears cookies/state between users)
        """
        await self.session.close()
        proxy_url = os.getenv("PROXY_URL")
        proxies = {"https": proxy_url, "http": proxy_url} if proxy_url else None
        self.session = AsyncSession(impersonate="chrome120", timeout=30, proxies=proxies, verify=False)

    async def rate_limited_request(self, url, _retries=0, headers=None):
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
                response = await self.session.get(url, headers=headers)
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
                return await self.rate_limited_request(url, _retries + 1, headers=headers)
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
        return await self.rate_limited_request(url, _retries + 1, headers=headers)

    async def fetch_html(self, url, headers=None):
        """
        Async HTTP GET request with rate limiting
        """
        return await self.rate_limited_request(url, headers=headers)

    async def get_popular_users(self):
        """
        Get the most popular users on Letterboxd asynchronously
        :return: list : list of users
        """
        users = []

        await self.fetch_html("https://letterboxd.com/")

        tasks = [
            self.fetch_html(self.popular_users_url.format(page))
            for page in range(2, self.num_top_users_pages + 1)
        ]
        tasks.insert(0, self.fetch_html("https://letterboxd.com/members/popular/this/month/"))
        
        pages_html = await asyncio.gather(*tasks)

        for html in pages_html:
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table", attrs={"class": "table-base member-table"})
            if not table:
                continue
                
            rows = table.findAll("td", attrs={"class": "col-member table-person"})

            for row in rows:
                user_id = str(uuid.uuid4())
                link = row.find("a", attrs={"class": "avatar -a40"})["href"]
                username = link.strip('/')
                display_name = row.find("a", attrs={"class": "name"}).text.strip()
                num_reviews = int(row.find("small").find("a").text.replace('\xa0', ' ').split()[0].replace(',', ''))
                user = {"user_id": user_id, "username": username, "display_name": display_name,
                        "num_reviews": num_reviews}
                if username not in {u["username"] for u in users}:
                    users.append(user)

        return users

    async def get_user(self, username):
        """
        Get user data asynchronously
        :param username: username
        :return: dictionary : dictionary with user data
        """

        html = await self.fetch_html(self.user_page_url.format(username))
        if not html:
            return {}

        page = BeautifulSoup(html, "html.parser")
        
        user_id = str(uuid.uuid4())
        display_name_element = page.find("span", attrs={"class": "displayname tooltip"})
        display_name = display_name_element.text.strip() if display_name_element else username
        
        num_reviews_element = page.find("h4", attrs={"class": "profile-statistic statistic"})
        if num_reviews_element:
            value_element = num_reviews_element.find("span", attrs={"class": "value"})
            num_reviews = value_element.text if value_element else "0"
        else:
            num_reviews = "0"

        user = {"user_id": user_id, "username": username, "display_name": display_name,
                "num_reviews": num_reviews}

        return user

    async def get_diary_reviews_page_count(self, username):
        """
        Get the number of pages of diary reviews for a user asynchronously
        :param username: username
        :return: int : number of pages in a user's review diary
        """

        html = await self.fetch_html(self.users_diary_page_number_url.format(username))
        if not html:
            return 1

        soup = BeautifulSoup(html, features="html.parser")
        body = soup.find("body")

        if body and "error" in body.get("class", []):
            return -1

        try:
            page_links = soup.findAll("li", attrs={"class", "paginate-page"})
            if page_links:
                page_link = page_links[-1]
                num_pages = int(page_link.find("a").text.replace(",", ""))
            else:
                num_pages = self.num_user_ratings_pages
        except (IndexError, ValueError, AttributeError):
            num_pages = self.num_user_ratings_pages

        return num_pages

    async def get_grid_reviews_page_count(self, username):
        """
        Get the number of pages of grid reviews for a user asynchronously
        :param username: username
        :return: int : number of pages in a user's grid reviews
        """

        html = await self.fetch_html(self.users_grid_page_number_url.format(username))
        if not html:
            return 1

        soup = BeautifulSoup(html, features="html.parser")
        body = soup.find("body")

        if body and "error" in body.get("class", []):
            return -1

        try:
            page_links = soup.findAll("li", attrs={"class", "paginate-page"})
            if page_links:
                page_link = page_links[-1]
                num_pages = int(page_link.find("a").text.replace(",", ""))
            else:
                num_pages = self.num_user_ratings_pages
        except (IndexError, ValueError, AttributeError):
            num_pages = self.num_user_ratings_pages

        return num_pages

    def get_ratings_data(self, html, user_id, return_unrated=False):
        """
        Get ratings data from a user's review page
        :param html: HTML content
        :param user_id: autogenerated custom user id
        :param return_unrated: return unrated movies
        :return: list : list of ratings
        """

        ratings = []
        soup = BeautifulSoup(html, features="html.parser")
        reviews = soup.select('tr[class*="diary-entry-row viewing-poster-container"]')
        
        for review in reviews:
            try:
                date_element = review.find('td', class_='col-daydate -align-center -padding-inline-large').find("a", class_="daydate")["href"].split("/")
                date = f"{date_element[5]}-{date_element[6]}-{date_element[7]}"
            except:
                date = ""

            try:
                movie_title = review.find("div", attrs={"data-component-class": "LazyPoster"})["data-item-slug"]
            except:
                continue

            try:
                rating_element = review.find('td', class_='col-rating -padding-inline-large')
                rated_span = rating_element.find('span', class_=lambda c: c and any(cls.startswith('rated-') for cls in c.split()))
                if rated_span:
                    rated_class = next(cls for cls in rated_span['class'] if cls.startswith('rated-'))
                    rating_val = float(rated_class.split('-')[1])
                else:
                    rating_val = float(rating_element.find('div', class_="rateit-range")["aria-valuenow"])
            except:
                rating_val = 0

            try:
                rewatch_element = review.find('td', class_='col-rewatch -align-center -padding-inline-large js-td-rewatch').find("span")
                is_rewatch = rewatch_element.has_attr('class') and 'icon-rewatch' in rewatch_element['class']
            except:
                is_rewatch = False

            try:
                review_element = review.find('td', class_='col-review -align-center -padding-inline-large js-td-review').find("a")
                is_reviewed = review_element is not None
            except:
                is_reviewed = False
                
            try:
                like_td = review.find('td', class_='col-like -align-center -padding-inline-large')
                is_liked = like_td.find('span', class_=lambda c: c and 'icon-liked' in c) is not None
            except:
                is_liked = False

            rating_object = {
                "movie_title": movie_title, 
                "rating_date": date, 
                "rating_val": rating_val,
                "user_id": user_id, 
                "is_rewatch": is_rewatch, 
                "is_review": is_reviewed,
                "is_liked": is_liked
            }
            
            ratings.append(rating_object)

        return ratings

    async def get_user_ratings(self, username, user_id, since_date=None, return_unrated=False, pages_limit=20):
        """
        Get user ratings based on username and number of review pages asynchronously
        :param username: username
        :param user_id: autogenerated custom user id
        :param since_date: only return ratings on or after this date (YYYY-MM-DD). Enables early stop.
        :param return_unrated: return unrated movies
        :param pages_limit: hard limit of pages of reviews to return
        :return: list : list of ratings
        """

        ratings = []
        nb_diary_pages = await self.get_diary_reviews_page_count(username)

        logger.info(f"User {username} has {nb_diary_pages} diary pages of reviews.")

        if nb_diary_pages == -1:
            return []

        # Visit profile first to pick up session cookies before hitting the diary
        await self.fetch_html(self.user_page_url.format(username))

        referer_headers = {"Referer": self.user_page_url.format(username)}

        if since_date:
            # Sequential fetch with early stop: diary is newest-first so stop once a full page is older than cutoff
            max_pages = min(nb_diary_pages, pages_limit)
            for page in range(1, max_pages + 1):
                url = (self.users_diary_page_number_url.format(username) if page == 1
                       else self.users_diary_pages_url.format(username, page))
                html = await self.fetch_html(url, headers=referer_headers)
                if not html:
                    continue
                page_ratings = self.get_ratings_data(html, user_id, return_unrated)
                new_ratings = [r for r in page_ratings if r["rating_date"] >= since_date]
                ratings.extend(new_ratings)
                if len(new_ratings) < len(page_ratings):
                    # Hit the cutoff boundary — no need to fetch older pages
                    break
        else:
            # Concurrent fetch for full scrape
            tasks = [
                self.fetch_html(self.users_diary_pages_url.format(username, i + 1), headers=referer_headers)
                for i in range(1, min(nb_diary_pages, 20))
            ]
            tasks.insert(0, self.fetch_html(self.users_diary_page_number_url.format(username), headers=referer_headers))
            pages_html = await asyncio.gather(*tasks)
            for html in pages_html:
                if html:
                    page_ratings = self.get_ratings_data(html, user_id, return_unrated)
                    ratings.extend(page_ratings)

        return ratings

    async def get_all_ratings(self, username, data_opt_out=False):
        """
        Fetch all ratings for a user asynchronously
        :param username: username
        :param data_opt_out: opt out of storing data in database
        :return: list : list of ratings
        """

        user_data = await self.get_user(username)
        if not user_data:
            return [], "user_not_found"

        user_ratings = await self.get_user_ratings(username, user_data["user_id"], return_unrated=True)
        user_ratings = [x for x in user_ratings if x["rating_val"] >= 0]

        return user_ratings

    async def get_popular_users_with_ratings(self, max_users=50):
        """
        Get popular users with their ratings asynchronously
        :param max_users: maximum number of users to process
        :return: list of users with ratings
        """
        users = await self.get_popular_users()
        users = users[:max_users]
        
        results = []
        for user in users:
            try:
                ratings = await self.get_user_ratings(user["username"], user["user_id"])
                user["ratings"] = ratings
                user["ratings_count"] = len(ratings)
                results.append(user)
            except Exception as e:
                logger.error(f"Error getting ratings for user {user['username']}: {e}")
                continue
        
        return results

