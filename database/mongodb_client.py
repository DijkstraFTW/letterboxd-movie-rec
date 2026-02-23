import os
import certifi
import numpy as np
from pymongo import MongoClient
from app_logger.app_logger import setup_logger

logger = setup_logger("../logs/mongodb_client.log", "MongoDBClient")


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

            self._client = MongoClient(self.URI, tlsCAFile=certifi.where())
            self._client.admin.command('ping')

            self._initialized = True
            logger.info(f"MongoDBClient singleton initialized for database '{self.database}' at cluster '{self.cluster}'.")
        except Exception as e:
            logger.error(f"Error initializing MongoDBClient: {e}", exc_info=True)
            raise

    @property
    def client(self):
        """Property to access the MongoDB client."""
        if self._client is None:
            raise RuntimeError("MongoDBClient not properly initialized")
        return self._client

    def open_conn_to_db(self):
        """Deprecated: Returns the singleton client for backward compatibility."""
        logger.warning("open_conn_to_db() is deprecated. Use MongoDBClient().client instead.")
        return self.client

    def close_conn_to_db(self, client):
        """Deprecated: No-op for backward compatibility. Connection is managed by singleton."""
        logger.warning("close_conn_to_db() is deprecated. Connection is managed by the singleton pattern.")
        return "OK"

    def insert_ratings(self, ratings, client=None):
        try:
            collection = self.client[self.database].ratings
            for rating in ratings:
                collection.insert_one(rating)
            logger.info(f"Successfully added {len(ratings)} ratings to MongoDB.")
        except Exception as e:
            logger.error(f"Error adding ratings to MongoDB: {e}", exc_info=True)

    def read_all_ratings(self, client=None):
        try:
            collection = self.client[self.database].ratings
            result = list(collection.find())
            result = [item for item in result if item["rating_val"] != "rating"]
            logger.info(f"Fetched {len(result)} ratings from MongoDB.")
            return result
        except Exception as e:
            logger.error(f"Error reading ratings from MongoDB: {e}", exc_info=True)
            return []

    def insert_movies(self, movie, client=None):
        try:
            collection = self.client[self.database].movies
            collection.insert_one(movie)
            logger.info(f"Inserted movie '{movie.get('movie_title_formatted', 'Unknown')}' into MongoDB.")
        except Exception as e:
            logger.error(f"Error inserting movie '{movie.get('movie_title', 'Unknown')}': {e}", exc_info=True)

    def read_all_movies_title_formatted(self, client=None):
        try:
            collection = self.client[self.database].movies
            result = [item["movie_title_formatted"] for item in collection.find()]
            logger.info(f"Fetched {len(result)} movie titles from MongoDB.")
            return set(result)
        except Exception as e:
            logger.error(f"Error reading all movies from MongoDB: {e}", exc_info=True)
            return set()

    def read_all_movies(self, client=None):
        try:
            collection = self.client[self.database].movies
            result = list(collection.find())
            for item in result:
                item.pop('_id', None)
            logger.info(f"Fetched {len(result)} movies from MongoDB.")
            return result
        except Exception as e:
            logger.error(f"Error reading all movies from MongoDB: {e}", exc_info=True)
            return []

    def read_all_rated_movies(self, client=None):
        try:
            collection = self.client[self.database].ratings
            result = list({item["movie_title"] for item in collection.find()})
            logger.info(f"Fetched {len(result)} rated movies from MongoDB.")
            return result
        except Exception as e:
            logger.error(f"Error reading rated movies from MongoDB: {e}", exc_info=True)
            return []

    def read_movie(self, movie_title, client=None):
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

    def read_movies_by_titles(self, movie_titles, client=None):
        """
        Fetch multiple movies by their titles in a single query.
        Efficient for enriching recommendation results.

        :param movie_titles: List of movie titles to fetch
        :return: List of movie documents
        """
        try:
            collection = self.client[self.database].movies
            # Use $in operator for efficient bulk query
            results = list(collection.find({"movie_title_formatted": {"$in": movie_titles}}))

            # Remove MongoDB _id field
            for result in results:
                result.pop('_id', None)

            logger.info(f"Fetched {len(results)} movies out of {len(movie_titles)} requested from MongoDB.")
            return results
        except Exception as e:
            logger.error(f"Error reading movies by titles from MongoDB: {e}", exc_info=True)
            return []

    def insert_users(self, users, client=None):
        try:
            collection = self.client[self.database].users
            for user in users:
                collection.insert_one(user)
            logger.info(f"Successfully added {len(users)} users to MongoDB.")
        except Exception as e:
            logger.error(f"Error inserting users into MongoDB: {e}", exc_info=True)

    def find_user(self, username, client=None):
        try:
            collection = self.client[self.database].users
            result = collection.count_documents({"username": username})
            logger.info(f"Found {result} entries for username '{username}'.")
            return result
        except Exception as e:
            logger.error(f"Error finding user '{username}' in MongoDB: {e}", exc_info=True)
            return None

    def get_user_custom_id(self, username, client=None):
        try:
            collection = self.client[self.database].users
            result = collection.find_one({"username": username})
            if result:
                logger.info(f"Retrieved user_id for username '{username}'.")
                return result.get('user_id')
            else:
                logger.warning(f"No user found with username '{username}'.")
                return None
        except Exception as e:
            logger.error(f"Error getting user_id for '{username}' from MongoDB: {e}", exc_info=True)
            return None

    def get_reviews_by_user_id(self, user_id, client=None):
        try:
            collection = self.client[self.database].reviews
            result = list(collection.find({"user_id": user_id}))
            logger.info(f"Fetched {len(result)} reviews for user_id '{user_id}'.")
            return result
        except Exception as e:
            logger.error(f"Error getting reviews for user_id '{user_id}' from MongoDB: {e}", exc_info=True)
            return []

    def delete_all_ratings(self, client=None):
        try:
            collection = self.client[self.database].ratings
            deleted_count = collection.delete_many({}).deleted_count
            logger.info(f"Deleted {deleted_count} ratings from MongoDB.")
        except Exception as e:
            logger.error(f"Error deleting all ratings from MongoDB: {e}", exc_info=True)

    def delete_all_users(self, client=None):
        try:
            collection = self.client[self.database].users
            deleted_count = collection.delete_many({}).deleted_count
            logger.info(f"Deleted {deleted_count} users from MongoDB.")
        except Exception as e:
            logger.error(f"Error deleting all users from MongoDB: {e}", exc_info=True)

    def insert_embeddings(self, embeddings, df_merged, client=None):
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
