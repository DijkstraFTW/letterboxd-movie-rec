import numpy as np
import pandas as pd
from surprise import SVD, Dataset, Reader
from surprise.model_selection import RandomizedSearchCV
import pickle
import os
from typing import List, Tuple, Optional
from app_logger.app_logger import setup_logger

logger = setup_logger("../logs/recommendation_engine.log", "RecommendationEngine")

class RecommendationEngine:
    """
    A hybrid recommendation engine trained on a fixed set of active users (e.g., 4000).
    Can generate predictions and recommendations for any user based on their ratings.
    """

    # Class constants
    RATING_SCALE_MIN = 0
    RATING_SCALE_MAX = 10
    DEFAULT_HYBRID_WEIGHT = 0.7
    CONTENT_SCORE_QUANTILE = 0.7
    DEFAULT_PARAMS = {
        'n_factors': 100,
        'n_epochs': 30,
        'lr_all': 0.01,
        'reg_all': 0.02
    }

    def __init__(self, ratings_df: Optional[pd.DataFrame] = None, movies_df: Optional[pd.DataFrame] = None) -> None:
        """
        Initializes the engine with dataframes.

        :param ratings_df: DataFrame containing columns ['user_id', 'movie_title', 'rating_val']
        :param movies_df: DataFrame containing movie metadata like 'vote_average', 'vote_count', 'year_released', 'popularity'.
        """
        self.model = None
        self.trainset_global_mean = None
        self.item_mapping = None  # movie_title -> inner_iid
        self.inverse_item_mapping = None # inner_iid -> movie_title
        self.movie_score_map = None # movie_title -> content_score
        self.all_movies_list = None # List of all known movie titles
        self.best_params = None
        self.movie_metadata = None  # Lightweight metadata dict for recommendations
        self.df_movies = movies_df  # Only used during training, not saved to bundle
        self.df_ratings = ratings_df

    def _validate_dataframes(self, ratings_df: pd.DataFrame, movies_df: pd.DataFrame) -> None:
        """
        Validates input dataframes have required columns and valid data.

        :raises ValueError: If validation fails
        """
        # Validate ratings_df
        required_ratings_cols = ['user_id', 'movie_title', 'rating_val']
        missing_cols = [col for col in required_ratings_cols if col not in ratings_df.columns]
        if missing_cols:
            raise ValueError(f"ratings_df missing required columns: {missing_cols}")

        if ratings_df.empty:
            raise ValueError("ratings_df is empty")

        # Check for NaN values
        if ratings_df[required_ratings_cols].isnull().any().any():
            nan_counts = ratings_df[required_ratings_cols].isnull().sum()
            raise ValueError(f"ratings_df contains NaN values: {nan_counts.to_dict()}")

        # Validate rating scale
        min_rating = ratings_df['rating_val'].min()
        max_rating = ratings_df['rating_val'].max()
        if min_rating < self.RATING_SCALE_MIN or max_rating > self.RATING_SCALE_MAX:
            raise ValueError(
                f"Ratings must be in range [{self.RATING_SCALE_MIN}, {self.RATING_SCALE_MAX}]. "
                f"Found: [{min_rating}, {max_rating}]"
            )

        # Validate movies_df
        required_movie_cols = ['movie_title', 'vote_average', 'vote_count']
        missing_cols = [col for col in required_movie_cols if col not in movies_df.columns]
        if missing_cols:
            raise ValueError(f"movies_df missing required columns: {missing_cols}")

        if movies_df.empty:
            raise ValueError("movies_df is empty")

        logger.info(f"Data validation passed: {len(ratings_df)} ratings, {len(movies_df)} movies")

    def _precompute_movie_scores(self) -> None:
        """
        Computes content-based scores for all movies using metadata.
        Uses a weighted Bayesian average to handle movies with few votes.
        Stores results in self.movie_score_map as {movie_title: score}.
        """
        logger.info("Precomputing content-based scores for all movies...")

        # Calculate weighted rating using Bayesian average
        C = self.df_movies['vote_average'].mean()  # Mean rating across all movies
        m = self.df_movies['vote_count'].quantile(self.CONTENT_SCORE_QUANTILE)  # Minimum votes required

        # Store parameters for on-demand content score computation
        self._content_score_params = {
            'mean_rating': C,
            'min_votes': m
        }

        def weighted_rating(row):
            v = row['vote_count']
            R = row['vote_average']
            # Bayesian average formula: (v/(v+m) * R) + (m/(v+m) * C)
            return (v / (v + m) * R) + (m / (v + m) * C)

        self.df_movies['content_score'] = self.df_movies.apply(weighted_rating, axis=1)

        # Normalize to 0-10 scale
        max_score = self.df_movies['content_score'].max()
        min_score = self.df_movies['content_score'].min()

        if max_score > min_score:
            self.df_movies['content_score'] = (
                (self.df_movies['content_score'] - min_score) / (max_score - min_score) * 10
            )

        # Create mapping: movie_title -> content_score
        self.movie_score_map = dict(zip(
            self.df_movies['movie_title'],
            self.df_movies['content_score']
        ))

        logger.info(f"Content scores computed for {len(self.movie_score_map)} movies.")

    def _extract_movie_metadata(self) -> None:
        """
        Extracts only the essential metadata needed for recommendations.
        Stores a lightweight dict instead of the full DataFrame to save memory.
        """
        # Only keep columns we actually use (for display and on-demand scoring)
        essential_cols = ['movie_title', 'year_released', 'vote_average', 'vote_count']

        # Check which columns exist (some might be optional)
        available_cols = [col for col in essential_cols if col in self.df_movies.columns]

        metadata_df = self.df_movies[available_cols].copy()

        # Convert to dict of dicts: {movie_title: {year_released: X, vote_average: Y}}
        self.movie_metadata = metadata_df.set_index('movie_title').to_dict('index')

        logger.info(f"Extracted metadata for {len(self.movie_metadata)} movies.")

    def _compute_content_score(self, vote_average: float, vote_count: int) -> float:
        """
        Computes content score for a single movie using Bayesian average.
        Used for cold start movies not in the training set.

        :param vote_average: Average rating of the movie
        :param vote_count: Number of votes/ratings
        :return: Content score normalized to 0-10 scale
        """
        if not hasattr(self, '_content_score_params'):
            # Use global defaults if training params not available
            logger.warning("Content score parameters not available, using defaults")
            C = 7.0  # Assume average rating of 7/10
            m = 100  # Assume minimum of 100 votes
        else:
            C = self._content_score_params['mean_rating']
            m = self._content_score_params['min_votes']

        # Bayesian average: (v/(v+m) * R) + (m/(v+m) * C)
        weighted_score = (vote_count / (vote_count + m) * vote_average) + (m / (vote_count + m) * C)

        # Normalize to 0-10 range (assuming input is already 0-10)
        return np.clip(weighted_score, self.RATING_SCALE_MIN, self.RATING_SCALE_MAX)

    def build_and_train_model(
        self,
        ratings_df: pd.DataFrame,
        movies_df: pd.DataFrame,
        bundle_path: str,
        perform_grid_search: bool = True,
        use_weighted_ratings: bool = True,
        rating_column: str = 'rating_val'
    ) -> str:
        """
        Monthly Training Job: Trains the model and saves a complete bundle to disk.

        :param ratings_df: DataFrame with user ratings and optional engagement features
        :param movies_df: DataFrame with movie metadata
        :param bundle_path: Path to save the trained model bundle
        :param perform_grid_search: If True, runs a GridSearchCV to find optimal hyperparameters.
                                    If False, uses the previously found best_params or defaults.
        :param use_weighted_ratings: If True, uses 'rating_val_weighted' instead of 'rating_val'
        :param rating_column: Name of the rating column to use (overrides use_weighted_ratings)
        :return: Path to the saved bundle file
        """
        # Validate input data
        self._validate_dataframes(ratings_df, movies_df)

        self.df_ratings = ratings_df
        self.df_movies = movies_df
        self._precompute_movie_scores()
        self._extract_movie_metadata()  # Extract lightweight metadata

        # Determine which rating column to use
        if use_weighted_ratings and 'rating_val_weighted' in ratings_df.columns:
            rating_column = 'rating_val_weighted'
            logger.info("Using weighted ratings with engagement features for training")
        elif rating_column not in ratings_df.columns:
            rating_column = 'rating_val'
            logger.warning(f"Specified column '{rating_column}' not found, using 'rating_val'")

        logger.info(f"Training model with rating column: '{rating_column}'")

        reader = Reader(rating_scale=(self.RATING_SCALE_MIN, self.RATING_SCALE_MAX))
        data = Dataset.load_from_df(self.df_ratings[['user_id', 'movie_title', rating_column]], reader)
        
        if perform_grid_search:
            logger.info("Starting GridSearchCV for hyperparameter tuning...")
            param_grid = {
                'n_factors': [50, 100],
                'n_epochs': [30],
                'lr_all': [0.005, 0.01],
                'reg_all': [0.02, 0.1]
            }
            rs = RandomizedSearchCV(SVD, param_distributions=param_grid, 
                        n_iter=12,  # Test only 12 random combinations
                        measures=['rmse'], cv=3, n_jobs=2)

            rs.fit(data)
            
            self.best_params = rs.best_params['rmse']
            logger.info(f"GridSearch complete. Best RMSE: {rs.best_score['rmse']}")
            logger.info(f"Best parameters: {self.best_params}")

            # Save GridSearch results with proper path handling
            results_df = pd.DataFrame(rs.cv_results)
            bundle_dir = os.path.dirname(bundle_path)
            bundle_name = os.path.splitext(os.path.basename(bundle_path))[0]
            results_path = os.path.join(bundle_dir, f"{bundle_name}_gridsearch_results.csv")
            results_df.to_csv(results_path, index=False)
            logger.info(f"GridSearch results saved to {results_path}")
            
        else:
            if self.best_params is None:
                self.best_params = self.DEFAULT_PARAMS.copy()
                logger.info(f"Using default parameters: {self.best_params}")

        trainset = data.build_full_trainset()
        logger.info("Training final model on the entire dataset with best parameters...")
        
        self.model = SVD(**self.best_params)
        self.model.fit(trainset)

        self.trainset_global_mean = trainset.global_mean
        self.item_mapping = trainset._raw2inner_id_items
        self.inverse_item_mapping = {v: k for k, v in self.item_mapping.items()}
        self.all_movies_list = list(self.item_mapping.keys())

        model_bundle = {
            'model': self.model,
            'trainset_global_mean': self.trainset_global_mean,
            'item_mapping': self.item_mapping,
            'inverse_item_mapping': self.inverse_item_mapping,
            'movie_score_map': self.movie_score_map,
            'all_movies_list': self.all_movies_list,
            'best_params': self.best_params,
            'movie_metadata': self.movie_metadata,  # Lightweight metadata only (not full df_movies)
            'content_score_params': self._content_score_params  # For computing scores of new movies
        }

        try:
            os.makedirs(os.path.dirname(bundle_path), exist_ok=True)
            with open(bundle_path, 'wb') as f:
                pickle.dump(model_bundle, f)

            logger.info(f"Final model training complete. Bundle saved to {bundle_path}")
            return bundle_path

        except IOError as e:
            logger.error(f"Failed to save model bundle: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving bundle: {e}")
            raise

    def load_bundle(self, bundle_path: str) -> 'RecommendationEngine':
        """
        Production Server: Loads a complete model bundle from disk.

        :param bundle_path: Path to the pickled bundle file
        :return: Self for method chaining
        """
        logger.info(f"Loading model bundle from {bundle_path}")

        try:
            if not os.path.exists(bundle_path):
                raise FileNotFoundError(f"Bundle file not found: {bundle_path}")

            with open(bundle_path, 'rb') as f:
                bundle = pickle.load(f)

            # Validate required keys
            required_keys = ['model', 'trainset_global_mean', 'item_mapping',
                           'inverse_item_mapping', 'movie_score_map', 'all_movies_list']
            missing_keys = [key for key in required_keys if key not in bundle]

            if missing_keys:
                raise ValueError(f"Bundle is missing required keys: {missing_keys}")

            self.model = bundle['model']
            self.trainset_global_mean = bundle['trainset_global_mean']
            self.item_mapping = bundle['item_mapping']
            self.inverse_item_mapping = bundle['inverse_item_mapping']
            self.movie_score_map = bundle['movie_score_map']
            self.all_movies_list = bundle['all_movies_list']
            self.best_params = bundle.get('best_params')
            self.movie_metadata = bundle.get('movie_metadata')  # Load lightweight metadata
            self._content_score_params = bundle.get('content_score_params')  # For on-demand scoring

            logger.info("Model bundle loaded successfully.")
            return self

        except FileNotFoundError as e:
            logger.error(f"Failed to load bundle: {e}")
            raise
        except pickle.UnpicklingError as e:
            logger.error(f"Corrupt bundle file: {e}")
            raise ValueError(f"Unable to load bundle from {bundle_path}. File may be corrupt.")
        except Exception as e:
            logger.error(f"Unexpected error loading bundle: {e}")
            raise

    def _fold_in_user(self, user_ratings: List[Tuple[str, float]]) -> Tuple[np.ndarray, float]:
        """
        Creates a personalized user factor vector for a new user based on their ratings.

        :param user_ratings: A list of tuples in the format [(movie_title, rating_val), ...]
        :return: Tuple of (user_vector, user_bias)
        """
        n_factors = self.model.n_factors
        user_vector = np.zeros(n_factors)
        user_bias = 0.0
        num_ratings = len(user_ratings)
        
        if num_ratings == 0:
            return user_vector, user_bias
        
        for movie_title, rating in user_ratings:
            if movie_title in self.item_mapping:
                inner_iid = self.item_mapping[movie_title]
                movie_factors = self.model.qi[inner_iid]
                movie_bias = self.model.bi[inner_iid]

                user_vector += (rating - self.model.trainset.global_mean - movie_bias) * movie_factors
                user_bias += (rating - self.model.trainset.global_mean - movie_bias)
        
        user_vector /= num_ratings
        user_bias /= num_ratings
        
        return user_vector, user_bias

    def predict_rating_for_new_user(self, user_ratings: List[Tuple[str, float]], movie_title: str) -> float:
        """
        Predicts the rating a new user would give to a movie.

        :param user_ratings: List of tuples of the user's ratings: [(movie_title, rating_val), ...]
        :param movie_title: The title of the movie to predict for.
        :return: The predicted rating (float).
        """
        user_factors, user_bias = self._fold_in_user(user_ratings)
        
        if movie_title in self.item_mapping:
            inner_iid = self.item_mapping[movie_title]
            movie_factors = self.model.qi[inner_iid]
            movie_bias = self.model.bi[inner_iid]
            
            prediction = self.model.trainset.global_mean
            prediction += user_bias
            prediction += movie_bias
            prediction += np.dot(user_factors, movie_factors)

            prediction = np.clip(prediction, self.RATING_SCALE_MIN, self.RATING_SCALE_MAX)
            return prediction
        else:
            # Cold start: movie not in training set
            content_score = None

            # Try to get precomputed content score
            if movie_title in self.movie_score_map:
                content_score = self.movie_score_map[movie_title]
            # If not precomputed, try to compute on-demand from metadata
            elif self.movie_metadata and movie_title in self.movie_metadata:
                metadata = self.movie_metadata[movie_title]
                if 'vote_average' in metadata and 'vote_count' in metadata:
                    vote_avg = metadata.get('vote_average')
                    vote_cnt = metadata.get('vote_count')
                    if vote_avg is not None and vote_cnt is not None:
                        content_score = self._compute_content_score(vote_avg, vote_cnt)
                        logger.debug(f"Computed on-demand content score for {movie_title}: {content_score}")

            # Use content score if available
            if content_score is not None:
                user_ratings_list = [r for _, r in user_ratings]
                if user_ratings_list:
                    user_avg = np.mean(user_ratings_list)
                    # Weight toward content score for cold start
                    return 0.3 * user_avg + 0.7 * content_score
                return content_score
            else:
                # No content info available, fall back to user average or global mean
                user_ratings_list = [r for _, r in user_ratings]
                fallback = np.mean(user_ratings_list) if user_ratings_list else self.model.trainset.global_mean
                logger.debug(f"No content score for {movie_title}, using fallback: {fallback}")
                return fallback

    def add_movie_metadata(self, movie_title: str, vote_average: float, vote_count: int, year_released: Optional[int] = None) -> None:
        """
        Adds metadata for a new movie not in the training set.
        Useful for handling new releases or movies added after training.

        :param movie_title: Title of the movie
        :param vote_average: Average rating (0-10)
        :param vote_count: Number of votes
        :param year_released: Optional release year
        """
        if self.movie_metadata is None:
            self.movie_metadata = {}

        # Add to metadata
        self.movie_metadata[movie_title] = {
            'vote_average': vote_average,
            'vote_count': vote_count
        }
        if year_released is not None:
            self.movie_metadata[movie_title]['year_released'] = year_released

        # Compute and cache content score
        content_score = self._compute_content_score(vote_average, vote_count)
        if self.movie_score_map is None:
            self.movie_score_map = {}
        self.movie_score_map[movie_title] = content_score

        logger.info(f"Added metadata for new movie '{movie_title}' with content score: {content_score:.2f}")

    def generate_recommendations(
        self,
        user_ratings: List[Tuple[str, float]],
        n: int = 10,
        hybrid_weight: Optional[float] = None,
        db_client = None,
        enrich_from_db: bool = False
    ) -> pd.DataFrame:
        """
        Generates top-N recommendations for a new user based on their ratings.

        :param user_ratings: A list of tuples in the format [(movie_title, rating_val), ...]
        :param n: Number of recommendations to return.
        :param hybrid_weight: Balance between CF and content score (0.0 = only content, 1.0 = only CF).
        :param db_client: Optional MongoDB client instance for enriching results with full metadata
        :param enrich_from_db: If True, fetch full movie metadata from database
        :return: DataFrame with top recommendations and their predicted scores.
        """
        if hybrid_weight is None:
            hybrid_weight = self.DEFAULT_HYBRID_WEIGHT

        logger.info(f"Generating {n} recommendations for a new user based on {len(user_ratings)} ratings.")

        all_movies = list(self.item_mapping.keys())
        user_rated_movies = set([movie for movie, _ in user_ratings])
        movies_to_predict = [movie for movie in all_movies if movie not in user_rated_movies]

        logger.info(f"Predicting for {len(movies_to_predict)} unrated movies out of {len(all_movies)} total.")

        user_factors, user_bias = self._fold_in_user(user_ratings)

        predictions = []
        for movie in movies_to_predict:
            if movie in self.item_mapping:
                inner_iid = self.item_mapping[movie]
                movie_factors = self.model.qi[inner_iid]
                movie_bias = self.model.bi[inner_iid]

                cf_score = self.model.trainset.global_mean + user_bias + movie_bias + np.dot(user_factors, movie_factors)
                cf_score = np.clip(cf_score, self.RATING_SCALE_MIN, self.RATING_SCALE_MAX)

                content_score = self.movie_score_map.get(movie, 0.0)

                hybrid_score = (hybrid_weight * cf_score) + ((1 - hybrid_weight) * content_score)
                predictions.append((movie, cf_score, content_score, hybrid_score))

        recommendations_df = pd.DataFrame(predictions, columns=['movie_title', 'cf_score', 'content_score', 'hybrid_score'])
        recommendations_df = recommendations_df.sort_values('hybrid_score', ascending=False).head(n)

        # Enrich with metadata - either from database or lightweight bundle
        if enrich_from_db and db_client is not None:
            logger.info("Enriching recommendations with full metadata from database...")
            movie_titles = recommendations_df['movie_title'].tolist()

            # Fetch full movie data from MongoDB
            movies_data = db_client.read_movies_by_titles(movie_titles)

            # Convert to DataFrame for merging
            movies_df = pd.DataFrame(movies_data)

            # Merge on movie_title_formatted (assuming this matches movie_title in recommendations)
            if 'movie_title_formatted' in movies_df.columns:
                movies_df = movies_df.rename(columns={'movie_title_formatted': 'movie_title'})

            # Merge to add all movie metadata
            recommendations_df = recommendations_df.merge(movies_df, on='movie_title', how='left')
            logger.info(f"Added database metadata for {len(movies_data)} movies.")

        else:
            # Use lightweight metadata from bundle
            if self.movie_metadata:
                recommendations_df['year_released'] = recommendations_df['movie_title'].map(
                    lambda x: self.movie_metadata.get(x, {}).get('year_released')
                )
                recommendations_df['vote_average'] = recommendations_df['movie_title'].map(
                    lambda x: self.movie_metadata.get(x, {}).get('vote_average')
                )

        return recommendations_df

    #TODO : Content Based Filtering

