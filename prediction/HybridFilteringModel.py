from processing.utils.utils import select_last_model


class HybridFilteringModel :

    def __init__(self) :
        self.algo = select_last_model("colab_filtering_")

    def hybrid_predicted_rating(self, userId, movieId):

        # Collaborative Filtering Prediction
        collaborative_rating = self.algo.predict(userId, movieId).est

        # Content-Based Filtering Prediction
        "get similar"

        weighted_score = weighted_df.loc[merged_df.loc[movieId, 'movie_title_formatted'], 'score']

        # Hybrid Prediction using weighted average of collaborative_rating, content_rating, and weighted_score
        final_rating = (0.4 * collaborative_rating) + (0.2 * content_rating) + (0.4 * weighted_score)

        return final_rating

    def fetch_weighted_scores(self, movie_ids, movies_df, weighted_df):
        weighted_df = weighted_df.loc[~weighted_df.index.duplicated(keep='first')]
        weighted_scores = {}
        for movie_id in movie_ids:
            if movie_id in weighted_df.index:
                weighted_scores[movie_id] = weighted_df.loc[movie_id]['score']
            else:
                weighted_scores[movie_id] = 0  # Assign default score of 0
        return weighted_scores

    # Utility function to show details of recommended movies
    def show_movie_details(self, movie_ids, movies_df):

        # Display the details
        print("Recommended Movies:")
        for i in movie_ids:
            row = movies_df[movies_df["movie_id_int"] == i]
            print("Title: " + str(row['movie_title']) + ", " + str(row['year_released']))

    def hybrid_recommendation(self, user_id, n=10):
        user_ratings = df_ratings[df_ratings['user_id_int'] == user_id]
        predictions = []
        for index, row in user_ratings.iterrows():
            pred = self.algo.predict(row['user_id_int'], row['movie_id_int']).est
            predictions.append((row['movie_id_int'], pred))
        top_collab_movies = [x[0] for x in sorted(predictions, key=lambda x: x[1], reverse=True)[:n]]

        last_watched_movieId = user_ratings.iloc[-1]['movie_id_int']
        if last_watched_movieId in merged_df['movie_id_int'].values:
            watched_movie_idx = merged_df[merged_df['movie_id_int'] == last_watched_movieId].index[0]
            similar_movies = list(enumerate(cosine_sim2[watched_movie_idx]))
            sorted_similar_movies = sorted(similar_movies, key=lambda x: x[1], reverse=True)[1:n + 1]
            top_content_movies = [merged_df.iloc[i[0]]['movie_id_int'] for i in sorted_similar_movies]
        else:
            print(f"Movie ID {last_watched_movieId} not found in movies_df.")
            top_content_movies = []

        collab_weighted_scores = fetch_weighted_scores(top_collab_movies, merged_df, weighted_df)
        content_weighted_scores = fetch_weighted_scores(top_content_movies, merged_df, weighted_df)

        combined_scores = {}
        for movie_id, score in collab_weighted_scores.items():
            combined_scores[movie_id] = combined_scores.get(movie_id, 0) + 0.5 * score
        for movie_id, score in content_weighted_scores.items():
            combined_scores[movie_id] = combined_scores.get(movie_id, 0) + 0.5 * score
        sorted_movies = sorted(combined_scores.keys(), key=lambda x: combined_scores[x], reverse=True)
        return sorted_movies[:n]

    def recommend_for_new_user_top_rating_movies(df, movies_df, n=10, min_year=8):
        """
        Recommend the top n movies for a new user based on weighted rating scores.

        Parameters:
        df (DataFrame): DataFrame containing movie IDs and their weighted scores.
        n (int): Number of top movies to recommend.

        Returns:
        DataFrame: Top n recommended movies for a new user.
        """
        # Get the current year
        current_year = datetime.now().year

        # Sort the DataFrame based on the 'score' column in descending order.
        sorted_df = df.copy()
        sorted_df = df.sort_values(by='score', ascending=False)
        sorted_df = pd.merge(sorted_df, movies_df, on='movie_title_formatted', how='left')
        sorted_df['year_released'] = sorted_df['year_released'].fillna(0).astype(int)
        sorted_df = sorted_df[sorted_df['year_released'] >= (current_year - min_year)]
        # Return the top n movies.
        return list(sorted_df["movie_id_int"][0:n])

    def recommend_for_new_user_by_genre(df, movies_df, genres, n=10, min_year=5):
        """
        Recommend the top n movies for a new user based on weighted rating scores for each genre.

        Parameters:
        df (DataFrame): DataFrame containing movie IDs and their weighted scores.
        movies_df (DataFrame): DataFrame containing movie details.
        genres (list): List of genres to consider.
        n (int): Number of top movies to recommend for each genre.
        min_year (int): Minimum year for movies to be considered.

        Returns:
        dict: Dictionary where keys are genres and values are DataFrames containing top n recommended movies for that genre.
        """
        recommendations = {}

        movies_df = movies_df[['movie_title_formatted', 'year_released', 'genres']]

        # Get the current year
        current_year = datetime.now().year

        for genre in genres:
            # Filter movies by genre
            genre_movies_df = movies_df[movies_df['genres'].apply(lambda x: genre in x if x else False)]

            # Merge with the df DataFrame to get scores
            genre_df = pd.merge(df, genre_movies_df[['movie_title_formatted', 'year_released']],
                                on='movie_title_formatted',
                                how='left')  # 'movie_title_formatted','year_released', "movie_id_int"

            # Filter movies released in the last min_year years
            genre_df['year_released'] = genre_df['year_released'].fillna(0).astype(int)
            genre_df = genre_df[genre_df['year_released'] >= (current_year - min_year)]

            # Sort by score
            genre_df = genre_df.sort_values(by='score', ascending=False)

            # Get top n movies for this genre
            recommendations[genre] = genre_df.head(n)

        return recommendations