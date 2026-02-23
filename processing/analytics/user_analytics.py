import json
import os

import duckdb
import pandas as pd

from database.mongodb_client import MongoDBClient
from app_logger.app_logger import setup_logger

logger = setup_logger("/root/letterboxd-movie-rec/logs/user_analytics.log", "UserAnalytics")


class UserAnalytics:
    """
    Class to perform analytics on user movie reviews and history data using DuckDB
    """

    DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "user_analytics.db")

    def __init__(self, db_path=None, reviews=None, movies=None):
        db_path = db_path or self.DEFAULT_DB_PATH
        if os.path.exists(db_path):
            os.remove(db_path)
        if os.path.exists(str(db_path) + ".wal"):
            os.remove(str(db_path) + ".wal")
        self.conn = duckdb.connect(db_path)
        self.cur = self.conn.cursor()
        self.user_reviews = pd.DataFrame(reviews)
        if not self.user_reviews.empty:
            self.user_reviews = self.user_reviews.astype({
                'movie_title': str,
                'rating_date': str,
                'rating_val': 'float64',
                'user_id': str,
                'is_rewatch': bool,
                'is_review': bool,
                'is_liked' : bool
            })
        self.user_movies = pd.DataFrame(movies)
        if not self.user_movies.empty:
            # Serialize native Python objects to JSON strings before astype converts them to repr
            for col, empty in (('histogram', '{}'), ('themes', '[]'), ('nanogenres', '[]')):
                if col in self.user_movies.columns:
                    self.user_movies[col] = self.user_movies[col].apply(
                        lambda v, e=empty: json.dumps(v) if isinstance(v, (dict, list)) else (v if isinstance(v, str) else e)
                    )
            self.user_movies = self.user_movies.astype({
                'movie_title_formatted': str,
                'movie_title': str,
                'type': str,
                'year_released': 'Int64',
                'imdb_link': str,
                'tmdb_link': str,
                'imdb_id': str,
                'tmdb_id': str,
                'lb_rating': 'float64',
                'histogram': str,
                'poster_url': str,
                'genres': str,
                'production_countries': str,
                'spoken_languages': str,
                'popularity': 'float64',
                'overview': str,
                'runtime': 'Int64',
                'vote_average': 'float64',
                'vote_count': 'Int64',
                'release_date': 'datetime64[ns]',
                'original_language': str,
                'last_updated': 'datetime64[ns]',
            })
        mongo_client = MongoDBClient()
        all_ratings = mongo_client.read_all_ratings()
        self.set_all_ratings_table(all_ratings)

    def set_user_history_reviews(self):
        """
        Sets the user history reviews table in duckdb
        """
        self.conn.register('reviews', self.user_reviews)

    def set_user_history_movies(self):
        """
        Sets the user history movies table in duckdb
        """
        self.conn.register('movies', self.user_movies)
        
    def set_all_ratings_table(self, all_ratings):
        """
        Loads all ratings into DuckDB for cohort analysis
        """
        all_ratings_df = pd.DataFrame(all_ratings)
        all_ratings_df = all_ratings_df.astype({
            'movie_title': str,
            'rating_val': float,
            'user_id': str,
            'is_review': bool
        })

        self.conn.register('all_reviews', all_ratings_df)

    def get_basic_metrics(self):
        """
        Returns basic metrics about the user's reviews and movies history.
        Delegates to private methods for each metric group.
        """
        return {
            "movies_reviewed": self._movies_reviewed(),
            "shows_reviewed": self._shows_reviewed(),
            "minutes_watched": self._minutes_watched(),
            "first_watches": self._first_watches(),
            "rewatches": self._rewatches(),
            "most_common_countries": self._most_common_countries(),
            "max_films_in_a_day": self._max_films_in_a_day(),
            "logged_per_release_year": self._logged_per_release_year(),
            "logged_per_year": self._logged_per_year(),
            "average_rating_per_year": self._average_rating_per_year(),
            "longest_streak": self._longest_streak(),
            "average_rating_decade": self._average_rating_decade(),
            "top_10_movies_decade": self._top_10_movies_decade(),
            "top_10_most_watched": self._top_10_most_watched(),
            "top_10_greater_than_average_rating": self._top_10_greater_than_average_rating(),
            "top_10_lower_than_average_rating": self._top_10_lower_than_average_rating(),
            "top_10_production_country_by_watch_count": self._top_10_production_country_by_watch_count(),
            "top_10_spoken_language_by_watch_count": self._top_10_spoken_language_by_watch_count(),
            "top_10_production_country_by_average_rating": self._top_10_production_country_by_average_rating(),
            "top_10_spoken_countries_by_average_rating": self._top_10_spoken_countries_by_average_rating(),
            "top_10_genres_by_watch_count": self._top_10_genres_by_watch_count(),
            "top_10_themes_by_watch_count": self._top_10_themes_by_watch_count(),
            "top_10_nanogenres_by_watch_count": self._top_10_nanogenres_by_watch_count(),
            "top_10_genres_by_average_rating": self._top_10_genres_by_average_rating(),
            "top_10_nanogenres_by_average_rating": self._top_10_nanogenres_by_average_rating(),
            "top_10_themes_by_average_rating": self._top_10_themes_by_average_rating(),
            "average_watched_per_day_of_week": self._average_watched_per_day_of_week(),
            "taste_alignment": self._taste_alignment(),
        }

    def _movies_reviewed(self):
        return self.conn.execute("""
            SELECT COUNT(*) FROM movies WHERE type = 'movie';
        """).fetchone()[0]

    def _shows_reviewed(self):
        return self.conn.execute("""
            SELECT COUNT(*) FROM movies WHERE type = 'shows';
        """).fetchone()[0]

    def _minutes_watched(self):
        return self.conn.execute("""
            SELECT SUM(runtime) FROM movies;
        """).fetchone()[0]

    def _first_watches(self):
        return self.conn.execute("""
            SELECT COUNT(*) FROM reviews WHERE is_rewatch = FALSE;
        """).fetchone()[0]

    def _rewatches(self):
        return self.conn.execute("""
            SELECT COUNT(*) FROM reviews WHERE is_rewatch = TRUE;
        """).fetchone()[0]

    def _most_common_countries(self):
        return self.conn.execute("""
            SELECT country, COUNT(*) AS count
            FROM (
                SELECT TRIM(REPLACE(REPLACE(unnested_country, '''', ''), '"', '')) AS country
                FROM (
                    SELECT UNNEST(SPLIT(REPLACE(REPLACE(production_countries, '[', ''), ']', ''), ','))
                    AS unnested_country
                    FROM movies
                ) AS t
                WHERE TRIM(unnested_country) != '' AND unnested_country IS NOT NULL
            ) AS countries
            GROUP BY country
            ORDER BY count DESC
        """).fetchdf().to_dict(orient='records')

    def _mean_daily_reviews(self):
        return self.conn.execute("""
            SELECT ROUND(AVG(num_reviews)) AS mean
            FROM (
                SELECT COUNT(*) AS num_reviews
                FROM reviews
                GROUP BY rating_date
            ) AS review_counts
        """).fetchone()[0]

    def _max_films_in_a_day(self):
        return self.conn.execute("""
            SELECT MAX(num_reviews) AS max_films
            FROM (
                SELECT COUNT(*) AS num_reviews
                FROM reviews
                GROUP BY rating_date
            ) AS daily_counts
        """).fetchone()[0] or 0

    def _logged_per_release_year(self):
        return self.conn.execute("""
            WITH movie_years AS (
                SELECT year_released AS year, COUNT(*) AS num_movies
                FROM movies
                GROUP BY year_released
            ),
            all_years AS (
                SELECT MIN(year_released) AS min_year, MAX(year_released) AS max_year
                FROM movies
            ),
            year_span AS (
                SELECT UNNEST(generate_series((SELECT min_year FROM all_years), (SELECT max_year FROM all_years))) AS year
            )
            SELECT
                y.year,
                COALESCE(m.num_movies, 0) AS num_movies
            FROM year_span y
            LEFT JOIN movie_years m ON y.year = m.year
            ORDER BY y.year;
        """).fetchdf().to_dict(orient='records')

    def _logged_per_year(self):
        return self.conn.execute("""
            WITH review_years AS (
                SELECT CAST(SUBSTRING(rating_date, 1, 4) AS INT) AS year, COUNT(*) AS num_reviews
                FROM reviews
                GROUP BY CAST(SUBSTRING(rating_date, 1, 4) AS INT)
            ),
            all_years AS (
                SELECT MIN(CAST(SUBSTRING(rating_date, 1, 4) AS INT)) AS min_year,
                       MAX(CAST(SUBSTRING(rating_date, 1, 4) AS INT)) AS max_year
                FROM reviews
            ),
            year_span AS (
                SELECT UNNEST(generate_series((SELECT min_year FROM all_years), (SELECT max_year FROM all_years))) AS year
            )
            SELECT
                y.year,
                COALESCE(r.num_reviews, 0) AS num_reviews
            FROM year_span y
            LEFT JOIN review_years r ON y.year = r.year
            ORDER BY y.year;
        """).fetchdf().to_dict(orient='records')

    def _average_rating_per_year(self):
        return self.conn.execute("""
            SELECT m.year_released, AVG(CAST(r.rating_val AS DOUBLE)) AS average_rating
            FROM movies m
            JOIN reviews r ON m.movie_title_formatted = r.movie_title
            GROUP BY m.year_released
            ORDER BY m.year_released
        """).fetchdf().to_dict(orient='records')

    def _longest_streak(self):
        return self.conn.execute("""
            WITH DateDiffs AS (
                SELECT
                    user_id,
                    rating_date,
                    LAG(rating_date) OVER (PARTITION BY user_id ORDER BY rating_date) AS prev_date
                FROM reviews
            ),
            Streaks AS (
                SELECT
                    user_id,
                    rating_date,
                    CASE
                        WHEN prev_date IS NULL OR DATEDIFF(
                            'days',
                            CAST(prev_date AS DATE),
                            CAST(rating_date AS DATE)
                        ) > 1 THEN 1
                        ELSE 0
                    END AS new_streak
                FROM DateDiffs
            ),
            StreakGroups AS (
                SELECT
                    user_id,
                    rating_date,
                    SUM(new_streak) OVER (PARTITION BY user_id ORDER BY rating_date) AS streak_group
                FROM Streaks
            ),
            StreakLengths AS (
                SELECT
                    user_id,
                    streak_group,
                    COUNT(*) AS streak_length
                FROM StreakGroups
                GROUP BY user_id, streak_group
            ),
            MaxStreak AS (
                SELECT MAX(streak_length) AS longest_streak
                FROM StreakLengths
            )
            SELECT longest_streak FROM MaxStreak;
        """).fetchone()[0]

    def _average_rating_decade(self):
        return self.conn.execute("""
            SELECT
                FLOOR(year_released / 10) * 10 AS decade,
                AVG(CAST(rating_val AS DOUBLE)) AS average_rating
            FROM reviews
            JOIN movies ON reviews.movie_title = movies.movie_title_formatted
            WHERE year_released > 0
            GROUP BY FLOOR(year_released / 10) * 10
            ORDER BY decade;
        """).fetchdf().to_dict(orient='records')

    def _average_watched_per_day_of_week(self):
        return self.conn.execute("""
            SELECT
                EXTRACT(ISODOW FROM CAST(rating_date AS DATE)) AS day_of_week,
                COUNT(*) / COUNT(DISTINCT rating_date) AS average_movies_watched
            FROM reviews
            GROUP BY day_of_week
            ORDER BY day_of_week;
        """).fetchdf().to_dict(orient='records')

    def _top_10_movies_decade(self):
        return self.conn.execute("""
            WITH DecadeMovies AS (
                SELECT
                    movies.movie_title,
                    movies.year_released,
                    FLOOR(movies.year_released / 10) * 10 AS decade,
                    AVG(CAST(reviews.rating_val AS DOUBLE)) AS average_rating
                FROM reviews
                JOIN movies ON reviews.movie_title = movies.movie_title_formatted
                GROUP BY movies.movie_title, movies.year_released
            ),
            RankedMovies AS (
                SELECT
                    movie_title,
                    year_released,
                    decade,
                    average_rating,
                    RANK() OVER (PARTITION BY decade ORDER BY average_rating DESC) AS rating_rank
                FROM DecadeMovies
            )
            SELECT decade, movie_title, year_released, average_rating
            FROM RankedMovies
            WHERE rating_rank <= 10
            ORDER BY decade, average_rating DESC;
        """).fetchdf().to_dict(orient='records')

    def _top_10_most_watched(self):
        return self.conn.execute("""
            SELECT m.movie_title AS title, COUNT(*) AS count, m.poster_url
            FROM reviews r
            JOIN movies m ON r.movie_title = m.movie_title_formatted
            GROUP BY m.movie_title, m.poster_url
            ORDER BY count DESC
            LIMIT 10;
        """).fetchdf().to_dict(orient='records')

    def _top_10_greater_than_average_rating(self):
        return self.conn.execute("""
            SELECT DISTINCT
                m.movie_title,
                m.movie_title_formatted,
                r.rating_val,
                m.lb_rating,
                m.poster_url,
                m.histogram,
                CAST(m.runtime AS VARCHAR) AS runtime,
                m.genres,
                m.year_released,
                (CAST(r.rating_val AS FLOAT) - m.lb_rating * 2) AS margin
            FROM reviews r
            JOIN movies m ON r.movie_title = m.movie_title_formatted
            WHERE CAST(r.rating_val AS FLOAT) > m.lb_rating * 2
              AND m.year_released > 0
              AND m.lb_rating > 0
            ORDER BY margin DESC
            LIMIT 10;
        """).fetchdf().to_dict(orient='records')

    def _top_10_lower_than_average_rating(self):
        return self.conn.execute("""
            SELECT DISTINCT
                m.movie_title,
                m.movie_title_formatted,
                r.rating_val,
                m.lb_rating,
                m.poster_url,
                m.histogram,
                CAST(m.runtime AS VARCHAR) AS runtime,
                m.genres,
                m.year_released,
                (CAST(r.rating_val AS FLOAT) - m.lb_rating * 2) AS margin
            FROM reviews r
            JOIN movies m ON r.movie_title = m.movie_title_formatted
            WHERE CAST(r.rating_val AS FLOAT) < m.lb_rating * 2
              AND m.year_released > 0
              AND m.lb_rating > 0
            ORDER BY margin ASC
            LIMIT 10;
        """).fetchdf().to_dict(orient='records')

    def _top_10_production_country_by_watch_count(self):
        return self.conn.execute("""
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
            LIMIT 10;
        """).fetchdf().to_dict(orient='records')

    def _top_10_spoken_language_by_watch_count(self):
        return self.conn.execute("""
            SELECT lang, COUNT(*) AS count
            FROM (
                SELECT TRIM(REPLACE(unnested_lang, '''', '')) AS lang
                FROM (
                    SELECT UNNEST(SPLIT(REPLACE(REPLACE(spoken_languages, '[', ''), ']', ''), ',')) AS unnested_lang
                    FROM movies
                ) AS t
            ) AS languages
            WHERE lang != ''
            GROUP BY lang
            ORDER BY count DESC
            LIMIT 10;
        """).fetchdf().to_dict(orient='records')

    def _top_10_production_country_by_average_rating(self):
        return self.conn.execute("""
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
            LIMIT 10;
        """).fetchdf().to_dict(orient='records')

    def _top_10_spoken_countries_by_average_rating(self):
        return self.conn.execute("""
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
            LIMIT 10;
        """).fetchdf().to_dict(orient='records')

    def _top_10_genres_by_watch_count(self):
        return self.conn.execute("""
            SELECT
                unnested_genre,
                COUNT(*) AS watch_count
            FROM (
                SELECT
                    TRIM(REPLACE(REPLACE(UNNEST(SPLIT(REPLACE(REPLACE(genres, '[', ''), ']', ''), ',')), '''', ''), '"', '')) AS unnested_genre,
                    movies.movie_title_formatted
                FROM movies
            ) AS genre_expansion
            JOIN reviews ON genre_expansion.movie_title_formatted = reviews.movie_title
            WHERE unnested_genre != ''
            GROUP BY unnested_genre
            ORDER BY watch_count DESC
            LIMIT 10;
        """).fetchdf().to_dict(orient='records')

    def _top_10_themes_by_watch_count(self):
        return self.conn.execute("""
            SELECT
                unnested_themes,
                COUNT(*) AS watch_count
            FROM (
                SELECT
                    TRIM(UNNEST(regexp_extract_all(themes, '"([^"]+)"', 1))) AS unnested_themes,
                    movies.movie_title_formatted
                FROM movies
            ) AS theme_expansion
            JOIN reviews ON theme_expansion.movie_title_formatted = reviews.movie_title
            WHERE unnested_themes != ''
            GROUP BY unnested_themes
            ORDER BY watch_count DESC
            LIMIT 10;
        """).fetchdf().to_dict(orient='records')

    def _top_10_nanogenres_by_watch_count(self):
        return self.conn.execute("""
            SELECT
                unnested_nanogenres,
                COUNT(*) AS watch_count
            FROM (
                SELECT
                    TRIM(UNNEST(regexp_extract_all(nanogenres, '"([^"]+)"', 1))) AS unnested_nanogenres,
                    movies.movie_title_formatted
                FROM movies
            ) AS nanogenre_expansion
            JOIN reviews ON nanogenre_expansion.movie_title_formatted = reviews.movie_title
            WHERE unnested_nanogenres != ''
            GROUP BY unnested_nanogenres
            ORDER BY watch_count DESC
            LIMIT 10;
        """).fetchdf().to_dict(orient='records')

    def _top_10_genres_by_average_rating(self):
        return self.conn.execute("""
            WITH SplitGenres AS (
                SELECT
                    m.movie_title,
                    TRIM(REPLACE(REPLACE(UNNEST(SPLIT(REPLACE(REPLACE(genres, '[', ''), ']', ''), ',')), '''', ''), '"', '')) AS unnested_genre,
                    r.rating_val
                FROM movies m
                JOIN reviews r ON m.movie_title_formatted = r.movie_title
            ),
            AvgRatings AS (
                SELECT
                    unnested_genre AS genre,
                    AVG(CAST(rating_val AS FLOAT)) AS avg_rating
                FROM SplitGenres
                WHERE unnested_genre != ''
                GROUP BY unnested_genre
            )
            SELECT genre, avg_rating
            FROM AvgRatings
            ORDER BY avg_rating DESC
            LIMIT 10;
        """).fetchdf().to_dict(orient='records')

    def _top_10_nanogenres_by_average_rating(self):
        return self.conn.execute("""
            WITH SplitNanogenres AS (
                SELECT
                    m.movie_title,
                    TRIM(UNNEST(regexp_extract_all(nanogenres, '"([^"]+)"', 1))) AS unnested_nanogenre,
                    r.rating_val
                FROM movies m
                JOIN reviews r ON m.movie_title_formatted = r.movie_title
            ),
            AvgRatings AS (
                SELECT
                    unnested_nanogenre AS nanogenre,
                    AVG(CAST(rating_val AS FLOAT)) AS avg_rating
                FROM SplitNanogenres
                WHERE unnested_nanogenre != ''
                GROUP BY nanogenre
            )
            SELECT nanogenre, avg_rating
            FROM AvgRatings
            ORDER BY avg_rating DESC
            LIMIT 10;
        """).fetchdf().to_dict(orient='records')

    def _top_10_themes_by_average_rating(self):
        return self.conn.execute("""
            WITH SplitThemes AS (
                SELECT
                    m.movie_title,
                    TRIM(UNNEST(regexp_extract_all(themes, '"([^"]+)"', 1))) AS unnested_themes,
                    r.rating_val
                FROM movies m
                JOIN reviews r ON m.movie_title_formatted = r.movie_title
            ),
            AvgRatings AS (
                SELECT
                    unnested_themes AS theme,
                    AVG(CAST(rating_val AS FLOAT)) AS avg_rating
                FROM SplitThemes
                WHERE unnested_themes != ''
                GROUP BY theme
            )
            SELECT theme, avg_rating
            FROM AvgRatings
            ORDER BY avg_rating DESC
            LIMIT 10;
        """).fetchdf().to_dict(orient='records')
        
    def _taste_alignment(self):
        return self.conn.execute("""
            SELECT
                SUM(CASE WHEN CAST(r.rating_val AS FLOAT) > m.lb_rating * 2 + 0.5 THEN 1 ELSE 0 END) AS above_avg,
                SUM(CASE WHEN ABS(CAST(r.rating_val AS FLOAT) - m.lb_rating * 2) <= 0.5 THEN 1 ELSE 0 END) AS similar_avg,
                SUM(CASE WHEN CAST(r.rating_val AS FLOAT) < m.lb_rating * 2 - 0.5 THEN 1 ELSE 0 END) AS below_avg
            FROM reviews r
            JOIN movies m ON r.movie_title = m.movie_title_formatted
            WHERE m.lb_rating > 0
        """).fetchdf().to_dict(orient='records')[0]

    # ─── Advanced Analytics ────────────────────────────────────────────────

    def get_advanced_metrics(self):
        """
        Returns all advanced metrics for the AdvancedUserMetrics component.
        """
        return {
            "rating_vs_consensus": self._rating_vs_public_consensus(),
            "histogram_superposition": self._histogram_superposition(),
            "popularity_vs_rating": self._popularity_vs_rating(),
            "era_analysis": self._release_era_analysis(),
            "rating_trend": self._rating_trend_over_time(),
            "theme_explorer": self._theme_explorer(),
            "nanogenre_correlations": self._nanogenre_correlations(),
        }

    def _rating_vs_public_consensus(self):
        """
        Scatter plot data: user rating vs public rating, colored by first genre.
        Returns [{title, userRating, publicRating, genre}]
        """
        result = self.conn.execute("""
            SELECT
                m.movie_title AS title,
                m.poster_url AS posterUrl,
                CAST(r.rating_val AS DOUBLE) AS userRating,
                m.lb_rating * 2 AS publicRating,
                TRIM(REPLACE(REPLACE(
                    SPLIT(REPLACE(REPLACE(m.genres, '[', ''), ']', ''), ',')[1],
                    '''', ''), '"', '')) AS genre
            FROM reviews r
            JOIN movies m ON r.movie_title = m.movie_title_formatted
        """).fetchdf().to_dict(orient='records')
        return result

    def _histogram_superposition(self, sample_size=40):
        """
        Rating distribution histogram: user vs averaged community sample.
        Returns [{rating: "1", user: count, community: avg_count}, ...]
        """
        target_user_ids = self.user_reviews['user_id'].unique().tolist()
        if not target_user_ids:
            return [{"rating": str(r), "user": 0, "community": 0} for r in range(1, 11)]
        target_user_id = target_user_ids[0]

        # User's rating distribution
        user_dist = self.conn.execute("""
            SELECT CAST(rating_val AS INTEGER) AS rating, COUNT(*) AS count
            FROM reviews
            GROUP BY CAST(rating_val AS INTEGER)
            ORDER BY rating
        """).fetchdf()

        # Sample random users and get their averaged distribution
        sample_users_df = self.conn.execute(f"""
            SELECT DISTINCT user_id
            FROM all_reviews
            WHERE is_review = TRUE AND user_id != '{target_user_id}'
            ORDER BY RANDOM()
            LIMIT {sample_size}
        """).fetchdf()
        sample_user_ids = sample_users_df['user_id'].tolist()

        if sample_user_ids:
            placeholders = ",".join([f"'{uid}'" for uid in sample_user_ids])
            community_dist = self.conn.execute(f"""
                SELECT rating, ROUND(AVG(count)) AS count FROM (
                    SELECT user_id, CAST(rating_val AS INTEGER) AS rating, COUNT(*) AS count
                    FROM all_reviews
                    WHERE user_id IN ({placeholders}) AND is_review = TRUE
                    GROUP BY user_id, CAST(rating_val AS INTEGER)
                ) per_user
                GROUP BY rating
                ORDER BY rating
            """).fetchdf()
        else:
            community_dist = pd.DataFrame({'rating': range(1, 11), 'count': [0] * 10})

        # Merge into a single list for all ratings 1-10
        result = []
        for rating in range(1, 11):
            user_count = int(user_dist.loc[user_dist['rating'] == rating, 'count'].sum())
            comm_count = int(community_dist.loc[community_dist['rating'] == rating, 'count'].sum())
            result.append({
                "rating": str(rating),
                "user": user_count,
                "community": comm_count,
            })
        return result

    def _popularity_vs_rating(self):
        """
        Scatter plot data: vote_count vs user rating, colored by first genre.
        Returns [{title, voteCount, userRating, genre}]
        """
        result = self.conn.execute("""
            SELECT
                m.movie_title AS title,
                m.poster_url AS posterUrl,
                CAST(JSON_EXTRACT(m.histogram, '$.total') AS INTEGER) AS voteCount,
                CAST(r.rating_val AS DOUBLE) AS userRating,
                TRIM(REPLACE(REPLACE(
                    SPLIT(REPLACE(REPLACE(m.genres, '[', ''), ']', ''), ',')[1],
                    '''', ''), '"', '')) AS genre
            FROM reviews r
            JOIN movies m ON r.movie_title = m.movie_title_formatted
        """).fetchdf().to_dict(orient='records')
        return result

    def _release_era_analysis(self):
        """
        Rating distribution per era (decade bucket).
        Returns [{era, avgRating, count, distribution: [{rating, count}]}]
        """
        eras_df = self.conn.execute("""
            SELECT
                CASE
                    WHEN m.year_released < 1970 THEN 'Pre-1970'
                    ELSE CAST(FLOOR(m.year_released / 10) * 10 AS VARCHAR) || 's'
                END AS era,
                CASE
                    WHEN m.year_released < 1970 THEN 0
                    ELSE CAST(FLOOR(m.year_released / 10) * 10 AS INTEGER)
                END AS era_sort,
                CAST(r.rating_val AS INTEGER) AS rating,
                COUNT(*) AS count
            FROM reviews r
            JOIN movies m ON r.movie_title = m.movie_title_formatted
            GROUP BY era, era_sort, rating
            ORDER BY era_sort, rating
        """).fetchdf()

        result = []
        for (era, era_sort), group in eras_df.groupby(['era', 'era_sort']):
            total_count = int(group['count'].sum())
            weighted_sum = (group['rating'] * group['count']).sum()
            avg_rating = round(float(weighted_sum / total_count), 1) if total_count > 0 else 0
            distribution = [
                {"rating": str(int(row['rating'])), "count": int(row['count'])}
                for _, row in group.iterrows()
            ]
            result.append({
                "era": era,
                "avgRating": avg_rating,
                "count": total_count,
                "distribution": distribution,
            })

        result.sort(key=lambda x: x['era'] if x['era'] != 'Pre-1970' else '0000')
        return result

    def _rating_trend_over_time(self, window=30):
        """
        Rolling average of user ratings over time.
        Returns [{date, rollingAvg, actual}]
        """
        df = self.conn.execute("""
            SELECT
                r.rating_date AS date,
                CAST(r.rating_val AS DOUBLE) AS actual
            FROM reviews r
            ORDER BY r.rating_date
        """).fetchdf()

        if df.empty:
            return []

        df['rollingAvg'] = df['actual'].rolling(window=window, min_periods=1).mean().round(1)

        # Downsample to at most ~50 points for the chart
        step = max(1, len(df) // 50)
        sampled = df.iloc[::step].copy()

        return sampled[['date', 'rollingAvg', 'actual']].to_dict(orient='records')

    def _theme_explorer(self):
        """
        Treemap data: theme name, count, average rating.
        Returns [{name, size, avgRating}]
        """
        result = self.conn.execute("""
            WITH expanded AS (
                SELECT
                    TRIM(unnested_theme) AS theme,
                    CAST(r.rating_val AS DOUBLE) AS rating
                FROM (
                    SELECT
                        UNNEST(regexp_extract_all(m.themes, '"([^"]+)"', 1)) AS unnested_theme,
                        m.movie_title_formatted
                    FROM movies m
                ) t
                JOIN reviews r ON t.movie_title_formatted = r.movie_title
                WHERE TRIM(unnested_theme) != ''
            )
            SELECT
                theme AS name,
                COUNT(*) AS size,
                ROUND(AVG(rating), 1) AS avgRating
            FROM expanded
            GROUP BY theme
            HAVING COUNT(*) >= 2
            ORDER BY size DESC
            LIMIT 30
        """).fetchdf().to_dict(orient='records')
        return result

    def _nanogenre_correlations(self):
        """
        Nanogenre tags correlated with high/low ratings.
        Returns {positive: [{tag, correlation, avgRating, count}], negative: [...]}
        """
        df = self.conn.execute("""
            WITH expanded AS (
                SELECT
                    TRIM(unnested_ng) AS tag,
                    CAST(r.rating_val AS DOUBLE) AS rating
                FROM (
                    SELECT
                        UNNEST(regexp_extract_all(m.nanogenres, '"([^"]+)"', 1)) AS unnested_ng,
                        m.movie_title_formatted
                    FROM movies m
                ) t
                JOIN reviews r ON t.movie_title_formatted = r.movie_title
                WHERE TRIM(unnested_ng) != ''
            )
            SELECT
                tag,
                COUNT(*) AS count,
                ROUND(AVG(rating), 1) AS avgRating,
                ROUND(AVG(CASE WHEN rating >= 8 THEN 1.0 ELSE 0.0 END), 2) AS highRateRatio
            FROM expanded
            GROUP BY tag
            HAVING COUNT(*) >= 3
        """).fetchdf()

        if df.empty:
            return {"positive": [], "negative": []}

        # Compute a correlation proxy: deviation from overall high-rate ratio
        overall_high_ratio = df['highRateRatio'].mean()
        df['correlation'] = (df['highRateRatio'] - overall_high_ratio).round(2)

        # Normalize correlation to [-1, 1] range
        max_abs = df['correlation'].abs().max()
        if max_abs > 0:
            df['correlation'] = (df['correlation'] / max_abs).round(2)

        positive = (
            df.nlargest(10, 'correlation')
            [['tag', 'correlation', 'avgRating', 'count']]
            .to_dict(orient='records')
        )
        negative = (
            df.nsmallest(5, 'correlation')
            [['tag', 'correlation', 'avgRating', 'count']]
            .to_dict(orient='records')
        )

        return {"positive": positive, "negative": negative}

    def close(self):
        self.conn.close()
