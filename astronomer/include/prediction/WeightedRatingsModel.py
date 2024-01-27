from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler


class WeightedRatingsModel:

    def predict_recs_weighted(self, df, recs_number):
        """
        Produces movies recommendations based on a custom score
        :param df: the dataframe containg the movies
        :param recs_number: the number of recommendations to return
        :return dataframe : dataframe containing the top $recs_number recommendations
        """

        # Calculating the weighted average of every movie using the IMDB formula
        avg_rating = df['vote_average']
        vote_count = df['vote_count']
        p90_votes = df['vote_count'].quantile(0.9)
        avg_rating_mean = avg_rating.mean()

        df['weighted_average'] = (avg_rating * vote_count + p90_votes * avg_rating_mean) / (
                vote_count + avg_rating_mean)

        # Calculating the time decay factor of every movie
        current_year = datetime.now().year
        df['time_decay_factor'] = 1 / (current_year - df['year_released'] + 1)
        df['time_decay_factor'] = df['time_decay_factor'].replace(np.inf, 1.0)

        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(df[['popularity', 'weighted_average', 'time_decay_factor']])

        df_movies_factors = pd.DataFrame(scaled, columns=['popularity', 'weighted_average', 'time_decay_factor'])
        df_movies_factors.index = df['movie_title_formatted']

        # Calculating a custom 'score' based on a weighted combination of factors
        df_movies_factors['score'] = (
                df_movies_factors['weighted_average'] * 0.5 + df_movies_factors['popularity'] * 0.45 +
                df_movies_factors['time_decay_factor'] * 0.05)

        # Sorting and returning the top $recs_numbers
        df_movies_factors_sorted = df_movies_factors.sort_values(by='score', ascending=False)
        top_movies = df_movies_factors_sorted.head(recs_number)

        return top_movies
