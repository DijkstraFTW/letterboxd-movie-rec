import uuid
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from logger import setup_logger

logger = setup_logger("../logs/factg.log", "UserReviewsScraping")


class UserReviewsScraping:

    def __init__(self, max_concurrent=4, requests_per_second=2):
        self.popular_users_url = "https://letterboxd.com/members/popular/this/month/page/{}/"
        self.user_page_url = "https://letterboxd.com/{}/"
        self.users_diary_page_number_url = "https://letterboxd.com/{}/films/diary/by/added/"
        self.users_diary_pages_url = "https://letterboxd.com/{}/films/diary/by/added/page/{}/"
        self.users_grid_page_number_url = "https://letterboxd.com/{}/films/by/date/"
        self.users_grid_pages_url = "https://letterboxd.com/{}/films/by/date/page/{}/"
        self.num_top_users_pages = 10
        self.num_user_ratings_pages = 3
        
        # Concurrency settings
        self.max_concurrent = max_concurrent
        self.requests_per_second = requests_per_second
        self.delay_between_requests = 1.0 / requests_per_second
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.last_request_time = 0
        self.session = None

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_connect=10, sock_read=10)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    async def rate_limited_request(self, url):
        """
        Rate limited request with concurrency control
        """
        
        async with self.semaphore:
            now = asyncio.get_event_loop().time()
            elapsed = now - self.last_request_time
            if elapsed < self.delay_between_requests:
                await asyncio.sleep(self.delay_between_requests - elapsed)
            
            self.last_request_time = now
            
            try:
                async with self.session.get(url) as response:
                    if response.status == 429:  
                        retry_after = int(response.headers.get('Retry-After', 5))
                        logger.warning(f"Rate limited. Waiting {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        return await self.rate_limited_request(url) 
                    
                    response.raise_for_status()
                    return await response.text()
                    
            except aiohttp.ClientResponseError as e:
                if e.status == 429:
                    logger.warning(f"Rate limited on {url}. Waiting 5 seconds")
                    await asyncio.sleep(5)
                    return await self.rate_limited_request(url)
                logger.error(f"HTTP error for {url}: {e}")
                return ""
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                return ""

    async def fetch_html(self, url):
        """
        Async HTTP GET request with rate limiting
        """
        return await self.rate_limited_request(url)

    async def get_popular_users(self):
        """
        Get the most popular users on Letterboxd asynchronously
        :return: list : list of users
        """
        users = []
        
        tasks = [
            self.fetch_html(self.popular_users_url.format(page))
            for page in range(1, self.num_top_users_pages + 1)
        ]
        
        pages_html = await asyncio.gather(*tasks)
        
        for html in pages_html:
            if not html:
                continue
                
            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table", attrs={"class": "person-table"})
            if not table:
                continue
                
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
                date_element = review.find('td', class_='td-day diary-day center').find("a")["href"].split("/")
                date = f"{date_element[-4]}-{date_element[-5]}-{date_element[-6]}"
            except:
                date = ""

            try:
                movie_title = review.find("div", attrs={"class", "film-poster"})["data-film-slug"]
            except:
                continue

            try:
                rating_element = review.find('td', class_='td-rating rating-green')
                rating_val = rating_element.find('span')['class'][-1].split("rated-")[-1]
                if rating_val == "rating":
                    rating_val = 0
            except:
                rating_val = 0

            try:
                rewatch_element = review.find('td', class_='td-rewatch center').find("span")
                is_rewatch = rewatch_element.has_attr('class') and 'icon-rewatch' in rewatch_element['class']
            except:
                is_rewatch = False

            try:
                review_element = review.find('td', class_='td-review center').find("a")
                is_reviewed = review_element is not None
            except:
                is_reviewed = False

            rating_object = {
                "movie_title": movie_title, 
                "rating_date": date, 
                "rating_val": rating_val,
                "user_id": user_id, 
                "is_rewatch": is_rewatch, 
                "is_review": is_reviewed
            }
            ratings.append(rating_object)

        return ratings

    async def get_user_ratings(self, username, user_id, return_unrated=False):
        """
        Get user ratings based on username and number of review pages asynchronously
        :param username: username
        :param user_id: autogenerated custom user id
        :param return_unrated: return unrated movies
        :return: list : list of ratings
        """

        ratings = []
        nb_diary_pages = await self.get_diary_reviews_page_count(username)
        
        if nb_diary_pages == -1:
            return []

        tasks = [
            self.fetch_html(self.users_diary_pages_url.format(username, i + 1))
            for i in range(min(nb_diary_pages, 50))
        ]
        
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

