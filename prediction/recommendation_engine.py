from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from surprise import SVD, Dataset, Reader
from surprise.model_selection import train_test_split, GridSearchCV
import pickle
import os
from logger import setup_logger

logger = setup_logger("../logs/recommendation_engine.log", "RecommendationEngine")

class RecommendationEngine:
    """
    A hybrid recommendation engine trained on a fixed set of active users (e.g., 4000).
    Can generate predictions and recommendations for any user based on their ratings.
    """

    def __init__(self, ratings_df, movies_df):
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

    def build_and_train_model(self, ratings_df, movies_df, bundle_path, perform_grid_search=True):
        """
        Monthly Training Job: Trains the model and saves a complete bundle to disk.
        
        :param perform_grid_search: If True, runs a GridSearchCV to find optimal hyperparameters.
                                    If False, uses the previously found best_params or defaults.
        """
        self.df_ratings = ratings_df
        self.df_movies = movies_df
        self._precompute_movie_scores()

        reader = Reader(rating_scale=(0, 10))
        data = Dataset.load_from_df(self.df_ratings[['user_id', 'movie_title', 'rating_val']], reader)
        
        # --- HYPERPARETER TUNING (GRID SEARCH) ---
        if perform_grid_search:
            logger.print("Starting GridSearchCV for hyperparameter tuning...")
            param_grid = {
                'n_factors': [50, 100, 150],
                'n_epochs': [20, 30],
                'lr_all': [0.005, 0.01],
                'reg_all': [0.02, 0.1]
            }
            gs = GridSearchCV(SVD, param_grid, measures=['rmse', 'mae'], cv=3, n_jobs=-1, joblib_verbose=1)
            gs.fit(data)
            
            self.best_params = gs.best_params['rmse']
            logger.print(f"GridSearch complete. Best RMSE: {gs.best_score['rmse']}")
            logger.print(f"Best parameters: {self.best_params}")
            
            results_df = pd.DataFrame(gs.cv_results)
            results_df.to_csv(bundle_path.replace('.pkl', '_gridsearch_results.csv'), index=False)
            
        else:
            if self.best_params is None:
                self.best_params = {'n_factors': 100, 'n_epochs': 30, 'lr_all': 0.01, 'reg_all': 0.02}
                logger.print(f"Using default parameters: {self.best_params}")

        # --- FINAL MODEL TRAINING ---
        trainset = data.build_full_trainset()
        logger.print("Training final model on the entire dataset with best parameters...")
        
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
            'best_params': self.best_params  # Also save the best params in the bundle
        }

        os.makedirs(os.path.dirname(bundle_path), exist_ok=True)
        with open(bundle_path, 'wb') as f:
            pickle.dump(model_bundle, f)
        
        logger.print(f"Final model training complete. Bundle saved to {bundle_path}")
        return bundle_path

    def load_bundle(self, bundle_path):
        """
        Production Server: Loads a complete model bundle from disk.
        This is called when your server starts up.
        """
        logger.print(f"Loading model bundle from {bundle_path}")
        with open(bundle_path, 'rb') as f:
            bundle = pickle.load(f)

        self.model = bundle['model']
        self.trainset_global_mean = bundle['trainset_global_mean']
        self.item_mapping = bundle['item_mapping']
        self.inverse_item_mapping = bundle['inverse_item_mapping']
        self.movie_score_map = bundle['movie_score_map']
        self.all_movies_list = bundle['all_movies_list']
        self.best_params = bundle['best_params'] # Load the best params as well
        
        logger.print("Model bundle loaded successfully.")
        return self

    def _fold_in_user(self, user_ratings):
        """
        Creates a personalized user factor vector for a new user based on their ratings.

        :param user_ratings: A list of tuples in the format [(movie_title, rating_val), ...]
        :return: A personalized factor vector for the new user.
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

                # Update user vector and bias
                user_vector += (rating - self.model.trainset.global_mean - movie_bias) * movie_factors
                user_bias += (rating - self.model.trainset.global_mean - movie_bias)
        
        user_vector /= num_ratings
        user_bias /= num_ratings
        
        return user_vector, user_bias

    def predict_rating_for_new_user(self, user_ratings, movie_title):
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
            
            prediction = np.clip(prediction, 0, 10)
            return prediction
        else:
            user_ratings_list = [r for _, r in user_ratings]
            return np.mean(user_ratings_list) if user_ratings_list else self.model.trainset.global_mean

    def generate_recommendations(self, user_ratings, n=10, hybrid_weight=0.7):
        """
        Generates top-N recommendations for a new user based on their ratings.

        :param user_ratings: A list of tuples in the format [(movie_title, rating_val), ...]
        :param n: Number of recommendations to return.
        :param hybrid_weight: Balance between CF and content score (0.0 = only content, 1.0 = only CF).
        :return: DataFrame with top recommendations and their predicted scores.
        """
        logger.info(f"Generating {n} recommendations for a new user based on {len(user_ratings)} ratings.")
        
        all_movies = list(self.item_mapping.keys())
        user_rated_movies = set([movie for movie, _ in user_ratings])
        movies_to_predict = [movie for movie in all_movies if movie not in user_rated_movies]
        
        logger.debug(f"Predicting for {len(movies_to_predict)} unrated movies.")

        user_factors, user_bias = self._fold_in_user(user_ratings)
        
        predictions = []
        for movie in movies_to_predict:
            if movie in self.item_mapping:
                inner_iid = self.item_mapping[movie]
                movie_factors = self.model.qi[inner_iid]
                movie_bias = self.model.bi[inner_iid]
                
                cf_score = self.model.trainset.global_mean + user_bias + movie_bias + np.dot(user_factors, movie_factors)
                cf_score = np.clip(cf_score, 0, 10)
                
                content_score = self.movie_score_map.get(movie, 0.0) 

                hybrid_score = (hybrid_weight * cf_score) + ((1 - hybrid_weight) * content_score)
                predictions.append((movie, cf_score, content_score, hybrid_score))

        recommendations_df = pd.DataFrame(predictions, columns=['movie_title', 'cf_score', 'content_score', 'hybrid_score'])
        recommendations_df = recommendations_df.sort_values('hybrid_score', ascending=False).head(n)

        final_output = recommendations_df.merge(self.df_movies, on='movie_title', how='left')
        
        return final_output[
            ['movie_title', 'hybrid_score', 'cf_score', 'content_score', 'year_released', 'vote_average']
        ]

        #TODO : Content Based Filtering

