import string
import os
import re
from pathlib import Path
from datetime import datetime

import numpy as np

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "was", "are", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "not", "no", "nor",
    "so", "yet", "both", "either", "neither", "as", "if", "then", "than",
    "that", "this", "these", "those", "it", "its", "he", "she", "they",
    "we", "you", "i", "me", "him", "her", "us", "them", "my", "your",
    "his", "our", "their", "what", "which", "who", "whom", "when", "where",
    "why", "how", "all", "each", "every", "any", "some", "more", "most",
    "other", "into", "through", "during", "about", "after", "before",
}


def remove_stopwords(text: str) -> str:
    """
    Removes common English stopwords and punctuation from text.
    :return: str : cleaned text
    """
    text = text.lower().translate(str.maketrans("", "", string.punctuation))
    return " ".join(word for word in text.split() if word not in STOPWORDS)


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

def load_latest_model(models_dir: str = "../prediction/models"):
    """
    Automatically loads the latest model based on filename pattern containing week, month and year.

    Args:
        models_dir (str): Directory containing model files (default: "../prediction/models")

    Returns:
        Loaded model object or None if no model found
    """
    pattern = "svd_model_*_*_*.pkl"
    models_path = Path(models_dir)
    model_files = list(models_path.glob(pattern))

    if not model_files:
        print(f"No model files found matching pattern: {pattern}")
        return None
    dated_models = []
    date_pattern = r"svd_model_(\d{1,2})_(\d{1,2})_(\d{4})\.pkl"

    for file in model_files:
        match = re.search(date_pattern, file.name)
        if match:
            week, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            dated_models.append((file, (year, month, week)))

    if not dated_models:
        print("No valid dated model files found")
        return None

    dated_models.sort(key=lambda x: x[1], reverse=True)

    latest_file, (year, month, week) = dated_models[0]

    print(f"Loading latest model: {latest_file.name} (week {week}, {datetime(year, month, 1).strftime('%B %Y')})")
    
    return str(latest_file)

