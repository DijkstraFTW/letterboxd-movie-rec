from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from surprise import (Reader, Dataset, SVD, SVDpp, accuracy)


class CollaborativeFilteringModel:

    def __init__(self, ratings, movies):
        self.model = None
        self.df_ratings = pd.DataFrame(ratings)
        self.df_movies = pd.DataFrame(movies)

    def prepare_dataset(self):
        """
        Prepares the ratings data for training and testing.

        :rtype: returns the training set and the testing set
        """

        # Preprocessing the ratings data
        self.df_ratings["rating_val"] = self.df_ratings["rating_val"].astype('float64')
        user_id_to_int = {user_id: idx for idx, user_id in enumerate(self.df_ratings['user_id'].unique())}
        movie_id_to_int = {movie_title: idx for idx, movie_title in enumerate(self.df_ratings['movie_title'].unique())}
        self.df_ratings['user_id_int'] = self.df_ratings['user_id'].map(user_id_to_int)
        self.df_ratings['movie_id_int'] = self.df_ratings['movie_title'].map(movie_id_to_int)

        print("Ratings data successfully preprocessed !")

        # Splitting the ratings data for training and testing
        train_df, test_df = train_test_split(self.df_ratings, test_size=0.25, random_state=42)
        reader = Reader(rating_scale=(1, 10))
        train_data = Dataset.load_from_df(train_df[["user_id_int", "rating_val", "movie_id_int"]], reader)
        test_data = Dataset.load_from_df(test_df[["user_id_int", "rating_val", "movie_id_int"]], reader)

        trainset = train_data.build_full_trainset()
        testset = test_data.build_full_trainset().build_testset()

        print("Training and Testing sets successfully loaded !")

        return trainset, testset

    def train_model(self, train_set, test_set):
        """
        Fits an SVDpp collaborative filtering model using the users ratings

        :param train_set: the training set
        :param test_set: the testing set
        :rtype: str: returns the saved model path
        """

        # Model parameters
        n_factors = 150
        n_epochs = 5
        lr_all = 0.012
        reg_all = 0.15

        # Training the SVD model
        algo = SVD(n_factors=n_factors, n_epochs=n_epochs, lr_all=lr_all, reg_all=reg_all)
        algo.fit(train_set)

        # Training metrics
        predictions = algo.test(test_set)
        rmse_value = accuracy.rmse(predictions)

        print(f"RMSE score : {rmse_value}")
        print("Model trained successfully !")

        # Saving the model
        self.model = algo

    def predict_rating_movie_user(self, user_id, movie_id):
        """
        Predicts the rating of a movie for a given user.

        :param user_id: the user id
        :param movie_id: the movie id
        :rtype: float: returns the predicted rating
        """
        prediction = self.model.predict(user_id, movie_id)
        return prediction.est

    def generate_recommendation(self, user_id, number_of_recommendations=10):
        """
        Generates recommendation items for a given user.

        :param user_id: The ID of the user for whom to recommend items.
        :param number_of_recommendations: The number of recommendations to generate.
        :rtype: returns a list of recommended item IDs along with predicted ratings.
        """
        # Getting the unrated items for the user
        rated_items = self.df_ratings[self.df_ratings['user_id_int'] == user_id]['movie_id_int'].unique()
        all_items = self.df_ratings['movie_id_int'].unique()
        unrated_items = [item for item in all_items if item not in rated_items]

        # Predicting the ratings for the unrated items
        predictions = [self.predict_rating_movie_user(user_id, item) for item in unrated_items]
        item_predictions = list(zip(unrated_items, predictions))

        print(item_predictions)

        # Sorting the predictions and returning the top N recommendations
        item_predictions.sort(key=lambda x: x[1], reverse=True)
        top_n_recommendations = item_predictions[:number_of_recommendations]

        return top_n_recommendations

    def get_weighted_recommendations(self, recs_number):
        """
        Produces movies recommendations based on a custom score.

        :param recs_number: the number of recommendations to return
        :rtype: dataframe : dataframe containing the top $recs_number recommendations
        """

        # Calculating the weighted average of every movie using the IMDB formula
        avg_rating = self.df_movies['vote_average']
        vote_count = self.df_movies['vote_count']
        p90_votes = self.df_movies['vote_count'].quantile(0.9)
        avg_rating_mean = avg_rating.mean()

        self.df_movies['weighted_average'] = (
            (avg_rating * vote_count + p90_votes * avg_rating_mean) / (vote_count + avg_rating_mean)
        )

        # Calculating the time decay factor of every movie
        current_year = datetime.now().year
        self.df_movies['time_decay_factor'] = 1 / (current_year - self.df_movies['year_released'] + 1)
        self.df_movies['time_decay_factor'] = self.df_movies['time_decay_factor'].replace(np.inf, 1.0)

        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(self.df_movies[['popularity', 'weighted_average', 'time_decay_factor']])

        df_movies_factors = pd.DataFrame(scaled, columns=['popularity', 'weighted_average', 'time_decay_factor'])
        df_movies_factors.index = self.df_movies['movie_title_formatted']

        # Calculating a custom 'score' based on a weighted combination of factors
        df_movies_factors['score'] = (
            df_movies_factors['weighted_average'] * 0.5 +
            df_movies_factors['popularity'] * 0.45 +
            df_movies_factors['time_decay_factor'] * 0.05
        )

        # Sorting and returning the top $recs_numbers
        df_movies_factors_sorted = df_movies_factors.sort_values(by='score', ascending=False)
        top_movies = df_movies_factors_sorted.head(recs_number)

        return top_movies
