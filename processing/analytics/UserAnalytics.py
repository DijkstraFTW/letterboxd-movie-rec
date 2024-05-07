import os

import duckdb
import pandas as pd


class UserAnalytics:

    def __init__(self, db_path, reviews, movies):
        if os.path.exists(db_path):
            os.remove(db_path)
        if os.path.exists(str(db_path) + ".wal"):
            os.remove(str(db_path) + ".wal")
        self.conn = duckdb.connect(db_path)
        self.cur = self.conn.cursor()
        self.user_reviews = pd.DataFrame(reviews)
        self.user_movies = pd.DataFrame(movies)
        self.user_movies = self.user_movies.astype(str)

    def set_user_history_reviews(self):
        """
        Sets the user history reviews table in duckdb
        """
        self.conn.execute("""
        CREATE TABLE reviews(
        movie_title VARCHAR,
        rating_date DATE,
        rating_val INTEGER,
        user_id VARCHAR,
        is_rewatch BOOLEAN,
        is_review BOOLEAN
        );
        """)
        self.conn.register('reviews', self.user_reviews)

    def set_user_history_movies(self):
        """
        Sets the user history movies table in duckdb
        """
        self.conn.execute("""
        CREATE TABLE movies (
        movie_title_formatted VARCHAR,
        movie_title VARCHAR,
        type VARCHAR,
        year_released INTEGER,
        imdb_link VARCHAR,
        tmdb_link VARCHAR,
        imdb_id VARCHAR,
        tmdb_id VARCHAR,
        lb_rating DECIMAL(2, 1),
        histogram VARCHAR,
        poster_url VARCHAR,
        genres VARCHAR,
        production_countries VARCHAR,
        spoken_languages VARCHAR,
        popularity FLOAT,
        overview VARCHAR,
        runtime INTEGER,
        vote_average FLOAT,
        vote_count INTEGER,
        release_date DATE,
        original_language VARCHAR,
        last_updated TIMESTAMP,
        themes VARCHAR,
        nanogenres VARCHAR
        );
        """)
        self.conn.register('movies', self.user_movies)

    def get_basic_metrics(self):
        """
        Returns basic metrics about the user's reviews and movies history
        :return: dictionary : dictionary with basic metrics
        """

        print(self.conn.execute("SELECT * FROM movies LIMIT 1").fetchdf())

        movies_reviewed = self.conn.execute("""
        SELECT COUNT(*) 
        FROM movies 
        WHERE type = 'movie';
        """).fetchone()[0]

        shows_reviewed = self.conn.execute("""
        SELECT COUNT(*) 
        FROM movies 
        WHERE type = 'shows';
        """).fetchone()[0]

        hours_watched = self.conn.execute("""
        SELECT SUM(runtime) 
        FROM movies;
        """).fetchone()[0]

        most_common_countries = self.conn.execute("""
            SELECT country, COUNT(*) AS count
            FROM (
                SELECT TRIM(unnested_country) AS country
                FROM (
                    SELECT UNNEST(SPLIT(REPLACE(REPLACE(production_countries, '[', ''), ']', ''), ','))
                    AS unnested_country
                    FROM movies
                ) AS t
            ) AS countries
            GROUP BY country
            ORDER BY count DESC""").fetchdf().to_dict(orient='records')

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
        """).fetchone()[0]

        logged_per_release_year = self.conn.execute("""SELECT year_released, COUNT(*) AS num_movies
        FROM movies
        GROUP BY year_released
        ORDER BY year_released
        """).fetchdf().to_dict(orient='records')

        logged_per_year = self.conn.execute("""
        SELECT SUBSTRING(rating_date, -4) AS year, COUNT(*) AS num_reviews
        FROM reviews
        GROUP BY year
        ORDER BY year
        """).fetchdf().to_dict(orient='records')

        average_rating_per_year = self.conn.execute("""
        SELECT m.year_released, AVG(CAST(r.rating_val AS DOUBLE)) AS average_rating
        FROM movies m
        JOIN reviews r ON m.movie_title_formatted = r.movie_title
        GROUP BY m.year_released
        ORDER BY m.year_released
        """).fetchdf().to_dict(orient='records')

        longest_streak = self.conn.execute("""
        WITH DateDiffs AS (
            SELECT
                user_id,
                rating_date,
                LAG(rating_date) OVER (PARTITION BY user_id ORDER BY rating_date) AS prev_date
            FROM
                reviews
        ),
        Streaks AS (
            SELECT
                user_id,
                rating_date,
                CASE
                    WHEN prev_date IS NULL OR DATEDIFF(
                        'days',
                        CAST(SUBSTR(prev_date, 7, 4) || '-' ||
                        SUBSTR(prev_date, 4, 2) || '-' ||
                        SUBSTR(prev_date, 1, 2) AS DATE),
                        CAST(SUBSTR(rating_date, 7, 4) || '-' ||
                        SUBSTR(rating_date, 4, 2) || '-' ||
                        SUBSTR(rating_date, 1, 2) AS DATE)
                    ) > 1 THEN 1
                    ELSE 0
                END AS new_streak
            FROM
                DateDiffs
        ),
        StreakGroups AS (
            SELECT
                user_id,
                rating_date,
                SUM(new_streak) OVER (PARTITION BY user_id ORDER BY rating_date) AS streak_group
            FROM
                Streaks
        ),
        StreakLengths AS (
            SELECT
                user_id,
                streak_group,
                COUNT(*) AS streak_length
            FROM
                StreakGroups
            GROUP BY
                user_id, streak_group
        ),
        MaxStreak AS (
            SELECT
                MAX(streak_length) AS longest_streak
            FROM
                StreakLengths
        )

        SELECT longest_streak FROM MaxStreak;


        """).fetchone()[0]

        average_rating_decade = self.conn.execute("""
        SELECT
            FLOOR(year_released / 10) * 10 AS decade,
            AVG(CAST(rating_val AS INTEGER)) AS average_rating
        FROM
            reviews
        JOIN
            movies ON reviews.movie_title = movies.movie_title_formatted
        GROUP BY
            FLOOR(year_released / 10) * 10
        ORDER BY
            decade;
        """).fetchdf().to_dict(orient='records')

        average_watched_per_day_of_week = self.conn.execute("""
        SELECT
            EXTRACT(ISODOW FROM rating_date) AS day_of_week,
            COUNT(*) / COUNT(DISTINCT rating_date) AS average_movies_watched
        FROM reviews
        GROUP BY day_of_week
        ORDER BY day_of_week;
        """).fetchdf().to_dict(orient='records')

        top_10_movies_decade = self.conn.execute("""
        WITH DecadeMovies AS (
            SELECT
                movies.movie_title,
                movies.year_released,
                FLOOR(movies.year_released / 10) * 10 AS decade,
                AVG(CAST(reviews.rating_val AS INTEGER)) AS average_rating
            FROM
                reviews
            JOIN
                movies ON reviews.movie_title = movies.movie_title_formatted
            GROUP BY
                movies.movie_title, movies.year_released
        ),
        RankedMovies AS (
            SELECT
                movie_title,
                year_released,
                decade,
                average_rating,
                RANK() OVER (PARTITION BY decade ORDER BY average_rating DESC) AS rating_rank
            FROM
                DecadeMovies
        )

        SELECT
            decade,
            movie_title,
            year_released,
            average_rating
        FROM
            RankedMovies
        WHERE
            rating_rank <= 10
        ORDER BY
            decade, average_rating DESC;

        """).fetchdf().to_dict(orient='records')

        top_10_most_watched = self.conn.execute("""
        SELECT
            movie_title,
            COUNT(*) AS watch_count
        FROM
            reviews
        GROUP BY
            movie_title
        ORDER BY
            watch_count DESC
        LIMIT 10;
        """).fetchdf().to_dict(orient='records')

        top_10_greater_than_average_rating = self.conn.execute("""
        SELECT DISTINCT
            r.movie_title,
            r.rating_val,
            m.vote_average,
            (CAST(r.rating_val AS FLOAT) - m.vote_average) AS margin
        FROM
            reviews r
        JOIN
            movies m ON r.movie_title = m.movie_title_formatted
        WHERE
            CAST(r.rating_val AS FLOAT) > m.vote_average
        ORDER BY
            margin DESC
        LIMIT 10;
        """).fetchdf().to_dict(orient='records')

        top_10_lower_than_average_rating = self.conn.execute("""
        SELECT DISTINCT
            r.movie_title,
            r.rating_val,
            m.vote_average,
            (CAST(r.rating_val AS FLOAT) - m.vote_average) AS margin
        FROM
            reviews r
        JOIN
            movies m ON r.movie_title = m.movie_title_formatted
        WHERE
            CAST(r.rating_val AS FLOAT) < m.vote_average
        ORDER BY
            margin ASC
        LIMIT 10;
        """).fetchdf().to_dict(orient='records')

        top_10_production_country_by_watch_count = self.conn.execute("""
        SELECT country, COUNT(*) AS count
        FROM (
            SELECT TRIM(unnested_country) AS country
            FROM (
                SELECT UNNEST(SPLIT(REPLACE(REPLACE(production_countries, '[', ''), ']', ''), ',')) AS unnested_country
                FROM movies
            ) AS t
        ) AS countries
        GROUP BY country
        ORDER BY count DESC
        LIMIT 10
        """).fetchdf().to_dict(orient='records')

        top_10_spoken_language_by_watch_count = self.conn.execute("""
        SELECT lang, COUNT(*) AS count
        FROM (
            SELECT TRIM(unnested_lang) AS lang
            FROM (
                SELECT UNNEST(SPLIT(REPLACE(REPLACE(spoken_languages, '[', ''), ']', ''), ',')) AS unnested_lang
                FROM movies
            ) AS t
        ) AS languages
        GROUP BY lang
        ORDER BY count DESC
        LIMIT 10
        """).fetchdf().to_dict(orient='records')

        top_10_production_country_by_average_rating = self.conn.execute("""
        SELECT
            unnested_country,
            AVG(CAST(r.rating_val AS FLOAT)) AS average_rating
        FROM (
            SELECT
                TRIM(UNNEST(SPLIT(REPLACE(REPLACE(m.production_countries, '[', ''), ']', ''), ',')))
                AS unnested_country,
                m.movie_title_formatted
            FROM movies m
        ) AS countries
        JOIN reviews r ON countries.movie_title_formatted = r.movie_title
        GROUP BY unnested_country
        ORDER BY average_rating DESC
        LIMIT 10
        """).fetchdf().to_dict(orient='records')

        top_10_spoken_countries_by_average_rating = self.conn.execute("""
        SELECT
            unnested_lang,
            AVG(CAST(r.rating_val AS FLOAT)) AS average_rating
        FROM (
            SELECT
                TRIM(UNNEST(SPLIT(REPLACE(REPLACE(m.spoken_languages, '[', ''), ']', ''), ','))) AS unnested_lang,
                m.movie_title_formatted
            FROM movies m
        ) AS languages
        JOIN reviews r ON languages.movie_title_formatted = r.movie_title
        GROUP BY unnested_lang
        ORDER BY average_rating DESC
        LIMIT 10
        """).fetchdf().to_dict(orient='records')

        top_10_genres_by_watch_count = self.conn.execute("""
        SELECT
            unnested_genre,
            COUNT(*) AS watch_count
        FROM (
            SELECT
                UNNEST(SPLIT(REPLACE(REPLACE(genres, '[', ''), ']', ''), ',')) AS unnested_genre,
                movies.movie_title_formatted
            FROM movies
        ) AS genre_expansion
        JOIN reviews ON genre_expansion.movie_title_formatted = reviews.movie_title
        GROUP BY
            unnested_genre
        ORDER BY
            watch_count DESC
        LIMIT 10;
        """).fetchdf().to_dict(orient='records')

        top_10_themes_by_watch_count = self.conn.execute("""
        SELECT
            unnested_themes,
            COUNT(*) AS watch_count
        FROM (
            SELECT
                UNNEST(SPLIT(REPLACE(REPLACE(themes, '[', ''), ']', ''), ',')) AS unnested_themes,
                movies.movie_title_formatted
            FROM movies
        ) AS theme_expansion
        JOIN reviews ON theme_expansion.movie_title_formatted = reviews.movie_title
        GROUP BY
            unnested_themes
        ORDER BY
            watch_count DESC
        LIMIT 10;
        """).fetchdf().to_dict(orient='records')

        top_10_nanogenres_by_watch_count = self.conn.execute("""
                SELECT
            unnested_nanogenres,
            COUNT(*) AS watch_count
        FROM (
            SELECT
                UNNEST(SPLIT(REPLACE(REPLACE(nanogenres, '[', ''), ']', ''), ',')) AS unnested_nanogenres,
                movies.movie_title_formatted
            FROM movies
        ) AS nanogenre_expansion
        JOIN reviews ON nanogenre_expansion.movie_title_formatted = reviews.movie_title
        GROUP BY
            unnested_nanogenres
        ORDER BY
            watch_count DESC
        LIMIT 10;
        """).fetchdf().to_dict(orient='records')

        top_10_genres_by_watch_count = self.conn.execute("""
                SELECT
                    unnested_genre,
                    COUNT(*) AS watch_count
                FROM (
                    SELECT
                        UNNEST(SPLIT(REPLACE(REPLACE(genres, '[', ''), ']', ''), ',')) AS unnested_genre,
                        movies.movie_title_formatted
                    FROM movies
                ) AS genre_expansion
                JOIN reviews ON genre_expansion.movie_title_formatted = reviews.movie_title
                GROUP BY
                    unnested_genre
                ORDER BY
                    watch_count DESC
                LIMIT 10;
                """).fetchdf().to_dict(orient='records')

        top_10_themes_by_watch_count = self.conn.execute("""
                SELECT
                    unnested_themes,
                    COUNT(*) AS watch_count
                FROM (
                    SELECT
                        UNNEST(SPLIT(REPLACE(REPLACE(themes, '[', ''), ']', ''), ',')) AS unnested_themes,
                        movies.movie_title_formatted
                    FROM movies
                ) AS themes_expansion
                JOIN reviews ON themes_expansion.movie_title_formatted = reviews.movie_title
                GROUP BY
                    unnested_themes
                ORDER BY
                    watch_count DESC
                LIMIT 10;
                """).fetchdf().to_dict(orient='records')

        top_10_genres_by_average_rating = self.conn.execute("""
            WITH SplitGenres AS (
                SELECT
                    m.movie_title,
                    UNNEST(SPLIT(REPLACE(REPLACE(genres, '[', ''), ']', ''), ',')) AS unnested_genre,
                    r.rating_val
                FROM movies m
                JOIN reviews r ON m.movie_title_formatted = r.movie_title
                ),
                AvgRatings AS (
                    SELECT
                        unnested_genre AS genre,
                        AVG(CAST(rating_val AS FLOAT)) AS avg_rating
                    FROM SplitGenres
                    GROUP BY genre
                )
                SELECT
                    genre,
                    avg_rating
                FROM AvgRatings
                ORDER BY avg_rating DESC
                LIMIT 10;
                """).fetchdf().to_dict(orient='records')

        top_10_nanogenres_by_average_rating = self.conn.execute("""
                    WITH SplitNanogenres AS (
                        SELECT
                            m.movie_title,
                            UNNEST(SPLIT(REPLACE(REPLACE(nanogenres, '[', ''), ']', ''), ',')) AS unnested_nanogenre,
                            r.rating_val
                        FROM movies m
                        JOIN reviews r ON m.movie_title_formatted = r.movie_title
                        ),
                        AvgRatings AS (
                            SELECT
                                unnested_nanogenre AS nanogenre,
                                AVG(CAST(rating_val AS FLOAT)) AS avg_rating
                            FROM SplitNanogenres
                            GROUP BY nanogenre
                        )
                        SELECT
                            nanogenre,
                            avg_rating
                        FROM AvgRatings
                        ORDER BY avg_rating DESC
                        LIMIT 10;
                        """).fetchdf().to_dict(orient='records')

        top_10_themes_by_average_rating = self.conn.execute("""
        WITH SplitThemes AS (
            SELECT
                m.movie_title,
                UNNEST(SPLIT(REPLACE(REPLACE(themes, '[', ''), ']', ''), ',')) AS unnested_themes,
                r.rating_val
            FROM movies m
            JOIN reviews r ON m.movie_title_formatted = r.movie_title
        ),
        AvgRatings AS (
            SELECT
                unnested_themes AS theme,
                AVG(CAST(rating_val AS FLOAT)) AS avg_rating
            FROM SplitThemes
            GROUP BY theme
        )
        SELECT
            theme,
            avg_rating
        FROM AvgRatings
        ORDER BY avg_rating DESC
        LIMIT 10;
                        """).fetchdf().to_dict(orient='records')

        return {"movies_reviewed": movies_reviewed, "shows_reviewed": shows_reviewed, "hours_watched": hours_watched,
                "most_common_countries": most_common_countries, "mean_daily_reviews": mean_daily_reviews,
                "number_daily_reviews_over_mean": number_daily_reviews_over_mean,
                "logged_per_release_year": logged_per_release_year, "logged_per_year": logged_per_year,
                "average_rating_per_year": average_rating_per_year, "longest_streak": longest_streak,
                "average_rating_decade": average_rating_decade, "top_10_movies_decade": top_10_movies_decade,
                "top_10_most_watched": top_10_most_watched,
                "top_10_greater_than_average_rating": top_10_greater_than_average_rating,
                "top_10_lower_than_average_rating": top_10_lower_than_average_rating,
                "top_10_production_country_by_watch_count": top_10_production_country_by_watch_count,
                "top_10_spoken_language_by_watch_count": top_10_spoken_language_by_watch_count,
                "top_10_production_country_by_average_rating": top_10_production_country_by_average_rating,
                "top_10_spoken_countries_by_average_rating": top_10_spoken_countries_by_average_rating,
                "top_10_genres_by_watch_count": top_10_genres_by_watch_count,
                "top_10_themes_by_watch_count": top_10_themes_by_watch_count,
                "top_10_nanogenres_by_watch_count": top_10_nanogenres_by_watch_count,
                "top_10_genres_by_average_rating": top_10_genres_by_average_rating,
                "top_10_nanogenres_by_average_rating": top_10_nanogenres_by_average_rating,
                "top_10_themes_by_average_rating": top_10_themes_by_average_rating,
                "average_watched_per_day_of_week": average_watched_per_day_of_week}

    def close(self):
        self.conn.close()
