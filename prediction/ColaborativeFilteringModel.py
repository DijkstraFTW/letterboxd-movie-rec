import pickle
from datetime import datetime

from sklearn.model_selection import train_test_split
from surprise import (Reader, Dataset, SVDpp, accuracy)
from tqdm import tqdm


class ColaborativeFiltering:

    def __init__(self, model_path):
        self.model = pickle.load(model_path)

    def prepare_dataset(self, df_ratings):
        """
        Prepares the ratings data for training and testing
        :rtype: returns the training set and the testing set
        """

        # Splitting the ratings data for training and testing
        train_df, test_df = train_test_split(df_ratings, test_size=0.25, random_state=42)
        reader = Reader(rating_scale=(1, 10))
        train_data = Dataset.load_from_df(train_df[["user_id_int", "rating_val", "movie_id_int"]], reader)
        test_data = Dataset.load_from_df(test_df[["user_id_int", "rating_val", "movie_id_int"]], reader)

        trainset = train_data.build_full_trainset()
        testset = test_data.build_full_trainset().build_testset()

        print(f"Training set succesfully loaded !")

        return trainset, testset

    def train_model(self, trainset, testset):
        """
        Fits an SVDpp colaborative filtering model using the user ratings
        :rtype: str: returns the saved model path
        """

        # Model parameters
        n_factors = 150
        n_epochs = 35
        lr_all = 0.012
        reg_all = 0.15

        # Training the SVDpp model
        algo = SVDpp(n_factors=n_factors, n_epochs=n_epochs, lr_all=lr_all, reg_all=reg_all)

        for epoch in tqdm(range(n_epochs)):
            algo.fit(trainset)

        # Training metrics
        predictions = algo.test(testset)
        rmse_value = accuracy.rmse(predictions)

        print(f"RMSE score : {rmse_value}")
        print("Model trained successfully !")

        # Saving the model
        model_filename = f"models/colab_filtering_{datetime.now().strftime("%Y%m%d%H%M%S")}.pkl"
        with open(model_filename, 'wb') as file:
            pickle.dump(algo, file)

        print(f"Model saved successfully at {model_filename}!")

        return model_filename
