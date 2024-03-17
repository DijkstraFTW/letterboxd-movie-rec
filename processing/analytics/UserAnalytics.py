import duckdb
import pandas as pd


class UserAnalytics:

    def __init__(self, db_path, reviews, movies):
        self.conn = duckdb.connect(db_path)
        self.cur = self.conn.cursor()
        self.user_reviews = pd.DataFrame(reviews)
        self.user_movies = pd.DataFrame(movies)

    def set_user_history_reviews(self):
        self.conn.execute(
            "CREATE TABLE reviews (movie_title VARCHAR, rating_date DATE, rating_val INTEGER, user_id VARCHAR, is_rewatch BOOLEAN, is_review BOOLEAN, is_liked BOOLEAN)")
        self.conn.register('reviews', self.user_reviews)

    def set_user_history_movies(self):
        self.conn.execute(
            """CREATE TABLE movies (movie_title_formatted VARCHAR,movie_title VARCHAR,type VARCHAR,year_released INTEGER,imdb_link VARCHAR,tmdb_link VARCHAR,imdb_id VARCHAR,tmdb_id VARCHAR,poster_url VARCHAR,genres VARCHAR,production_countries VARCHAR,spoken_languages VARCHAR,popularity FLOAT,overview VARCHAR,runtime INTEGER,vote_average FLOAT,vote_count INTEGER,release_date DATE,original_language VARCHAR,last_updated TIMESTAMP,themes VARCHAR,nanogenres VARCHAR)""")
        self.conn.register('movies', self.user_movies)

    def get_basic_metrics(self):

        # TODO : group in one object

        movies_reviewed = self.conn.execute("SELECT COUNT(*) FROM movies WHERE type = 'movie'").fetchone()[0]
        shows_reviewed = self.conn.execute("SELECT COUNT(*) FROM movies WHERE type = 'shows'").fetchone()[0]
        hours_watched = self.conn.execute("SELECT SUM(runtime) FROM movies").fetchone()[0]
        most_common_countries = self.conn.execute("""
            SELECT country, COUNT(*) AS count
            FROM (
                SELECT TRIM(unnested_country) AS country
                FROM (
                    SELECT UNNEST(SPLIT(REPLACE(REPLACE(production_countries, '[', ''), ']', ''), ',')) AS unnested_country
                    FROM movies
                ) AS t
            ) AS countries
            GROUP BY country
            ORDER BY count DESC""").fetchdf()

        mean_daily_reviews = self.conn.execute("""
        SELECT ROUND(AVG(num_reviews)) AS mean
        FROM (
            SELECT COUNT(*) AS num_reviews
            FROM reviews
            GROUP BY rating_date
        ) AS review_counts
        """).fetchone()[0]

        number_daily_reviews_over_mean = self.conn.execute(f"""
        SELECT COUNT(*) AS num_days_with_more_than_median_reviews
        FROM (
            SELECT rating_date, COUNT(*) AS num_reviews
            FROM reviews
            GROUP BY rating_date
            HAVING COUNT(*) > {mean_daily_reviews}
        ) AS days_with_more_than_median_reviews
        """).fetchdf()

        logged_per_release_year = self.conn.execute("""SELECT year_released, COUNT(*) AS num_movies
        FROM movies
        GROUP BY year_released
        ORDER BY year_released
        """).fetchdf()

        logged_per_year = self.conn.execute("""
        SELECT SUBSTRING(rating_date, -4) AS year, COUNT(*) AS num_reviews
        FROM reviews
        GROUP BY year
        ORDER BY year
        """).fetchdf()

        average_rating_per_year = self.conn.execute("""
        SELECT m.year_released, AVG(CAST(r.rating_val AS DOUBLE)) AS average_rating
        FROM movies m
        JOIN reviews r ON m.movie_title_formatted = r.movie_title
        GROUP BY m.year_released
        ORDER BY m.year_released
        """).fetchdf()
        
        
        # TODO
        longest_streak = ""


    def close(self):
        self.conn.close()
