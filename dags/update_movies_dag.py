import sys
sys.path.insert(0, "/root/letterboxd-movie-rec")

import math
import asyncio
from datetime import datetime, timedelta

from airflow.decorators import dag, task
from dotenv import load_dotenv
from app_logger.app_logger import setup_logger

load_dotenv("/root/letterboxd-movie-rec/.env")

from database.mongodb_client import MongoDBClient
from processing.scraping.movies_scraping import MoviesScraping

logger = setup_logger("/root/letterboxd-movie-rec/logs/update_movies_dag.log", "UpdateMoviesDAG")

MISSING_FIELDS = [
    "histogram",
    "poster_url",
    "lb_rating",
    "genres",
    "runtime",
    "overview",
    "themes",
    "nanogenres",
]

LETTERBOXD_FIELDS = {"poster_url", "lb_rating", "tmdb_id", "imdb_id", "year_released", "histogram"}
TMDB_FIELDS = {"genres", "runtime", "overview", "popularity", "vote_average",
               "vote_count", "release_date", "original_language", "production_countries", "spoken_languages"}

THEMES_FIELDS = {"themes"}
NANOGENRES_FIELDS = {"nanogenres"}


def _is_missing(value) -> bool:
    """Return True when a field value should be considered absent."""
    if value is None:
        return True
    if isinstance(value, (str, list)) and len(value) == 0:
        return True
    if isinstance(value, (int, float)) and value == 0:
        return True
    return False


def _missing_fields_for_movie(movie: dict) -> set:
    return {f for f in MISSING_FIELDS if _is_missing(movie.get(f))}


default_args = {
    "owner": "DijkstraFTW",
    "start_date": datetime(2024, 1, 1),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    "update_movies_dag",
    default_args=default_args,
    schedule="0 4 * * 0",
    catchup=False,
    description="Find movies with incomplete data and fill in missing fields via scraping",
)
def update_movies_dag():

    @task
    def find_incomplete_movies(batch_size: int = 50) -> list[list[dict]]:
        MAX_MAPPED_TASKS = 1024
        logger.info(f"Querying for movies with missing fields: {MISSING_FIELDS}")
        try:
            mongo = MongoDBClient()
            movies = mongo.find_movies_with_missing_fields(MISSING_FIELDS)
            logger.info(f"Found {len(movies)} incomplete movies.")

            movies = [m for m in movies if _missing_fields_for_movie(m)]
            logger.info(f"{len(movies)} movies need updating after filtering.")

            # Ensure we never exceed Airflow's max_map_length limit
            effective_batch_size = max(batch_size, math.ceil(len(movies) / MAX_MAPPED_TASKS))
            num_batches = max(1, math.ceil(len(movies) / effective_batch_size))
            batches = [movies[i * effective_batch_size:(i + 1) * effective_batch_size] for i in range(num_batches)]
            logger.info(f"Split into {len(batches)} batches of up to {effective_batch_size} (adjusted from {batch_size}).")
            return batches
        except Exception as e:
            logger.error(f"Error finding incomplete movies: {e}", exc_info=True)
            raise

    @task
    def scrape_and_update(batch: list[dict]):
        logger.info(f"Processing batch of {len(batch)} movies.")

        async def _run():
            mongo = MongoDBClient()
            movie_slugs = [m["movie_title_formatted"] for m in batch]

            scraper = MoviesScraping(movie_slugs, max_concurrent=2, requests_per_second=1)
            async with scraper:

                for movie in batch:
                    slug = movie["movie_title_formatted"]
                    missing = _missing_fields_for_movie(movie)
                    logger.info(f"[{slug}] Missing fields: {missing}")

                    update = {}

                    needs_lb = bool(missing & LETTERBOXD_FIELDS)
                    if needs_lb:
                        logger.info(f"[{slug}] Scraping Letterboxd main page.")
                        lb_data = await scraper.get_letterboxd_movies(
                            scraper.movies_url.format(slug), slug
                        )
                        if lb_data:
                            for field in LETTERBOXD_FIELDS:
                                if field in missing and not _is_missing(lb_data.get(field)):
                                    update[field] = lb_data[field]
                            if lb_data.get("tmdb_id"):
                                movie["tmdb_id"] = lb_data["tmdb_id"]
                            if lb_data.get("type"):
                                movie["type"] = lb_data["type"]

                    needs_tmdb = bool(missing & TMDB_FIELDS)
                    tmdb_id = movie.get("tmdb_id") or update.get("tmdb_id")
                    movie_type = movie.get("type", "none")
                    if needs_tmdb and tmdb_id and movie_type != "none":
                        logger.info(f"[{slug}] Scraping TMDB (id={tmdb_id}, type={movie_type}).")
                        tmdb_data = await scraper.fetch_themoviedb_data(
                            {"tmdb_id": tmdb_id}, movie_type
                        )
                        if tmdb_data:
                            for field in TMDB_FIELDS:
                                if field in missing and not _is_missing(tmdb_data.get(field)):
                                    update[field] = tmdb_data[field]

                    if "themes" in missing:
                        logger.info(f"[{slug}] Scraping Letterboxd themes.")
                        result = await scraper.get_movie_genres(slug, "themes")
                        if not _is_missing(result.get("themes")):
                            update["themes"] = result["themes"]

                    if "nanogenres" in missing:
                        logger.info(f"[{slug}] Scraping Letterboxd nanogenres.")
                        result = await scraper.get_movie_genres(slug, "nanogenres")
                        if not _is_missing(result.get("nanogenres")):
                            update["nanogenres"] = result["nanogenres"]

                    if update:
                        update["data_last_updated"] = datetime.utcnow()
                        mongo.update_movie(slug, update)
                        logger.info(f"[{slug}] Updated {list(update.keys())}.")
                    else:
                        logger.warning(f"[{slug}] Nothing to update after scraping.")

        try:
            asyncio.run(_run())
        except Exception as e:
            logger.error(f"Error in scrape_and_update batch: {e}", exc_info=True)
            raise

    batches = find_incomplete_movies()
    scrape_and_update.expand(batch=batches)


update_movies_dag = update_movies_dag()
