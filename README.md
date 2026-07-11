# Letterboxd Movie Recommender

> **Disclaimer:** This is a personal, non-commercial project built for learning purposes. It is not affiliated with, endorsed by, or associated with Letterboxd, TMDB, or any other platform referenced herein. No data is sold or monetized. All scraped content remains the property of its respective owners.


## Overview

It's finally the week-end, you open [Letterboxd](https://letterboxd.com/), a platform built specifically for ✨cinephiles✨, scroll through your watchlist, browse popular lists, check what your friends have been watching, and somehow still end up staring at a blank screen twenty minutes later with nothing picked. This project started from that frustration: rather than asking you to fill out a form or pick genres from a list, it reads your Letterboxd history directly and uses that as the input signal to tell *you*, specifically, what to watch *tonight*.

Under the hood this is a hybrid recommendation system: it scrapes the most active Letterboxd users each week to build a community ratings matrix, trains an SVD matrix factorization model on that data, and at request time folds your personal ratings into the learned latent space to generate predictions. Those predictions are blended with a Bayesian content score derived from TMDB metadata, genres, themes, and nanogenres scraped from Letterboxd itself. The entire pipeline is orchestrated by Apache Airflow, persisted in MongoDB, and delivered to the frontend via a FastAPI middleware using Redis pub/sub for async result delivery.

## Try it out

