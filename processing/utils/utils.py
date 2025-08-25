import string
import os
import datetime

import numpy as np
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize


def remove_stopwords(text):
    """
    Removes stopwords and punctuation from a string
    :return: str : the text filtered
    """

    words = word_tokenize(str(text))
    stop_words = set(stopwords.words('english'))
    filtered_words = [word for word in words if word.lower() not in stop_words]
    filtered_text = ' '.join(filtered_words)
    translator = str.maketrans('', '', string.punctuation)
    filtered_text = filtered_text.translate(translator)
    filtered_text = filtered_text.replace("  ", " ")

    return filtered_text


def create_bag_of_words(x):
    """
    Combines multiple words into a single bag of words
    :return: str : the bag of words
    """

    overview = x.get('overview_cleaned', '')
    movie_type = str(x.get('type', ''))
    genres = " ".join(x.get('genres', [])) if isinstance(x.get('genres'), list) else ''
    production_countries = " ".join(x.get('production_countries', [])) if isinstance(x.get('production_countries'),
                                                                                     list) else ''
    spoken_languages = " ".join(x.get('spoken_languages', [])) if isinstance(x.get('spoken_languages'), list) else ''
    runtime = str(x.get('runtime', ''))

    return "".join(
        [overview, " ", movie_type, " ", genres, " ", production_countries, " ", spoken_languages, " ", runtime])


def select_last_model(directory):
    """
    Selects the most recent collaborative filtering model
    :return: object : path of the latest collaborative filtering model
    """

    list_of_files = os.listdir(directory)

    if not list_of_files:
        return None
    list_of_files = [file for file in list_of_files if file.endswith('.pkl')]

    if not list_of_files:
        return None

    latest_model = max(list_of_files, key=lambda x: datetime.strptime(x.split('_')[-1].split('.')[0], "%Y%m%d%H%M%S"))
    return os.path.join(directory, latest_model)


def val2stars(index):
    """
    Converts a numerical value to a star rating
    :return: str : the star rating
    """
    return f"{index * 2}"


def default_converter(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

def load_latest_model(models_dir: str):
    """
    Automatically loads the latest model based on filename pattern containing month and year.
    
    Args:
        models_dir (str): Directory containing model files
        pattern (str): Filename pattern to match (e.g., "svd_model_*_*.pkl")
    
    Returns:
        Loaded model object or None if no model found
    """
    models_dir="../prediction/models"
    pattern="svd_model_*_*.pkl"
    models_path = Path(models_dir)
    model_files = list(models_path.glob(pattern))
    
    if not model_files:
        print(f"No model files found matching pattern: {pattern}")
        return None
    dated_models = []
    date_pattern = r"svd_model_(\d{1,2})_(\d{4})\.pkl"
    
    for file in model_files:
        match = re.search(date_pattern, file.name)
        if match:
            month, year = int(match.group(1)), int(match.group(2))
            dated_models.append((file, datetime(year, month, 1)))
    
    if not dated_models:
        print("No valid dated model files found")
        return None
    
    dated_models.sort(key=lambda x: x[1], reverse=True)
    
    latest_file, latest_date = dated_models[0]
    
    print(f"Loading latest model: {latest_file.name} (from {latest_date.strftime('%B %Y')})")
    
    try:
        with open(latest_file, 'rb') as f:
            model = pickle.load(f)
        print("Model loaded successfully!")
        return model
    except Exception as e:
        print(f"Error loading model: {e}")
        return None

