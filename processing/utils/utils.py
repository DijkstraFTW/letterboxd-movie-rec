import string
import os
import datetime
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