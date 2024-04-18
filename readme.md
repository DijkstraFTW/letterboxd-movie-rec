# Letterboxd Movie Recommender


## Overview

The Letterboxd Movie Recommender System is a hybrid recommendation system that suggests movies to users based on their Letterboxd activity. The system combines collaborative filtering and content-based filtering techniques to provide personalized and diverse movie recommendations.

## IN PROGRESS
- Modules tests
- Content-based filtering
- Webapp
- Webapp integration deployment
- Monitoring
- Logging

## Try it out

1. Go to the Webapp: [Letterboxd Movie Recommender](https://letterboxd-movie-recommender.herokuapp.com/) ( NOT FUNCTIONAL YET )
2. Input your Letterboxd username when prompted.
3. Receive personalized recommendations and analytics based on your Letterboxd activity.


## Features

- **User Input:** Users can input their Letterboxd username to receive personalized movie recommendations as well as various analytics of their logged movies and TV shows.

- **Hybrid Recommendation Model:** The system leverages both collaborative filtering and content-based filtering to enhance the accuracy and diversity of movie and TV show suggestions.

- **User Profiles:** The system analyzes user profiles, including ratings, reviews, and watch history, to understand user preferences.

- **Movie Database:** Recommendations are generated from an extensive database of movies and TV shows, based on TMDB (The Movie Database).

## Architecture

The system consists of the following components:

![shapes at 24-04-18 11.39.59.png](..%2F..%2F..%2FDownloads%2Fshapes%20at%2024-04-18%2011.39.59.png)

- **Data Collection DAG:** The system fetches the 4000 most active monthly users on Letterboxd and scrapes their reviews. It then collects movie and show data and enriches it with features from TMDB. 
- **Recommendation DAG:** Using the Aiflow REST API, the user profile associated with the Letterboxd username is scraped. The recommendation model then generates personalized movie and TV show suggestions based on user profiles and movie features. The analytics module provides insights into the user's activity using DuckDB. Afterward, the recommendation and analytics data are pushed to a Redis queue.
- **Recommendation Model:** The hybrid recommendation model generates personalized movie suggestions based on user profiles and movie features.
- **React app:** The web application provides an interface for users to input their Letterboxd username and receive movie recommendations and analytics based on their activity.
- **MongoDB:** The system stores user profiles, movie features, and recommendations on MongoDB.
- **Deployment:** The data collection and recommendation system is deployed on AWS, while the Webapp is deployed on Heroku.
- **CI/CD:** The system follows continuous integration and continuous deployment practices to automate testing, deployment. The DAG files as well as the data collection and recommendation modules are linted (flak8, black) and tested (pytest) using GitHub Actions, and deployed on their respective EC2 instances. The Webapp is deployed on Heroku. 

## Recommendation Model

The recommendation model incorporates collaborative filtering, considering user interactions, and content-based filtering, analyzing movie features. The hybrid approach enhances the accuracy of suggestions.

// TODO: Add more details.

## Acknowledgments

- The system collects user reviews and ratings from [Letterboxd](https://letterboxd.com/).
- The system uses the [TMDB API](https://www.themoviedb.org/documentation/api) to enrich movie and TV show data with features.
