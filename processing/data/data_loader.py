import pandas as pd

from database.mongodb_client import MongoDBClient
from processing.utils.utils import remove_stopwords, create_bag_of_words

from app_logger.app_logger import setup_logger

logger = setup_logger("../logs/data_loader.log", "DataLoader")


class DataLoader:

    def load_ratings(self, include_engagement_features: bool = False):
        """
        Loads the ratings data from the MongoDB database
        :param include_engagement_features: If True, loads is_reviewed, is_liked, is_rewatch features
        :return: dataframe : dataframe containing all ratings
        """

        # Loading the ratings data
        ratings_list = []
        mongodb = MongoDBClient()
        ratings = mongodb.read_all_ratings()

        for i in ratings:
            rating_entry = {
                "movie_title": i["movie_title"],
                "rating_val": i["rating_val"],
                "user_id": i["user_id"]
            }

            if include_engagement_features:
                rating_entry["is_reviewed"] = i.get("is_review", False)
                rating_entry["is_liked"] = i.get("is_liked", False)
                rating_entry["is_rewatch"] = i.get("is_rewatch", False)

            ratings_list.append(rating_entry)

        df_ratings = pd.DataFrame(ratings_list)
        df_ratings["rating_val"] = df_ratings["rating_val"].astype("float64")

        # Processing the ratings data
        user_id_to_int = {user_id: idx for idx, user_id in enumerate(df_ratings["user_id"].unique())}
        movie_id_to_int = {movie_title: idx for idx, movie_title in enumerate(df_ratings["movie_title"].unique())}

        df_ratings["user_id_int"] = df_ratings["user_id"].map(user_id_to_int)
        df_ratings["movie_id_int"] = df_ratings["movie_title"].map(movie_id_to_int)

        logger.info(f"{len(df_ratings)} ratings successfully loaded!")

        return df_ratings

    def apply_engagement_weights(self, df_ratings: pd.DataFrame,
                                  review_boost: float = 0.5,
                                  like_boost: float = 0.3,
                                  rewatch_boost: float = 0.7,
                                  rating_threshold: float = 5.0,
                                  use_directional_review: bool = True) -> pd.DataFrame:
        """
        Adjusts ratings based on engagement signals (is_reviewed, is_liked, is_rewatch).

        IMPORTANT: Reviews can indicate strong feelings in EITHER direction:
        - High rating + review = amplify positive signal (great movie, wanted to share)
        - Low rating + review = amplify negative signal (bad movie, wanted to warn)

        Likes and rewatches are unambiguous positive signals.

        :param df_ratings: DataFrame with rating_val and engagement features
        :param review_boost: Boost magnitude for reviewed movies (direction depends on rating)
        :param like_boost: Boost amount for liked movies (always positive)
        :param rewatch_boost: Boost amount for rewatched movies (always positive)
        :param rating_threshold: Threshold to determine positive/negative review (default 5.0)
        :param use_directional_review: If True, reviews amplify in the rating's direction
        :return: DataFrame with adjusted 'rating_val_weighted' column
        """
        df = df_ratings.copy()

        # Ensure engagement features exist
        if 'is_reviewed' not in df.columns:
            logger.warning("Engagement features not found. Skipping weighting.")
            df['rating_val_weighted'] = df['rating_val']
            return df

        # Calculate engagement boost for each rating
        df['engagement_boost'] = 0.0

        # DIRECTIONAL REVIEW BOOST
        # Review amplifies the sentiment: push good ratings higher, bad ratings lower
        if use_directional_review:
            # For ratings above threshold: positive boost
            positive_mask = (df['is_reviewed'] == True) & (df['rating_val'] > rating_threshold)
            df.loc[positive_mask, 'engagement_boost'] += review_boost

            # For ratings below threshold: negative boost (push down)
            negative_mask = (df['is_reviewed'] == True) & (df['rating_val'] <= rating_threshold)
            df.loc[negative_mask, 'engagement_boost'] -= review_boost
        else:
            # Original behavior: always boost (not recommended)
            df.loc[df['is_reviewed'] == True, 'engagement_boost'] += review_boost

        # UNAMBIGUOUS POSITIVE SIGNALS
        # Like and rewatch are always positive indicators
        df.loc[df['is_liked'] == True, 'engagement_boost'] += like_boost
        df.loc[df['is_rewatch'] == True, 'engagement_boost'] += rewatch_boost

        # Apply boost (weighted rating = original + boost, clipped to valid range)
        df['rating_val_weighted'] = (df['rating_val'] + df['engagement_boost']).clip(lower=0.0, upper=10.0)

        # Log statistics
        logger.info(f"Applied engagement weights: review={review_boost}, like={like_boost}, rewatch={rewatch_boost}")
        logger.info(f"Directional reviews: {use_directional_review}, threshold={rating_threshold}")
        logger.info(f"Average rating before: {df['rating_val'].mean():.2f}, after: {df['rating_val_weighted'].mean():.2f}")

        # Log distribution of review sentiment
        if 'is_reviewed' in df.columns and use_directional_review:
            positive_reviews = df[(df['is_reviewed'] == True) & (df['rating_val'] > rating_threshold)].shape[0]
            negative_reviews = df[(df['is_reviewed'] == True) & (df['rating_val'] <= rating_threshold)].shape[0]
            logger.info(f"Reviews: {positive_reviews} positive (boosted up), {negative_reviews} negative (boosted down)")

        return df

    def apply_engagement_amplification(self, df_ratings: pd.DataFrame,
                                        review_amplification: float = 1.15,
                                        like_amplification: float = 1.10,
                                        rewatch_amplification: float = 1.20) -> pd.DataFrame:
        """
        Alternative approach: AMPLIFY ratings based on engagement (multiplicative instead of additive).

        This naturally handles directional sentiment:
        - 8.0 with review -> 8.0 * 1.15 = 9.2 (amplified positive)
        - 3.0 with review -> 3.0 * 1.15 = 3.45 (amplified negative)

        Ratings are centered around 5.0, so amplification pushes away from the middle:
        - Loved it (9) + engaged -> even stronger signal
        - Hated it (2) + engaged -> even stronger negative signal
        - Meh (5) + engaged -> stays near middle

        :param df_ratings: DataFrame with rating_val and engagement features
        :param review_amplification: Multiplier for reviewed movies (e.g., 1.15 = 15% amplification)
        :param like_amplification: Multiplier for liked movies
        :param rewatch_amplification: Multiplier for rewatched movies
        :return: DataFrame with adjusted 'rating_val_weighted' column
        """
        df = df_ratings.copy()

        # Ensure engagement features exist
        if 'is_reviewed' not in df.columns:
            logger.warning("Engagement features not found. Skipping amplification.")
            df['rating_val_weighted'] = df['rating_val']
            return df

        # Center ratings around 5.0 (middle of 0-10 scale)
        RATING_CENTER = 5.0
        df['rating_centered'] = df['rating_val'] - RATING_CENTER

        # Calculate cumulative amplification multiplier
        df['amplification_factor'] = 1.0
        df.loc[df['is_reviewed'] == True, 'amplification_factor'] *= review_amplification
        df.loc[df['is_liked'] == True, 'amplification_factor'] *= like_amplification
        df.loc[df['is_rewatch'] == True, 'amplification_factor'] *= rewatch_amplification

        # Apply amplification to centered ratings, then shift back
        df['rating_val_weighted'] = (
            df['rating_centered'] * df['amplification_factor'] + RATING_CENTER
        ).clip(lower=0.0, upper=10.0)

        # Log statistics
        logger.info(f"Applied engagement amplification: review={review_amplification}x, "
                   f"like={like_amplification}x, rewatch={rewatch_amplification}x")
        logger.info(f"Average rating before: {df['rating_val'].mean():.2f}, "
                   f"after: {df['rating_val_weighted'].mean():.2f}")

        # Show examples of high and low engagement
        high_engagement = df[(df['is_reviewed'] == True) & (df['rating_val'] > 7)].head(3)
        low_engagement = df[(df['is_reviewed'] == True) & (df['rating_val'] < 4)].head(3)

        if not high_engagement.empty:
            logger.info("Sample high-rated reviews:")
            for _, row in high_engagement.iterrows():
                logger.info(f"  {row['rating_val']:.1f} -> {row['rating_val_weighted']:.1f}")

        if not low_engagement.empty:
            logger.info("Sample low-rated reviews:")
            for _, row in low_engagement.iterrows():
                logger.info(f"  {row['rating_val']:.1f} -> {row['rating_val_weighted']:.1f}")

        return df

    def load_movies(self):
        """
        Loads the movies data from the MongoDB database
        :return: dataframe : dataframe containing all movies
        """

        # Loading the movies data
        mongodb = MongoDBClient()
        movies = mongodb.read_all_movies()

        movies_list = []
        for i in movies:
            movies_list.append({"movie_title_formatted": i.get("movie_title_formatted"), "movie_title": i.get("movie_title"),
                                "type": i.get("type"), "year_released": i.get("year_released"), "imdb_link": i.get("imdb_link"),
                                "tmdb_link": i.get("tmdb_link"), "imdb_id": i.get("imdb_id"), "tmdb_id": i.get("tmdb_id"),
                                "poster_url": i.get("poster_url"), "genres": i.get("genres"),
                                "production_countries": i.get("production_countries"),
                                "spoken_languages": i.get("spoken_languages"), "popularity": i.get("popularity"),
                                "overview": i.get("overview"), "runtime": i.get("runtime"), "vote_average": i.get("vote_average"),
                                "vote_count": i.get("vote_count"), "release_date": i.get("release_date"),
                                "original_language": i.get("original_language"), "last_updated": i.get("last_updated")})

        df_movies = pd.DataFrame(movies_list)
        df_movies["movie_title_formatted"] = df_movies["movie_title_formatted"].astype(str)
        df_movies = df_movies.dropna()

        logger.info(f"{len(df_movies)} movies successfully loaded!")

        return df_movies

    def combine_movies_ratings(self, df_ratings, df_movies):
        """
        Prepares the merged ratings and movies data
        :return: dataframe : dataframe containing all ratings and movies
        """

        # Merging the two dataframes
        df_unique_ratings = df_ratings[['movie_title', 'movie_id_int']].drop_duplicates(subset='movie_id_int',
                                                                                        keep="first")
        df_merged = pd.merge(df_movies, df_unique_ratings, left_on='movie_title_formatted', right_on='movie_title',
                             how='right')
        df_merged = df_merged.drop(columns=["movie_title_y"])
        df_merged = df_merged.rename(columns={'movie_title_x': 'movie_title'})

        # Adding fields
        df_merged["overview_cleaned"] = df_merged["overview"].fillna("").apply(remove_stopwords)
        df_merged["bag_of_words"] = df_merged.apply(create_bag_of_words, axis=1)

        return df_merged
