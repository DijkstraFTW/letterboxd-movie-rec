import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown } from "lucide-react"
import ChartPieSimple from "./ChartPieSimple.tsx";
import ChartPieSimpleToggable from "./ChartPieSimpleToggable.tsx";
import BarChartDefault from "./BarChartDefault.tsx";
import BarChartDefaultYears from "./BarChartDefaultYears.tsx";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../shadcn/components/ui/card.tsx"
import MovieCarousel from "./MovieCarousel.tsx";
import ChartBarMixedMostWatched from "./ChartBarMixedMostWatched.tsx";
import ChartBarMixedDecades from "./ChartBarMixedDecades.tsx";


type ChartConfig = {
  [key: string]: {
    label: string;
    color?: string;
  };
};

function Counter({ end, duration = 2000 }: { end: number; duration?: number }) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    let start: number | null = null;
    const step = (timestamp: number) => {
      if (!start) start = timestamp;
      const progress = Math.min((timestamp - start) / duration, 1);

      const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      setValue(Math.floor(eased * end));

      if (progress < 1) requestAnimationFrame(step);
    };

    requestAnimationFrame(step);
  }, [end, duration]);

  return <>{value}</>;
}

const viewingHabitsConfig = {
  new_watch: { label: "New Adventures", color: "var(--color-new-watch)" },
  rewatch: { label: "Comfort Views", color: "var(--color-rewatch)" },
} satisfies ChartConfig


const tasteAlignmentConfig = {
  above_avg: { label: "Your Unique Loves", color: "var(--color-above-avg)" },
  similar_avg: { label: "In Agreement", color: "var(--color-similar-avg)" },
  below_avg: { label: "Your Contrarian Takes", color: "var(--color-below-avg)" },
} satisfies ChartConfig

const weeklyRhythmConfig = {
  count: { label: "Movies Watched", color: "var(--chart-1)" },
} satisfies ChartConfig


const mostWatchedMoviesConfig = {
  count: { label: "Watch Count" },
} satisfies ChartConfig


