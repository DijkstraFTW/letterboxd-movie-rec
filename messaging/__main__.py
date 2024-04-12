from dotenv import load_dotenv

from database.MongoDBClient import MongoDBClient

if __name__ == "__main__":

    load_dotenv()

    mongodb = MongoDBClient()
    print(mongodb.URI)
    client = mongodb.open_conn_to_db()