1. Go to the Webapp: [myletterboxdflicks.xyz](https://myletterboxdflicks.xyz)
2. Input your Letterboxd username when prompted.
3. Receive personalized recommendations and analytics based on your Letterboxd activity.


## Architecture

![architecture_diagram.png](assets%2Farchitecture_diagram.png)


**Key component responsibilities:**

| Component | Role |
|---|---|
| `dags/letterboxd_bulk_scraping.py` | Weekly collection of top 2000 users + movie enrichment |
| `dags/letterboxd_user_scraping.py` | On-demand per-user recommendation pipeline |
| `dags/update_popular_movies.py` | Daily Redis cache refresh for popular movies |
| `dags/release_schedule_scraping.py` | Daily scrape of upcoming releases |
| `prediction/recommendation_engine.py` | SVD model training, user folding, hybrid scoring |
| `processing/analytics/user_analytics.py` | 25+ DuckDB-based user analytics |
| `middleware/middleware.py` | FastAPI REST API, Airflow integration, auth |
| `messaging/redis_client.py` | Redis pub/sub publisher |
| `database/mongodb_client.py` | Singleton MongoDB client |


## Recommendation System

### Algorithm: Hybrid SVD + Bayesian Content Scoring

The recommender combines a **Collaborative Filtering (CF)** model with a **Content-Based Filtering (CBF)** score, blended by a configurable weight:

```python
hybrid_score = (hybrid_weight * cf_score) + ((1 - hybrid_weight) * content_score)
```

- Letterboxd users (have ratings history): `hybrid_weight = 0.9`
- New / cold-start users: `hybrid_weight = 0.7`


### Collaborative Filtering — SVD Matrix Factorization

**Library**: `scikit-surprise`
**Algorithm**: SVD (Singular Value Decomposition), matrix factorization over the user-item rating matrix.

**Hyperparameters (tuned via `RandomizedSearchCV`, 12 iterations, 3-fold CV):**

| Parameter | Value |
|---|---|
| `n_factors` | 100 |
| `n_epochs` | 30 |
| `lr_all` | 0.01 |
| `reg_all` | 0.02 |
| Rating scale | 0 – 10 |

**Training** (`RecommendationEngine.build_and_train_model()`):
1. Loads all ratings and movie metadata from MongoDB.
2. Validates data quality (minimum ~1,000 active users).
3. Runs `RandomizedSearchCV` for hyperparameter tuning on a `surprise.Dataset`.
4. Retrains SVD on the full trainset with winning hyperparameters.
5. Serializes the complete model bundle as a `.pkl` file containing:
   - Trained SVD model object
   - `item_mappings`: bidirectional `movie_title ↔ inner_iid` lookup
   - Precomputed content (Bayesian) scores per movie
   - Lightweight movie metadata
   - Content-score parameters for cold-start movies not in the training set

**Inference — User Folding** (for new/transient users not in the training matrix):

Rather than retraining, the system folds a user into the latent space at prediction time:

```python
user_vector = Σ (rating - global_mean - movie_bias) × movie_factors
user_vector /= num_ratings  # average across all rated items
```

The resulting user factor vector is then used to compute dot-product predictions against all unrated item factor vectors. This avoids retraining while still producing personalized scores.


### Content-Based Filtering — Bayesian Average

The content score is a **Bayesian weighted average** that shrinks low-vote movies towards the global mean, preventing noise from sparsely-reviewed titles:

```
content_score = (v / (v + m)) × R  +  (m / (v + m)) × C

Where:
  v = movie vote count
  R = movie average rating
  m = 70th percentile of vote count distribution (minimum votes threshold)
  C = global mean rating across all movies
```

**Features used for content scoring:**

| Category | Fields |
|---|---|
| Numeric | `vote_average`, `vote_count`, `popularity`, `year_released` |
| Categorical | `genres`, `themes`, `nanogenres`, `production_countries`, `spoken_languages` |
| Text | `overview` (bag-of-words after English stopword removal) |

The bag-of-words representation is constructed from concatenating overview text, genres, languages, and runtime tier, then stripping stopwords before vectorization.

> **TODO:** the current `_precompute_movie_scores()` implementation only uses `vote_average` / `vote_count` for the Bayesian formula above — the bag-of-words / text-feature scoring described here is not yet wired in.


### Content-Based Filtering — TF-IDF Taste Profile

For users with rating history, content scoring goes beyond the global Bayesian average: a **personalized taste profile** is built from TF-IDF vectors over each movie's genres, themes, and nanogenres, then compared against every candidate via cosine similarity.

**Building the profile** (`_tfidf_content_scores()`):
```
profile = Σ (rating - user_avg) × tfidf_vector(movie)   for each rated movie
```
Movies rated above the user's average contribute positively to the profile; movies rated below it contribute negatively — so a user's taste vector reflects what they liked *relative to their own scale*, not just what they watched.

**Scoring candidates:**
```
content_score(movie) = cosine_similarity(profile, tfidf_vector(movie))
```
Scores are normalized to the `[0, 10]` scale to stay compatible with `cf_score` in the hybrid blend.

- The TF-IDF matrix (genres + themes + nanogenres per movie) is precomputed once at training time and stored in the model bundle, so inference requires no recomputation.
- Falls back to the Bayesian content score (above) when a user has no rated movies in the feature matrix — e.g. pure cold-start users, or users whose entire history predates the current movie catalog.

This means the hybrid score for an active user blends three signals in practice: the SVD collaborative-filtering prediction, a personalized cosine-similarity taste match, and (as a fallback) global popularity.


### Engagement Weighting

Beyond raw ratings, the system uses engagement signals from Letterboxd to adjust the effective rating before passing it to the model:

**Additive weighting** (`apply_engagement_weights()`):

| Signal | Condition | Adjustment |
|---|---|---|
| `is_reviewed` | High rating + review | Upward boost |
| `is_reviewed` | Low rating + review | Downward boost |
| `is_liked` | Any | +0.3 |
| `is_rewatch` | Any | +0.7 |

All adjusted values are clipped to `[0.0, 10.0]`.

**Multiplicative amplification** (`apply_engagement_amplification()`):
- Applied relative to the midpoint (5.0) of the scale
- `is_reviewed`: 1.15× amplification
- `is_liked`: 1.10× amplification
- `is_rewatch`: 1.20× amplification

---

### Cold-Start Handling

| Scenario | Strategy |
|---|---|
| New user, known movies | User folding with `hybrid_weight = 0.7` (more content) |
| Known user, new movie (not in training) | Bayesian content score + user average fallback |
| Both new | Global popularity + Bayesian content score |

---

### Recommendation Generation (`generate_recommendations()`)

**Steps:**
1. Map movie titles to SVD inner item IDs via `item_mappings`.
2. Compute user latent vector via folding (described above).
3. Predict rating for every unrated movie in the catalog.
4. Compute hybrid score for each candidate.
5. Sort descending by hybrid score, return top-N with:
   - `cf_score`: SVD predicted rating
   - `content_score`: Bayesian average score
   - `hybrid_score`: weighted blend
   - Full movie metadata (poster, genres, links, etc.)

**Output size**: 24 recommendations for Letterboxd users, 48 for new/genre-based users.

## Apache Airflow Setup

Airflow orchestrates all data pipelines. The DAG server runs locally on the VPS and is exposed to the middleware at `http://localhost:8080/api/v1`.

### DAG 1 — `letterboxd_bulk_scraping_dag`

**Schedule**: `0 3 1 * *` (3:00 AM on the 1st of every month)

**Concurrency**: 4 parallel tasks

**Purpose**: Refresh the training dataset with fresh ratings from the most active Letterboxd users.

**Task graph:**

```
scraping_users_reviews
        │
        ▼
batching_movies_shows
        │
        ▼ (dynamic expansion)
scraping_movies_shows[batch_0] ─┐
scraping_movies_shows[batch_1]  ├─► cleanup_redis
scraping_movies_shows[batch_N] ─┘
```


### DAG 2 — `letterboxd_recommendation_dag` (`letterboxd_user_scraping`)

**Schedule**: None (triggered programmatically)

**Trigger method**: `POST http://localhost:8080/api/v1/dags/{dag_id}/dagRuns` with JSON config

**Purpose**: End-to-end per-user recommendation pipeline, executed on demand from the webapp.

**Trigger payload:**
```json
{
  "conf": {
    "username": "johndoe",
    "type": "letterboxd",
    "data_opt_out": false
  }
}
```

**Task graph:**

```
setup_context
      │
      ▼
scraping_user_reviews
      │
      ▼
load_pre_trained_model
      │
      ▼
get_user_recommendations ──► get_user_analytics
                  │                    │
                  └────────┬───────────┘
                           ▼
                     write_to_redis
```


### DAG 3 — `update_popular_movies`

**Schedule**: `0 6 * * *` (6:00 AM daily)

**Purpose**: Keep the "Popular Movies" widget current.

**Tasks:**
1. `fetch_top_reviewed_movies`: Queries MongoDB `movies` sorted by `histogram.total` descending, returns top 20.
2. `write_to_redis`: Stores the result as a JSON list in Redis key `popular_movies`.

### DAG 4 — `whentostream_daily_scraper`

**Schedule**: `0 5 * * *` (5:00 AM daily)

**Purpose**: Populate the release calendar for the webapp.

**Task — `scrape_and_publish_releases`:**
- Scrapes [whentostream.com] (https://whentostream.com/) for current month + next 2 months.
- Collects streaming releases and theatrical releases separately.
- Publishes to Redis queue `release_schedule`:
  ```json
  {
    "date": "2025-03-15",
    "streaming_releases": [{"title": "...", "slug": "...", "poster_url": "...", "url": "..."}],
    "theater_releases": [...],
    "scraped_at": "2025-02-01T05:00:00Z"
  }
  ```


## Redis Setup

Redis serves two distinct roles: **pub/sub message queue** for async recommendation delivery, and **ephemeral caching** for frequently read data.

### Keys and Data Structures

#### Pub/Sub Queues

**`recs`** (env: `REDIS_QUEUE_RECS`)
- **Type**: Queue (list-based pub/sub)
- **Written by**: `write_to_redis` task in the recommendation DAG
- **Read by**: FastAPI middleware (`/recommend/trigger` subscriber)
- **Payload schema:**
  ```json
  {
    "username": "string",
    "user_recommendation": [
      {
        "movie_title": "string",
        "cf_score": 8.4,
        "content_score": 7.1,
        "hybrid_score": 8.13,
        "genres": ["Drama"],
        "poster_url": "string",
        "tmdb_link": "string",
        "year_released": 2019
      }
    ],
    "user_analytics": { ... }
  }
  ```
- **Serialization**: JSON with numpy type coercion (`int64` → `int`, `float32` → `float`)

**`release_schedule`** (env: `REDIS_QUEUE_RELEASES`)
- **Type**: Queue
- **Written by**: `whentostream_daily_scraper` DAG
- **Read by**: `/calendar/releases` middleware endpoint
- **Payload**: Streaming + theatrical releases by date

#### Cache Keys

**`popular_movies`**
- **Type**: String (JSON list)
- **Written by**: `update_popular_movies` DAG (daily at 6 AM)
- **Read by**: `/recommend/popular` endpoint
- **Content**: Top 20 movies sorted by total Letterboxd review count

**`recently_recommended`**
- **Type**: List
- **Written by**: Recommendation DAG after each run
- **Read by**: `/recommend/recent` endpoint
- **Retention**: Last 20 entries (trimmed by `cleanup_redis` task)

**`top_picks`**
- **Type**: Hash / JSON dict
- **Written by**: `/recommend/add-top-pick` endpoint
- **Read by**: `/recommend/top-picks` endpoint
- **Content**: `{movie_id: {title, count, poster_url, ...}}`
- **Retention**: Top 20 by selection count (trimmed monthly)

The middleware blocks on the queue with a timeout, returning a 504 if Airflow does not publish within the deadline.


## User Analytics

Analytics are computed entirely in-process using **DuckDB** with no separate analytics database required. DuckDB tables are instantiated from Pandas DataFrames loaded from MongoDB, queries run in memory, and results are returned as dicts.

**Computed metrics (25+):**

| Category | Metrics |
|---|---|
| Volume | `movies_reviewed`, `shows_reviewed`, `minutes_watched`, `first_watches`, `rewatches` |
| Activity patterns | `longest_streak`, `mean_daily_reviews`, `number_daily_reviews_over_mean`, day-of-week distribution |
| Rating behavior | Average rating per year, per decade, rating vs. public consensus scatter data |
| Histogram | User rating distribution superimposed on community distribution |
| Genre/theme breakdown | Top 10 genres, themes, nanogenres by watch count and by average rating |
| Geographic | Top 10 production countries, top 10 spoken languages |
| Era analysis | Release decade distribution with rolling averages |
| Trending | Popularity vs. user rating scatter (identifies contrarian/mainstream taste) |
| Exploration | Theme treemap data, nanogenre correlation matrix (positive/negative affinity) |
| Time series | Rating trend over time (rolling average) |


## Data Pipeline — Scraping

### User Reviews Scraping (`processing/scraping/user_reviews_scraping.py`)

- **Proxy**: rotating proxy (env: `PROXY_URL`)
- **Rate limiting**: configurable `REQUESTS_PER_SECONDS` + `MAX_CONCURRENT`
- **Pages scraped per user:**
  - `/members/popular/this/month/page/{n}` — discover active users
  - `/{username}/` — profile (follower/following counts)
  - `/{username}/films/diary/by/added/page/{n}` — chronological ratings
- **Fields extracted**: username, user_id, rating (0–10), date, `is_review`, `is_liked`, `is_rewatch`

### Movie Scraping (`processing/scraping/movies_scraping.py`)

- **Letterboxd endpoints:**
  - `/film/{slug}/` — type, year, LB rating
  - `/film/{slug}/themes/` — curated theme tags
  - `/film/{slug}/nanogenres/` — fine-grained genre tags
  - `/csi/film/{id}/rating-histogram/` — full rating distribution
- **TMDB API** (`api.themoviedb.org/3/{type}/{id}`):
  - `vote_average`, `vote_count`, `popularity`, `overview`
  - `runtime`, `release_date`, `poster_path`
  - `genres`, `production_countries`, `spoken_languages`
  - `imdb_id`


## MongoDB Schema

**Collection: `users`**
```json
{
  "username": "string (unique)",
  "user_id": "string (UUID)",
  "profile_url": "string",
  "follower_count": "int",
  "following_count": "int"
}
```

**Collection: `ratings`**
```json
{
  "user_id": "string (UUID FK)",
  "movie_title": "string",
  "rating_val": "float (0–10)",
  "rating_date": "string (dd-mm-yyyy)",
  "is_review": "bool",
  "is_liked": "bool",
  "is_rewatch": "bool"
}
```

**Collection: `movies`**
```json
{
  "movie_title_formatted": "string (unique slug)",
  "movie_title": "string",
  "type": "movie | shows | none",
  "year_released": "int",
  "imdb_id": "string",
  "tmdb_id": "string",
  "lb_rating": "float",
  "histogram": {
    "0": "int", "0.5": "int", "...", "10": "int",
    "total": "int"
  },
  "genres": ["string"],
  "themes": ["string"],
  "nanogenres": ["string"],
  "production_countries": ["string"],
  "spoken_languages": ["string"],
  "vote_average": "float",
  "vote_count": "int",
  "popularity": "float",
  "overview": "string",
  "runtime": "int (minutes)",
  "release_date": "date",
  "poster_url": "string",
  "last_updated": "datetime"
}
```

**Collection: `movies_embeddings`** (reserved for semantic search)
```json
{
  "_id": "string (movie_title_formatted)",
  "embedding": "[float] (L2-normalized vector)"
}
```

**NB :** the Semantic Search functionnality is still a WIP.

**Connection**: MongoDB Atlas (`mongodb+srv`) with TLS via certifi. `MongoDBClient` is a process-level singleton to reuse the connection across Airflow task instances.


## Middleware API

The FastAPI middleware (`middleware/middleware.py`) bridges the frontend, Airflow, and Redis.

**Endpoints:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/recommend/trigger` | Trigger Airflow DAG, block on Redis queue, return recs |
| `POST` | `/recommend/fallback` | Genre + min-rating content-only recommendations |
| `GET` | `/recommend/recent` | Recently recommended movies from Redis |
| `GET` | `/recommend/popular` | Top 20 movies from Redis cache |
| `GET` | `/recommend/random` | Random movies from MongoDB |
| `GET` | `/recommend/top-picks` | User-saved top picks from Redis |
| `POST` | `/recommend/add-top-pick` | Save movie to top picks |
| `POST` | `/recommend/remove-top-pick` | Remove movie from top picks |
| `GET` | `/calendar/releases` | Upcoming streaming + theatrical releases |
| `GET` | `/health` | Health check |
| `GET` | `/announcements` | System announcements |


## Deployment

- **Platform**: Single VPS
- **Process manager**: systemd / shell scripts in `vps/`
- **Reverse proxy**: Nginx (`vps/nginx.sh`)
- **Airflow**: Standalone mode (`vps/airflow.sh`)
- **Redis**: System service (`vps/redis.sh`)
- **Frontend**: Vite build served via Nginx
- **CI/CD**: GitHub Actions — lint + test on push, then deploy to VPS on merge to `main`


## Acknowledgments

- User reviews and ratings scraped from [Letterboxd](https://letterboxd.com/).
- Movie and TV metadata via the [TMDB API](https://www.themoviedb.org/documentation/api).
- Upcoming release data from [WhenToStream.com](https://whentostream.com/).
