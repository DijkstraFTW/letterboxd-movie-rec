import re
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from surprise import SVD, Dataset, Reader
from surprise.model_selection import GridSearchCV
import pickle
import os
from typing import List, Tuple, Optional
from app_logger.app_logger import setup_logger

logger = setup_logger("/root/letterboxd-movie-rec/logs/recommendation_engine.log", "RecommendationEngine")

class RecommendationEngine:
    """
    A hybrid recommendation engine trained on a fixed set of active users (e.g., 4000).
    Can generate predictions and recommendations for any user based on their ratings.
    """

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
        required_ratings_cols = ['user_id', 'movie_title', 'rating_val']
        missing_cols = [col for col in required_ratings_cols if col not in ratings_df.columns]
        if missing_cols:
            raise ValueError(f"ratings_df missing required columns: {missing_cols}")

        if ratings_df.empty:
            raise ValueError("ratings_df is empty")

        if ratings_df[required_ratings_cols].isnull().any().any():
            nan_counts = ratings_df[required_ratings_cols].isnull().sum()
            raise ValueError(f"ratings_df contains NaN values: {nan_counts.to_dict()}")

        min_rating = ratings_df['rating_val'].min()
        max_rating = ratings_df['rating_val'].max()
        if min_rating < self.RATING_SCALE_MIN or max_rating > self.RATING_SCALE_MAX:
            raise ValueError(
                f"Ratings must be in range [{self.RATING_SCALE_MIN}, {self.RATING_SCALE_MAX}]. "
                f"Found: [{min_rating}, {max_rating}]"
            )

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

        C = self.df_movies['vote_average'].mean()
        m = self.df_movies['vote_count'].quantile(self.CONTENT_SCORE_QUANTILE)

        self._content_score_params = {
            'mean_rating': C,
            'min_votes': m,
            'min_score': None,  # set after normalization below
            'max_score': None,
        }

        v = self.df_movies['vote_count']
        R = self.df_movies['vote_average']
        # Bayesian average formula: (v/(v+m) * R) + (m/(v+m) * C)
        self.df_movies['content_score'] = (v / (v + m) * R) + (m / (v + m) * C)

        max_score = self.df_movies['content_score'].max()
        min_score = self.df_movies['content_score'].min()

        if max_score > min_score:
            self.df_movies['content_score'] = (
                (self.df_movies['content_score'] - min_score) / (max_score - min_score) * 10
            )

        self._content_score_params['min_score'] = min_score
        self._content_score_params['max_score'] = max_score

        # item_mapping keys are slugs (movie_title_formatted from ratings),
        # so key the score map by movie_title_formatted to match.
        key_col = 'movie_title_formatted' if 'movie_title_formatted' in self.df_movies.columns else 'movie_title'
        self.movie_score_map = dict(zip(
            self.df_movies[key_col],
            self.df_movies['content_score']
        ))

        logger.info(f"Content scores computed for {len(self.movie_score_map)} movies (keyed by '{key_col}').")

    def _extract_movie_metadata(self) -> None:
        """
        Extracts only the essential metadata needed for recommendations.
        Stores a lightweight dict instead of the full DataFrame to save memory.
        """
        essential_cols = ['movie_title', 'movie_title_formatted', 'lb_rating', 'histogram', 'runtime', 'poster_url', 'genres']

        available_cols = [col for col in essential_cols if col in self.df_movies.columns]

        metadata_df = self.df_movies[available_cols].copy()

        dupes = metadata_df['movie_title_formatted'].duplicated().sum()
        if dupes:
            logger.warning(f"Found {dupes} duplicate movie_title_formatted values; keeping first occurrence.")
            metadata_df = metadata_df.drop_duplicates(subset='movie_title_formatted', keep='first')

        self.movie_metadata = metadata_df.set_index('movie_title_formatted').to_dict('index')

        logger.info(f"Extracted metadata for {len(self.movie_metadata)} movies.")

    def _extract_tags(self, row) -> str:
        """Extracts genres, themes and nanogenres from a movie row into a single tag string."""
        tags = []
        for col in ('genres', 'themes', 'nanogenres'):
            raw = row.get(col, '') if isinstance(row, dict) else getattr(row, col, '')
            if isinstance(raw, list):
                tags += raw
            elif isinstance(raw, str) and raw:
                found = re.findall(r"'([^']+)'|\"([^\"]+)\"", raw)
                tags += [a or b for a, b in found]
        return ' '.join(t.strip().replace(' ', '_') for t in tags if t.strip())

    def _build_content_feature_matrix(self) -> None:
        """
        Builds a TF-IDF matrix over genres, themes, and nanogenres for all movies.
        Stored in the bundle so inference requires no recomputation.
        """
        logger.info("Building TF-IDF content feature matrix...")

        key_col = 'movie_title_formatted' if 'movie_title_formatted' in self.df_movies.columns else 'movie_title'
        keys = self.df_movies[key_col].tolist()
        docs = self.df_movies.apply(self._extract_tags, axis=1).tolist()

        vectorizer = TfidfVectorizer(min_df=1, max_df=0.95, sublinear_tf=True)
        matrix = vectorizer.fit_transform(docs)  # sparse CSR (n_movies × n_tags)

        self._tfidf_vectorizer = vectorizer
        self._tfidf_matrix = matrix
        self._tfidf_index = {k: i for i, k in enumerate(keys)}

        logger.info(f"TF-IDF matrix built: {matrix.shape[0]} movies × {matrix.shape[1]} tags.")

    def _tfidf_content_scores(self, rated_user_ratings: List[Tuple[str, float]], movies_to_predict: List[str]) -> np.ndarray:
        """
        Builds a user taste profile from their rated movies' TF-IDF vectors,
        then scores all candidate movies by cosine similarity.
        Falls back to Bayesian content scores if TF-IDF data is unavailable.
        """
        fallback = np.array([self.movie_score_map.get(m, 0.0) for m in movies_to_predict])

        if not hasattr(self, '_tfidf_matrix') or self._tfidf_matrix is None or not rated_user_ratings:
            return fallback

        user_avg = np.mean([r for _, r in rated_user_ratings])
        profile = None
        matched = 0

        for movie_title, rating in rated_user_ratings:
            idx = self._tfidf_index.get(movie_title)
            if idx is None:
                continue
            weight = rating - user_avg
            vec = self._tfidf_matrix[idx]       # sparse (1, n_tags)
            profile = vec * weight if profile is None else profile + vec * weight
            matched += 1

        if profile is None or matched == 0:
            logger.warning("TF-IDF: no rated movies found in feature matrix — falling back to Bayesian scores.")
            return fallback

        # Batch cosine similarity: (n_candidates, n_tags) · profile.T → (n_candidates,)
        candidate_indices = [self._tfidf_index.get(m) for m in movies_to_predict]
        has_index = [i is not None for i in candidate_indices]

        if not any(has_index):
            return fallback

        valid_indices = [i for i in candidate_indices if i is not None]
        candidate_matrix = self._tfidf_matrix[valid_indices]       # sparse
        dots = candidate_matrix.dot(profile.T).toarray().flatten()

        profile_norm = float(np.sqrt(profile.multiply(profile).sum()))
        row_norms = np.sqrt(np.array(candidate_matrix.multiply(candidate_matrix).sum(axis=1)).flatten())
        denom = profile_norm * row_norms + 1e-9
        sims = dots / denom

        # Map back to full candidate list (movies not in index get 0)
        scores = np.zeros(len(movies_to_predict))
        valid_pos = [i for i, ok in enumerate(has_index) if ok]
        scores[valid_pos] = sims

        # Normalize to [0, 10] to match the rating scale
        max_s = scores.max()
        if max_s > 0:
            scores = scores / max_s * 10.0

        logger.info(f"TF-IDF content scores computed from {matched} rated movies.")
        return scores

    def _compute_content_score(self, vote_average: float, vote_count: int) -> float:
        """
        Computes content score for a single movie using Bayesian average.
        Used for cold start movies not in the training set.

        :param vote_average: Average rating of the movie
        :param vote_count: Number of votes/ratings
        :return: Content score normalized to 0-10 scale
        """
        if not hasattr(self, '_content_score_params'):
            logger.warning("Content score parameters not available, using defaults")
            C = 7.0  # Assume average rating of 7/10
            m = 100  # Assume minimum of 100 votes
        else:
            C = self._content_score_params['mean_rating']
            m = self._content_score_params['min_votes']

        # Bayesian average: (v/(v+m) * R) + (m/(v+m) * C)
        weighted_score = (vote_count / (vote_count + m) * vote_average) + (m / (vote_count + m) * C)

        # Normalize to 0-10 using the same min/max computed during training
        if hasattr(self, '_content_score_params'):
            min_score = self._content_score_params.get('min_score', 0)
            max_score = self._content_score_params.get('max_score', 10)
            if max_score > min_score:
                weighted_score = (weighted_score - min_score) / (max_score - min_score) * 10

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
        self._validate_dataframes(ratings_df, movies_df)

        self.df_ratings = ratings_df
        self.df_movies = movies_df
        self._precompute_movie_scores()
        self._extract_movie_metadata()
        self._build_content_feature_matrix()

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
            gs = GridSearchCV(SVD, param_grid=param_grid,
                        measures=['rmse'], cv=3, n_jobs=1)

            gs.fit(data)

            self.best_params = gs.best_params['rmse']
            logger.info(f"GridSearch complete. Best RMSE: {gs.best_score['rmse']}")
            logger.info(f"Best parameters: {self.best_params}")

            results_df = pd.DataFrame(gs.cv_results)
            bundle_dir = os.path.dirname(bundle_path)
            bundle_name = os.path.splitext(os.path.basename(bundle_path))[0]
            results_path = os.path.join(bundle_dir, f"{bundle_name}_gridsearch_results.csv")
            try:
                results_df.to_csv(results_path, index=False)
                logger.info(f"GridSearch results saved to {results_path}")
            except OSError as e:
                logger.warning(f"Could not save GridSearch results to {results_path}: {e}")
            
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
        self.user_mapping = trainset._raw2inner_id_users

        model_bundle = {
            'model': self.model,
            'trainset_global_mean': self.trainset_global_mean,
            'item_mapping': self.item_mapping,
            'inverse_item_mapping': self.inverse_item_mapping,
            'user_mapping': self.user_mapping,
            'movie_score_map': self.movie_score_map,
            'all_movies_list': self.all_movies_list,
            'best_params': self.best_params,
            'movie_metadata': self.movie_metadata,
            'content_score_params': self._content_score_params,
            'tfidf_vectorizer': self._tfidf_vectorizer,
            'tfidf_matrix': self._tfidf_matrix,
            'tfidf_index': self._tfidf_index,
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

        try:
            if not os.path.exists(bundle_path):
                raise FileNotFoundError(f"Bundle file not found: {bundle_path}")

            with open(bundle_path, 'rb') as f:
                bundle = pickle.load(f)

            required_keys = ['model', 'trainset_global_mean', 'item_mapping',
                           'inverse_item_mapping', 'movie_score_map', 'all_movies_list']
            missing_keys = [key for key in required_keys if key not in bundle]

            if missing_keys:
                raise ValueError(f"Bundle is missing required keys: {missing_keys}")

            self.model = bundle['model']
            self.trainset_global_mean = bundle['trainset_global_mean']
            self.item_mapping = bundle['item_mapping']
            self.inverse_item_mapping = bundle['inverse_item_mapping']
            self.user_mapping = bundle.get('user_mapping', {})
            self.movie_score_map = bundle['movie_score_map']
            self.all_movies_list = bundle['all_movies_list']
            self.best_params = bundle.get('best_params')
            self.movie_metadata = bundle.get('movie_metadata')
            self._content_score_params = bundle.get('content_score_params')
            self._tfidf_vectorizer = bundle.get('tfidf_vectorizer')
            self._tfidf_matrix = bundle.get('tfidf_matrix')
            self._tfidf_index = bundle.get('tfidf_index', {})

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
        matched = 0

        if len(user_ratings) == 0:
            return user_vector, user_bias

        for movie_title, rating in user_ratings:
            if movie_title in self.item_mapping:
                inner_iid = self.item_mapping[movie_title]
                movie_factors = self.model.qi[inner_iid]
                movie_bias = self.model.bi[inner_iid]

                user_vector += (rating - self.trainset_global_mean - movie_bias) * movie_factors
                user_bias += (rating - self.trainset_global_mean - movie_bias)
                matched += 1

        if matched > 0:
            user_vector /= matched
            user_bias /= matched
        else:
            logger.warning(
                f"fold_in_user: 0/{len(user_ratings)} rated movies found in item_mapping. "
                f"CF scores will be identical for all users (item popularity only). "
                f"Sample user titles: {[m for m, _ in user_ratings[:5]]}. "
                f"Sample item_mapping titles: {list(self.item_mapping.keys())[:5]}"
            )

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
            
            prediction = self.trainset_global_mean
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
                # No content info available
                user_ratings_list = [r for _, r in user_ratings]
                fallback = np.mean(user_ratings_list) if user_ratings_list else self.trainset_global_mean
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

        self.movie_metadata[movie_title] = {
            'vote_average': vote_average,
            'vote_count': vote_count
        }
        if year_released is not None:
            self.movie_metadata[movie_title]['year_released'] = year_released

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
        user_id: Optional[str] = None,
        db_client = None,
        enrich_from_db: bool = False,
        exploration_pool: int = 3,
    ) -> pd.DataFrame:
        """
        Generates top-N recommendations for a new user based on their ratings.

        :param user_ratings: A list of tuples in the format [(movie_title, rating_val), ...]
        :param n: Number of recommendations to return.
        :param hybrid_weight: Balance between CF and content score (0.0 = only content, 1.0 = only CF).
        :param db_client: Optional MongoDB client instance for enriching results with full metadata
        :param enrich_from_db: If True, fetch full movie metadata from database
        :param exploration_pool: Multiplier for the candidate pool used in weighted sampling.
            A value of 3 (default) builds a pool of 3*n candidates and samples n from it,
            weighted by hybrid_score, so top movies are still most likely but results vary
            across runs. Set to 1 to disable exploration (always return the strict top-N).
        :return: DataFrame with top recommendations and their predicted scores.
        """
        # Separate genuinely rated movies (rating > 0) from unrated ones.
        # Rating=0 means "logged but not rated" — passing it to fold-in creates
        # a strongly negative user vector (~0 - global_mean ≈ -7) that surfaces
        # obscure/niche items rather than reflecting real taste.
        rated_user_ratings = [(m, r) for m, r in user_ratings if r > 0]
        n_user_ratings = len(rated_user_ratings)
        is_cold_start = n_user_ratings == 0

        if hybrid_weight is None:
            if is_cold_start:
                hybrid_weight = 0.0  # no rating signal — content only
            elif n_user_ratings < 5:
                hybrid_weight = 0.3
            elif n_user_ratings < 20:
                hybrid_weight = 0.5
            else:
                hybrid_weight = self.DEFAULT_HYBRID_WEIGHT

        logger.info(f"Generating {n} recommendations based on {n_user_ratings} rated movies (hybrid_weight={hybrid_weight}, cold_start={is_cold_start}).")

        user_rated_movies = {movie for movie, _ in user_ratings}
        movies_to_predict = [movie for movie in self.item_mapping if movie not in user_rated_movies]

        # Filter out short films (< 40 min) — they tend to dominate cold-start
        # results because they can have high vote_average on few votes.
        MIN_RUNTIME = 40
        if self.movie_metadata:
            movies_to_predict = [
                m for m in movies_to_predict
                if (self.movie_metadata.get(m, {}).get('runtime') or MIN_RUNTIME) >= MIN_RUNTIME
            ]

        logger.info(f"Predicting for {len(movies_to_predict)} unrated movies out of {len(self.item_mapping)} total.")

        inner_uid = self.user_mapping.get(user_id) if user_id else None
        if inner_uid is not None:
            user_factors = self.model.pu[inner_uid]
            user_bias = self.model.bu[inner_uid]
            logger.info(f"Using pre-trained factors for known user '{user_id}'.")
        else:
            user_factors, user_bias = self._fold_in_user(rated_user_ratings)
            logger.info(f"User '{user_id}' not in trainset — using fold-in with {n_user_ratings} rated movies.")

        if not np.any(user_factors):
            logger.warning("generate_recommendations: user_factors is all zeros — recommendations will NOT be personalized.")

        inner_iids = [self.item_mapping[movie] for movie in movies_to_predict]
        qi = self.model.qi[inner_iids]
        bi = self.model.bi[inner_iids]

        cf_scores = np.clip(
            qi @ user_factors + bi + user_bias + self.trainset_global_mean,
            self.RATING_SCALE_MIN, self.RATING_SCALE_MAX
        )

        # Use TF-IDF tag similarity as content score for users with rating signal;
        # fall back to Bayesian popularity score for pure cold-start.
        if rated_user_ratings:
            content_scores = self._tfidf_content_scores(rated_user_ratings, movies_to_predict)
        else:
            content_scores = np.array([self.movie_score_map.get(movie, 0.0) for movie in movies_to_predict])

        hybrid_scores = hybrid_weight * cf_scores + (1 - hybrid_weight) * content_scores

        recommendations_df = pd.DataFrame({
            'movie_title': movies_to_predict,
            'cf_score': cf_scores,
            'content_score': content_scores,
            'hybrid_score': hybrid_scores,
        })
        if exploration_pool > 1:
            pool_size = min(n * exploration_pool, len(recommendations_df))
            pool = recommendations_df.nlargest(pool_size, 'hybrid_score')
            min_score = pool['hybrid_score'].min()
            weights = pool['hybrid_score'] - min_score + 1e-6
            recommendations_df = pool.sample(n=min(n, len(pool)), weights=weights, replace=False)
            recommendations_df = recommendations_df.sort_values('hybrid_score', ascending=False)
        else:
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

