import os

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient


class MongoDBClient:

    def __init__(self):
        self.username = os.getenv('MONGO_USERNAME')
        self.password = os.getenv('MONGO_PASSWORD')
        self.cluster = os.getenv('MONGO_CLUSTER')
        self.URI = "mongodb+srv://" + str(self.username) + ':' + str(self.password) + "@" + str(
            self.cluster) + "/?retryWrites=true&w=majority"

    def connect_to_db(self):

        client = MongoClient(self.URI, tlsCAFile=certifi.where())

        try:
            client.admin.command('ping')
            print("Successfully connected to MongoDB instance!")
        except Exception:
            print("Not connected to MongoDB")


if __name__ == "__main__":
    load_dotenv()
    client = MongoDBClient()
    client.connect_to_db()
