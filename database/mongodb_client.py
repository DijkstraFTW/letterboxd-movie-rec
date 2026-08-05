import os
import certifi
import numpy as np
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from app_logger.app_logger import setup_logger

logger = setup_logger("/root/letterboxd-movie-rec/logs/mongodb_client.log", "MongoDBClient")


class MongoDBClient:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDBClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        try:
            self.username = os.getenv('MONGO_USERNAME')
            self.password = os.getenv('MONGO_PASSWORD')
            self.cluster = os.getenv('MONGO_CLUSTER')
            self.database = os.getenv('MONGO_DATABASE')
            self.URI = f"mongodb+srv://{self.username}:{self.password}@{self.cluster}/?retryWrites=true&w=majority"

            self._client = MongoClient(
                self.URI,
                tlsCAFile=certifi.where(),
                maxPoolSize=5,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
            )
            self._client.admin.command('ping')

            self._initialized = True
            logger.info(f"MongoDBClient singleton initialized for database '{self.database}' at cluster '{self.cluster}'.")
        except Exception as e:
            logger.error(f"Error initializing MongoDBClient: {e}", exc_info=True)
            raise

    @property
    def client(self):
        if self._client is None:
            raise RuntimeError("MongoDBClient not properly initialized")
        return self._client

    def open_conn_to_db(self):
        """Deprecated: Returns the singleton client for backward compatibility."""
        logger.warning("open_conn_to_db() is deprecated. Use MongoDBClient().client instead.")
        return self.client

    def close_conn_to_db(self):
        """Deprecated: No-op for backward compatibility. Connection is managed by singleton."""
        logger.warning("close_conn_to_db() is deprecated. Connection is managed by the singleton pattern.")
        return "OK"

    def insert_ratings(self, ratings):
        try:
            collection = self.client[self.database].ratings
            inserted = 0
            for rating in ratings:
                result = collection.update_one(
                    {
                        "user_id": rating["user_id"],
                        "movie_title": rating["movie_title"],
                        "rating_date": rating["rating_date"]
                    },
                    {"$setOnInsert": rating},
                    upsert=True
                )
                if result.upserted_id:
                    inserted += 1
            logger.info(f"Processed {len(ratings)} ratings: {inserted} new, {len(ratings) - inserted} already existing.")
        except Exception as e:
            logger.error(f"Error adding ratings to MongoDB: {e}", exc_info=True)

    def read_all_ratings(self):
        try:
            collection = self.client[self.database].ratings
            projection = {"_id": 0, "movie_title": 1, "rating_val": 1, "user_id": 1,
                          "is_review": 1, "is_liked": 1, "is_rewatch": 1, "rating_date": 1}
            result = list(collection.find({}, projection))
            result = [item for item in result if item["rating_val"] != "rating"]
            logger.info(f"Fetched {len(result)} ratings from MongoDB.")
            return result
        except Exception as e:
            logger.error(f"Error reading ratings from MongoDB: {e}", exc_info=True)
            return []

    def insert_movies(self, movie):
        try:
            collection = self.client[self.database].movies
            collection.insert_one(movie)
            logger.info(f"Inserted movie '{movie.get('movie_title_formatted', 'Unknown')}' into MongoDB.")
        except Exception as e:
            logger.error(f"Error inserting movie '{movie.get('movie_title', 'Unknown')}': {e}", exc_info=True)

    def read_all_movies_title_formatted(self):
        try:
            collection = self.client[self.database].movies
            result = [item["movie_title_formatted"] for item in collection.find({}, {"_id": 0, "movie_title_formatted": 1})]
            logger.info(f"Fetched {len(result)} movie titles from MongoDB.")
            return set(result)
        except Exception as e:
            logger.error(f"Error reading all movies from MongoDB: {e}", exc_info=True)
            return set()

    def read_all_movies(self):
        try:
            collection = self.client[self.database].movies
            projection = {"_id": 0, "movie_title_formatted": 1, "movie_title": 1, "type": 1,
                          "year_released": 1, "imdb_link": 1, "tmdb_link": 1, "imdb_id": 1,
                          "tmdb_id": 1, "poster_url": 1, "genres": 1, "themes": 1, "nanogenres": 1,
                          "production_countries": 1, "spoken_languages": 1, "popularity": 1,
                          "overview": 1, "runtime": 1, "vote_average": 1, "vote_count": 1,
                          "release_date": 1, "original_language": 1, "last_updated": 1}
            result = list(collection.find({}, projection))
            logger.info(f"Fetched {len(result)} movies from MongoDB.")
            return result
        except Exception as e:
            logger.error(f"Error reading all movies from MongoDB: {e}", exc_info=True)
            return []

    def read_all_rated_movies(self):
        try:
            collection = self.client[self.database].ratings
            result = list({item["movie_title"] for item in collection.find({}, {"_id": 0, "movie_title": 1})})
            logger.info(f"Fetched {len(result)} rated movies from MongoDB.")
            return result
        except Exception as e:
            logger.error(f"Error reading rated movies from MongoDB: {e}", exc_info=True)
            return []

    def read_movie(self, movie_title):
        try:
            collection = self.client[self.database].movies
            result = collection.find_one({"movie_title_formatted": movie_title})
            if result:
                result.pop('_id', None)
                logger.info(f"Read movie '{movie_title}' from MongoDB.")
            else:
                logger.warning(f"Movie '{movie_title}' not found in MongoDB.")
            return result
        except Exception as e:
            logger.error(f"Error reading movie '{movie_title}' from MongoDB: {e}", exc_info=True)
            return None

    def read_movies_by_titles(self, movie_titles):
        """
        Fetch multiple movies by their formatted titles (movie_title_formatted) in a single query.
        Efficient for enriching recommendation results.

        :param movie_titles: List of formatted movie titles to fetch (e.g. "dune-part-2")
        :return: List of movie documents
        """
        try:
            collection = self.client[self.database].movies
            projection = {"_id": 0, "movie_title_formatted": 1, "movie_title": 1, "type": 1,
                          "year_released": 1, "imdb_link": 1, "tmdb_link": 1, "imdb_id": 1,
                          "tmdb_id": 1, "poster_url": 1, "lb_rating": 1, "histogram": 1,
                          "genres": 1, "themes": 1, "nanogenres": 1, "production_countries": 1,
                          "spoken_languages": 1, "popularity": 1, "overview": 1, "runtime": 1,
                          "vote_average": 1, "vote_count": 1, "release_date": 1,
                          "original_language": 1, "last_updated": 1}
            results = list(collection.find({"movie_title_formatted": {"$in": movie_titles}}, projection))

            logger.info(f"Fetched {len(results)} movies out of {len(movie_titles)} requested from MongoDB.")
            return results
        except Exception as e:
            logger.error(f"Error reading movies by titles from MongoDB: {e}", exc_info=True)
            return []

    def insert_users(self, users):
        try:
            collection = self.client[self.database].users
            for user in users:
                collection.insert_one(user)
            logger.info(f"Successfully added {len(users)} users to MongoDB.")
        except Exception as e:
            logger.error(f"Error inserting users into MongoDB: {e}", exc_info=True)

    def find_user(self, username):
        try:
            collection = self.client[self.database].users
            result = collection.count_documents({"username": username})
            logger.info(f"Found {result} entries for username '{username}'.")
            return result
        except Exception as e:
            logger.error(f"Error finding user '{username}' in MongoDB: {e}", exc_info=True)
            return None

    def get_user_custom_id(self, username):
        try:
            collection = self.client[self.database].users
            result = collection.find_one({"username": username})
            if result:
                logger.info(f"Retrieved user_id '{result.get('user_id')}' for username '{username}'.")
                return result.get('user_id')
            else:
                logger.warning(f"No user found with username '{username}'.")
                return None
        except Exception as e:
            logger.error(f"Error getting user_id for '{username}' from MongoDB: {e}", exc_info=True)
            return None

    def get_reviews_by_user_id(self, user_id):
        try:
            collection = self.client[self.database].ratings
            result = list(collection.find({"user_id": str(user_id), "rating_val": {"$ne": 0}}))
            for item in result:
                item.pop('_id', None)
            logger.info(f"Fetched {len(result)} reviews for user_id '{user_id}'.")
            return result
        except Exception as e:
            logger.error(f"Error getting reviews for user_id '{user_id}' from MongoDB: {e}", exc_info=True)
            return []

    def delete_all_ratings(self):
        try:
            collection = self.client[self.database].ratings
            deleted_count = collection.delete_many({}).deleted_count
            logger.info(f"Deleted {deleted_count} ratings from MongoDB.")
        except Exception as e:
            logger.error(f"Error deleting all ratings from MongoDB: {e}", exc_info=True)

    def delete_all_users(self):
        try:
            collection = self.client[self.database].users
            deleted_count = collection.delete_many({}).deleted_count
            logger.info(f"Deleted {deleted_count} users from MongoDB.")
        except Exception as e:
            logger.error(f"Error deleting all users from MongoDB: {e}", exc_info=True)

    def upsert_user(self, user):
        """
        Insert user if not exists, update if exists.
        Preserves the existing user_id so ratings stay linked.
        Returns the user_id to use.
        """
        try:
            collection = self.client[self.database].users
            existing = collection.find_one({"username": user["username"]})
            if existing:
                user["user_id"] = existing["user_id"]
                collection.update_one({"username": user["username"]}, {"$set": user})
                logger.info(f"Updated user '{user['username']}' in MongoDB.")
            else:
                collection.insert_one(user)
                logger.info(f"Inserted new user '{user['username']}' into MongoDB.")
            return user["user_id"]
        except Exception as e:
            logger.error(f"Error upserting user '{user.get('username')}': {e}", exc_info=True)
            return user["user_id"]

    def delete_ratings_by_user_id(self, user_id):
        """
        Delete all ratings associated with a specific user_id.
        """
        try:
            collection = self.client[self.database].ratings
            deleted_count = collection.delete_many({"user_id": user_id}).deleted_count
            logger.info(f"Deleted {deleted_count} ratings for user_id '{user_id}'.")
        except Exception as e:
            logger.error(f"Error deleting ratings for user_id '{user_id}': {e}", exc_info=True)

    def get_weekly_popular_movies(self, limit: int = 20):
        try:
            db = self.client[self.database]

            weekly_top = []
            weeks_back = 1
            max_weeks = 52
            while not weekly_top and weeks_back <= max_weeks:
                since = datetime.now(timezone.utc) - timedelta(weeks=weeks_back)
                pipeline = [
                    {
                        "$addFields": {
                            "parsed_date": {
                                "$dateFromString": {
                                    "dateString": "$rating_date",
                                    "format": "%Y-%m-%d"
                                }
                            }
                        }
                    },
                    {"$match": {"parsed_date": {"$gte": since}}},
                    {"$group": {"_id": "$movie_title", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": limit},
                ]
                weekly_top = list(db.ratings.aggregate(pipeline))
                if not weekly_top:
                    logger.info(f"No movies found in last {weeks_back} week(s), going back further.")
                    weeks_back += 1

            if not weekly_top:
                logger.warning(f"No movies found within {max_weeks} weeks, returning empty list.")
                return []

            logger.info(f"Found movies using a {weeks_back}-week window.")
            movie_titles = [doc["_id"] for doc in weekly_top]

            movies_map = {
                m["movie_title_formatted"]: m
                for m in db.movies.find({"movie_title_formatted": {"$in": movie_titles}})
            }

            results = []
            for doc in weekly_top:
                m = movies_map.get(doc["_id"], {})
                results.append({
                    "id": doc["_id"],
                    "movie_title_formatted": m.get("movie_title_formatted"),
                    "movie_title": m.get("movie_title"),
                    "runtime": m.get("runtime"),
                    "histogram": m.get("histogram"),
                    "year": m.get("year_released", 0),
                    "poster_url": m.get("poster_url", ""),
                    "lb_rating": float(m.get("lb_rating", 0.0)),
                    "genres": m.get("genres", []),
                    "source": "Popular"
                })

            logger.info(f"Fetched {len(results)} weekly popular movies from MongoDB.")
            return results
        except Exception as e:
            logger.error(f"Error fetching weekly popular movies: {e}", exc_info=True)
            return []

    def find_movies_with_missing_fields(self, fields: list, limit: int = 0) -> list:
        """
        Return movies that have at least one of the given fields missing, null, empty, or zero.
        """
        try:
            collection = self.client[self.database].movies
            missing_conditions = []
            for field in fields:
                missing_conditions.append({field: {"$exists": False}})
                missing_conditions.append({field: None})
                missing_conditions.append({field: ""})
                missing_conditions.append({field: []})
                missing_conditions.append({field: 0})

            query = {"$or": missing_conditions}
            results = list(collection.find(query, limit=limit))
            for item in results:
                item.pop("_id", None)
            logger.info(f"Found {len(results)} movies with missing fields {fields}.")
            return results
        except Exception as e:
            logger.error(f"Error finding movies with missing fields: {e}", exc_info=True)
            return []

    def update_movie(self, movie_title_formatted: str, update_data: dict):
        """
        Update fields on an existing movie document.
        """
        try:
            collection = self.client[self.database].movies
            result = collection.update_one(
                {"movie_title_formatted": movie_title_formatted},
                {"$set": update_data}
            )
            logger.info(
                f"Updated movie '{movie_title_formatted}': matched={result.matched_count}, modified={result.modified_count}."
            )
        except Exception as e:
            logger.error(f"Error updating movie '{movie_title_formatted}': {e}", exc_info=True)

    def get_db_size_mb(self) -> dict:
        """
        Return current database size stats in MB using dbStats.
        Keys: data_mb, storage_mb, index_mb, total_mb
        total_mb = storageSize + indexSize, which is what Atlas counts against the free-tier cap.
        """
        try:
            stats = self.client[self.database].command("dbStats")
            result = {
                "data_mb":    stats.get("dataSize", 0)    / 1024 / 1024,
                "storage_mb": stats.get("storageSize", 0) / 1024 / 1024,
                "index_mb":   stats.get("indexSize", 0)   / 1024 / 1024,
                "total_mb":   (stats.get("storageSize", 0) + stats.get("indexSize", 0)) / 1024 / 1024,
            }
            logger.info(f"DB size: {result}")
            return result
        except Exception as e:
            logger.error(f"Error fetching DB size: {e}", exc_info=True)
            return {}

    def delete_no_signal_ratings(self, limit: int = 5000) -> int:
        """
        Delete ratings that carry no recommendation signal:
        rating_val == 0, is_review == False, is_liked == False.
        These are plain "watched" entries with nothing to learn from.
        Returns number of deleted documents.
        """
        try:
            collection = self.client[self.database].ratings
            query = {
                "rating_val": {"$in": [0, "0"]},
                "is_review":  {"$ne": True},
                "is_liked":   {"$ne": True},
            }
            result = collection.delete_many(query)
            logger.info(f"Deleted {result.deleted_count} no-signal ratings.")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting no-signal ratings: {e}", exc_info=True)
            return 0

    def delete_oldest_ratings(self, limit: int = 5000) -> int:
        """
        Delete the oldest `limit` rating documents by rating_date.
        Returns number of deleted documents.
        """
        try:
            collection = self.client[self.database].ratings
            oldest = list(
                collection.find({}, {"_id": 1})
                .sort("rating_date", 1)
                .limit(limit)
            )
            if not oldest:
                return 0
            ids = [doc["_id"] for doc in oldest]
            result = collection.delete_many({"_id": {"$in": ids}})
            logger.info(f"Deleted {result.deleted_count} oldest ratings.")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting oldest ratings: {e}", exc_info=True)
            return 0

    def insert_embeddings(self, embeddings, df_merged):
        """
        Insert movie embeddings into MongoDB.
        Each embedding is normalized and stored with the movie title as the identifier.
        """
        try:
            collection = self.client[self.database].movies_embeddings
            for idx, embedding in enumerate(embeddings):
                identifier = df_merged["movie_title_formatted"][idx]
                normalized_embedding = embedding / np.linalg.norm(embedding)
                document = {
                    '_id': identifier,
                    'embedding': normalized_embedding.tolist()
                }
                collection.insert_one(document)
            logger.info(f"Successfully inserted {len(embeddings)} embeddings into MongoDB.")
        except Exception as e:
            logger.error(f"Error inserting embeddings into MongoDB: {e}", exc_info=True)
