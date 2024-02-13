import pandas as pd

from astronomer.include.database.MongoDBClient import MongoDBClient
from processing.utils.utils import remove_stopwords, create_bag_of_words


class DataLoader:

    def load_ratings(self):

        # Loading the ratings data
        ratings_list = []
        mongodb = MongoDBClient()
        client = mongodb.open_conn_to_db()
        ratings = client.read_all_ratings

        for i in ratings:
            ratings_list.append(
                {"movie_title": i["movie_title"], "rating_val": i["rating_val"], "user_id": i["user_id"]})

        df_ratings = pd.DataFrame(ratings_list)
        df_ratings["rating_val"] = df_ratings["rating_val"].astype("float64")

        # Processing the ratings data
        user_id_to_int = {user_id: idx for idx, user_id in enumerate(df_ratings["user_id"].unique())}
        movie_id_to_int = {movie_title: idx for idx, movie_title in enumerate(df_ratings["movie_title"].unique())}

        df_ratings["user_id_int"] = df_ratings["user_id"].map(user_id_to_int)
        df_ratings["movie_id_int"] = df_ratings["movie_title"].map(movie_id_to_int)

        print(f"{len(df_ratings)} ratings succesfully loaded !")

        client.close_conn_to_db(client)

        return df_ratings

    def load_movies(self):

        # Loading the movies data
        movies_list = []
        mongodb = MongoDBClient()
        client = mongodb.open_conn_to_db()
        movies = client.read_all_movies

        for i in movies:
            movies_list.append({"movie_title_formatted": i["movie_title_formatted"], "movie_title": i["movie_title"],
                                "type": i["type"], "year_released": i["year_released"], "imdb_link": i["imdb_link"],
                                "tmdb_link": i["tmdb_link"], "imdb_id": i["imdb_id"], "tmdb_id": i["tmdb_id"],
                                "poster_url": i["poster_url"], "genres": i["genres"],
                                "production_countries": i["production_countries"],
                                "spoken_languages": i["spoken_languages"], "popularity": i["popularity"],
                                "overview": i["overview"], "runtime": i["runtime"], "vote_average": i["vote_average"],
                                "vote_count": i["vote_count"], "release_date": i["release_date"],
                                "original_language": i["original_language"], "last_updated": i["last_updated"]})

        df_movies = pd.DataFrame(movies_list)
        df_movies["movie_title_formatted"] = str(df_movies["movie_title_formatted"])

        # TODO add filtering func for NaN

        print(f"{len(df_movies)} movies succesfully loaded !")

        client.close_conn_to_db(client)

        return df_movies

    def combine_movies_ratings(self, df_ratings, df_movies):
        """
        Prepares the merged ratings and movies data
        :rtype: dataframe : dataframe containing all ratings and movies
        """

        # Merging the two dataframes
        df_merged = pd.DataFrame({})
        df_unique_ratings = df_ratings[['movie_title', 'movie_id_int']].drop_duplicates(subset='movie_id_int',
                                                                                        keep="first")
        df_merged = pd.merge(df_movies, df_unique_ratings, left_on='movie_title_formatted', right_on='movie_title',
                             how='right')
        df_merged = df_merged.drop(columns=["movie_title_y"])
        df_merged = df_merged.rename(columns={'movie_title_x': 'movie_title'})

        # Adding fields
        df_merged["overview_cleaned"] = [remove_stopwords(i) for i in df_merged["overview"]]
        df_merged["bag_of_words"] = df_merged.apply(create_bag_of_words, axis=1)

        return df_merged