const cleanStr = (s: string) => s.replace(/['"]/g, '').trim();

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

type UserMetricsProps = {
  data: {
    movies_reviewed: number;
    shows_reviewed: number;
    minutes_watched: number;
    max_films_in_a_day: number;
    longest_streak: number;
    first_watches?: number;
    rewatches?: number;
    average_watched_per_day_of_week?: Array<{ day_of_week: number; average_movies_watched: number }>;
    average_rating_decade?: Array<{ decade: number; average_rating: number }>;
    top_10_genres_by_watch_count?: Array<{ unnested_genre: string; watch_count: number }>;
    top_10_genres_by_average_rating?: Array<{ genre: string; avg_rating: number }>;
    top_10_nanogenres_by_watch_count?: Array<{ unnested_nanogenres: string; watch_count: number }>;
    top_10_nanogenres_by_average_rating?: Array<{ nanogenre: string; avg_rating: number }>;
    top_10_spoken_language_by_watch_count?: Array<{ lang: string; count: number }>;
    top_10_spoken_countries_by_average_rating?: Array<{ unnested_lang: string; average_rating: number }>;
    average_rating_per_year?: Array<{ year_released: number; average_rating: number }>;
    top_10_most_watched?: Array<{ title: string; count: number; poster_url?: string }>;
    top_10_themes_by_watch_count?: Array<{ unnested_themes: string; watch_count: number }>;
    top_10_themes_by_average_rating?: Array<{ theme: string; avg_rating: number }>;
    top_10_production_country_by_watch_count?: Array<{ country: string; count: number }>;
    top_10_production_country_by_average_rating?: Array<{ unnested_country: string; average_rating: number }>;
    taste_alignment?: { above_avg: number; similar_avg: number; below_avg: number };
    top_10_greater_than_average_rating?: Array<{ movie_title: string; movie_title_formatted?: string; rating_val: number; lb_rating?: number; vote_average: number; poster_url: string; histogram?: any; runtime?: string; genres?: string[]; year_released?: number; margin: number }>;
    top_10_lower_than_average_rating?: Array<{ movie_title: string; movie_title_formatted?: string; rating_val: number; lb_rating?: number; vote_average: number; poster_url: string; histogram?: any; runtime?: string; genres?: string[]; year_released?: number; margin: number }>;
  };
  sectionTitle: string;
};

export const UserMetrics = ({ data, sectionTitle }: UserMetricsProps) => {
  const hoursWatched = Math.round((data.minutes_watched ?? 0) / 60);

  const computedTasteAlignmentData = data.taste_alignment
    ? [
        { category: "above average", count: data.taste_alignment.above_avg },
        { category: "similar to the average", count: data.taste_alignment.similar_avg },
        { category: "below average", count: data.taste_alignment.below_avg },
      ]
    : [];

  const computedViewingHabitsData = data.first_watches != null && data.rewatches != null
    ? [
        { category: "new watches", count: data.first_watches },
        { category: "rewatches", count: data.rewatches },
      ]
    : [];

  const computedWeeklyRhythmData = data.average_watched_per_day_of_week?.map(d => ({
    day: DAY_NAMES[(d.day_of_week - 1) % 7],
    count: d.average_movies_watched,
  })) ?? [];

  const computedRatingsPerDecadeData = data.average_rating_decade?.map(d => ({
    decade: String(Math.round(d.decade)),
    avg_rating: d.average_rating,
  })) ?? [];

  const computedTopGenresData = data.top_10_genres_by_average_rating?.map(d => ({
    genre: cleanStr(d.genre), count: d.avg_rating,
  })) ?? [];
  const computedTopGenresAltData = data.top_10_genres_by_watch_count?.map(d => ({
    genre: cleanStr(d.unnested_genre), count: d.watch_count,
  })) ?? [];

  const computedTopNanogenresData = data.top_10_nanogenres_by_average_rating?.map(d => ({
    nanogenre: cleanStr(d.nanogenre), count: d.avg_rating,
  })) ?? [];
  const computedTopNanogenresAltData = data.top_10_nanogenres_by_watch_count?.map(d => ({
    nanogenre: cleanStr(d.unnested_nanogenres), count: d.watch_count,
  })) ?? [];

  const computedFavoriteLanguageData = data.top_10_spoken_countries_by_average_rating?.map(d => ({
    language: cleanStr(d.unnested_lang), count: d.average_rating,
  })) ?? [];
  const computedFavoriteLanguageAltData = data.top_10_spoken_language_by_watch_count?.map(d => ({
    language: cleanStr(d.lang), count: d.count,
  })) ?? [];

  const computedRatingsPerYearData = (data.average_rating_per_year ?? []).filter(d => d.year_released > 0);

  const computedMostWatchedMoviesData = data.top_10_most_watched ?? [];

  const computedFavoriteThemesData = data.top_10_themes_by_average_rating?.map(d => ({
    theme: cleanStr(d.theme), count: d.avg_rating,
  })) ?? [];
  const computedFavoriteThemesAltData = data.top_10_themes_by_watch_count?.map(d => ({
    theme: cleanStr(d.unnested_themes), count: d.watch_count,
  })) ?? [];

  const computedTopCountriesData = data.top_10_production_country_by_average_rating?.map(d => ({
    country: cleanStr(d.unnested_country), count: d.average_rating,
  })) ?? [];
  const computedTopCountriesAltData = data.top_10_production_country_by_watch_count?.map(d => ({
    country: cleanStr(d.country), count: d.count,
  })) ?? [];

  const higherRatedMovies = data.top_10_greater_than_average_rating ?? [];
  const lowerRatedMovies = data.top_10_lower_than_average_rating ?? [];

  return (
    <div className="rounded-md text-[#e5e3e2]">
      <div className="flex flex-col h-full bg-[#111111] p-4 rounded-xl">
        <h1 className="text-2xl font-bold mb-4 text-left">{sectionTitle}</h1>
        <div className="grid gap-3 mb-8">
          <div className="grid grid-cols-2 gap-6 md:grid-cols-4 text-center">
            <div className="flex flex-col items-center">
              <span className="text-4xl font-bold">
                <Counter end={data.movies_reviewed + data.shows_reviewed} />
              </span>
              <span className="text-muted-foreground">reviews</span>
            </div>
            <div className="flex flex-col items-center">
              <span className="text-4xl font-bold">
                <Counter end={hoursWatched} />
              </span>
              <span className="text-muted-foreground">total watched hours</span>
            </div>
            <div className="flex flex-col items-center">
              <span className="text-4xl font-bold">
                <Counter end={data.max_films_in_a_day} />
              </span>
              <span className="text-muted-foreground">most films in a single day</span>
            </div>
            <div className="flex flex-col items-center">
              <span className="text-4xl font-bold">
                <Counter end={data.longest_streak} />
              </span>
              <span className="text-muted-foreground">longest review streak in days</span>
            </div>
          </div>
        </div>
        <div className="grid gap-3 mb-8">
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
            <ChartPieSimple
              title="Viewing Habits"
              description="Your balance between new discoveries and beloved favorites."
              data={computedViewingHabitsData}
              config={viewingHabitsConfig}
              dataKey="count"
              nameKey="category"
            />
            <ChartPieSimple
              title="Taste Alignment"
              description="See how your unique taste compares to the popular consensus."
              data={computedTasteAlignmentData}
              config={tasteAlignmentConfig}
              dataKey="count"
              nameKey="category"
            />
            <div className="col-span-1 md:col-span-2 lg:col-span-2">
              <BarChartDefault
                title="Weekly Rhythm"
                description="Your movie-watching habits across the week."
                data={computedWeeklyRhythmData}
                config={weeklyRhythmConfig}
                xKey="day"
                dataKey="count"
              />
            </div>
          </div>
        </div>

        <div className="grid gap-3 mb-8">
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
            <div className="col-span-1 md:col-span-2 lg:col-span-2">
                <ChartBarMixedDecades
                  title="Ratings Through the Decades"
                  description="Your average movie ratings summarized per decade."
                  data={computedRatingsPerDecadeData}
                  config={{}}
                  dataKey="avg_rating"
                  yKey="decade"
                />
              </div>
            <ChartPieSimpleToggable
              title="Top Genres"
              description="Discover which genres dominate your watchlist and which you explore occasionally."
              data={computedTopGenresData}
              altData={computedTopGenresAltData}
              config={{}}
              dataKey="count"
              nameKey="genre"
            />
            <ChartPieSimpleToggable
              title="Top Nanogenres"
              description="Dive into your niche preferences and see how they compare to mainstream trends."
              data={computedTopNanogenresData}
              altData={computedTopNanogenresAltData}
              config={{}}
              dataKey="count"
              nameKey="nanogenre"
            />
          </div>
        </div>

        <div className="grid gap-3 mb-8">
            <div className="grid grid-cols-2 gap-5 sm:grid-cols-1 md:grid-cols-1 lg:grid-cols-4">
              <ChartPieSimpleToggable
                title="Favorite Language"
                description="Discover which languages dominate your watchlist and which you explore occasionally."
                data={computedFavoriteLanguageData}
                altData={computedFavoriteLanguageAltData}
                config={{}}
                dataKey="count"
                nameKey="language"
              />
              <div className="col-span-1 md:col-span-3 lg:col-span-3">
                <BarChartDefaultYears
                  title="Ratings Through the Years"
                  description="The evolution of your ratings based on the release year of the movies you've watched."
                  data={computedRatingsPerYearData}
                  config={{}}
                  xKey="year_released"
                  dataKey="average_rating"
                />
              </div>
            </div>
          </div>
          <div className="grid gap-3 mb-8">
            <div className="grid grid-cols-2 gap-5 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
              <div className="col-span-1 md:col-span-2 lg:col-span-2">
                <ChartBarMixedMostWatched
                  title="Most Watched"
                  description="Your most frequently watched movies and shows."
                  data={computedMostWatchedMoviesData}
                  config={mostWatchedMoviesConfig}
                  dataKey="count"
                  yKey="title"
                  legendKey={false}
                  imageKey="poster_url"
                />
              </div>
              <ChartPieSimpleToggable
              title="Favorite Themes"
              description="Visualize the recurring themes you enjoy in your movies and shows."
              data={computedFavoriteThemesData}
              altData={computedFavoriteThemesAltData}
              config={{}}
              dataKey="count"
              nameKey="theme"
              legendKey={false}
            />
            <ChartPieSimpleToggable
              title="Top Production Countries"
              description="See which countries produce the majority of your watched content."
              data={computedTopCountriesData}
              altData={computedTopCountriesAltData}
              config={{}}
              dataKey="count"
              nameKey="country"
              legendKey={false}
            />
            </div>
          </div>
          <div className="grid gap-3 mb-8">
            <div className="grid grid-cols-2 gap-5 sm:grid-cols-1 md:grid-cols-1 lg:grid-cols-1">
              <Card className="bg-transparent text-card-white flex flex-col gap-6 rounded-xl border-0 py-6">
                <CardHeader>
                  <CardTitle>Tops and Flops</CardTitle>
                  <CardDescription>
                    A quick look at your highest and lowest rated movies compared to their average ratings.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2 leading-none font-medium">
                    <span className="text-white text-sm">Rated higher than average</span>
                    <TrendingUp className="h-4 w-4" />
                  </div>
                  <MovieCarousel movies={higherRatedMovies} />
                </CardContent>
                <CardContent>
                  <div className="flex items-center gap-2 leading-none font-medium">
                    <span className="text-white text-sm">Rated lower than average</span>
                    <TrendingDown className="h-4 w-4" />
                  </div>
                  <MovieCarousel movies={lowerRatedMovies} />
                </CardContent>
              </Card>
            </div>
          </div>

      </div>
    </div>
  );
};
