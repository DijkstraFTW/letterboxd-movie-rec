import os

import certifi
import numpy as np
from dotenv import load_dotenv
from pymongo import MongoClient

class MongoDBClient:

    def __init__(self):
        self.username = os.getenv('MONGO_USERNAME')
        self.password = os.getenv('MONGO_PASSWORD')
        self.cluster = os.getenv('MONGO_CLUSTER')
        self.database = os.getenv('MONGO_DATABASE')
        self.URI = "mongodb+srv://" + str(self.username) + ':' + str(self.password) + "@" + str(self.cluster) + "/?retryWrites=true&w=majority"

    def open_conn_to_db(self):
        try:
            client = MongoClient(self.URI, tlsCAFile=certifi.where())
            client.admin.command('ping')
            print("Successfully connected to MongoDB instance!")
            return client
        except Exception as e:
            print("Error disconnecting from MongoDB : " + str(e))
            return None

    def close_conn_to_db(self, client):
        try:
            client.close()
            print("Successfully disconnected to MongoDB instance!")
            return "OK"
        except Exception as e:
            print("Error disconnecting from MongoDB : " + str(e))
            return None

    def insert_movies(self, client, movies):
        try:
            collection = client[str(self.database)].movies
            for movie in movies:
                collection.insert_one(movie)
            print("Successfully added {} movies to MongoDB instance!".format(len(movies)))
        except Exception as e:
            print("Error adding movies to MongoDB : " + str(e))

    def insert_ratings(self, client, ratings):
        try:
            collection = client[str(self.database)].ratings
            for rating in ratings:
                collection.insert_one(rating)
            print("Successfully added {} ratings to MongoDB instance!".format(len(ratings)))
        except Exception as e:
            print("Error adding ratings to MongoDB : " + str(e))

    def read_all_ratings(self, client):
        try:
            collection = client[str(self.database)].ratings
            result = collection.find()
            return result
        except Exception as e:
            print("Error reading all movies from MongoDB: " + str(e))
            return []

    def read_all_movies_rated(self, client):
        try:
            collection = client[str(self.database)].ratings
            result = collection.find()
            result = [item["movie_title"] for item in result]
            return list(set(result))
        except Exception as e:
            print("Error reading all movies from MongoDB: " + str(e))
            return []

    def insert_users(self, client, users):
        try:
            collection = client[str(self.database)].users
            for user in users:
                collection.insert_one(user)
            print("Successfully added {} users to MongoDB instance!".format(len(users)))
        except Exception as e:
            print("Error adding users to MongoDB : " + str(e))

    def insert_embeddings(self, client, embeddings, df_merged):
        try:
            collection = client[str(self.database)].movies_embeddings
            for idx, embedding in enumerate(embeddings):
                identifier = df_merged["movie_title_formatted"][idx]
                normalized_embedding = embedding / np.linalg.norm(embedding)
                document = {
                    '_id': identifier,
                    'embedding': normalized_embedding.tolist()
                }
                collection.insert_one(document)
            print("Successfully added {} users to MongoDB instance!".format(len(embeddings)))
        except Exception as e:
            print("Error adding users to MongoDB : " + str(e))
