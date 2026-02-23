import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/Header.tsx";
import Footer from "../components/Footer.tsx";
import { InputLbRecForm } from "../components/InputLbRecForm.tsx";
import { InputRecForm } from "../components/InputRecForm.tsx";
import { Spinner } from "../../shadcn/components/ui/spinner.tsx";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "../../shadcn/components/ui/empty.tsx";

type FormType = "letterboxd" | "genres" | null;

const LETTERBOXD_CONFIG = {
  title: "Crafting personalized recommendations",
  descriptions: [
    "Fetching your Letterboxd profile",
    "Analyzing your reviews and ratings",
    "Querying our recommendation model",
    "Processing your watch history",
    "Finishing up"
  ],
};

const GENRES_CONFIG = {
  title: "Generating recommendations",
  descriptions: [
    "Processing your preferences",
    "Analyzing selected genres and ratings",
    "Searching our movie database",
    "Ranking recommendations",
    "Finishing up"

  ],
};

const MAX_POLL_DURATION_MS = 5 * 60 * 1000;
const POLL_INTERVAL_MS = 5000;
const FINISHING_UP_DURATION_MS = 4000;
const getRandomInterval = () => Math.floor(Math.random() * 4000) + 10000;

const RecommendationsPage = () => {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [formType, setFormType] = useState<FormType>(null);
  const [messageIndex, setMessageIndex] = useState(0);
  const [loadError, setLoadError] = useState(false);
  const [scrapeWarning, setScrapeWarning] = useState(false);
  const [isFinishing, setIsFinishing] = useState(false);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollStartRef = useRef<number>(0);

  useEffect(() => {
    if (!isLoading) return;

    const config = formType === "letterboxd" ? LETTERBOXD_CONFIG : GENRES_CONFIG;

    const lastStepIndex = config.descriptions.length - 2; // stop before "Finishing up"

    const scheduleNextMessage = (currentIndex: number) => {
      if (currentIndex >= lastStepIndex) return undefined;
      const interval = getRandomInterval();
      return setTimeout(() => {
        setMessageIndex(currentIndex + 1);
        scheduleNextMessage(currentIndex + 1);
      }, interval);
    };

    const timer = scheduleNextMessage(0);
    return () => { if (timer) clearTimeout(timer); };
  }, [isLoading, formType]);

  useEffect(() => {
    if (isLoading) {
      setMessageIndex(0);
    }
  }, [isLoading]);

  useEffect(() => {
    return () => {
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    };
  }, []);

  const handleLetterboxdSubmit = async (username: string, dataOptIn: boolean) => {
    setFormType("letterboxd");
    setIsLoading(true);
    setLoadError(false);

    const runId = Date.now().toString();

    try {
      const response = await fetch(`${import.meta.env.VITE_MIDDLEWARE_HOST}/recommend/trigger`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': import.meta.env.VITE_MIDDLEWARE_API_KEY,
        },
        body: JSON.stringify({ letterboxd_username: username, data_opt_in: dataOptIn, run_id: runId }),
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    } catch (err) {
      console.error('Error triggering Letterboxd recommendation:', err);
      setIsLoading(false);
      return;
    }

    pollStartRef.current = Date.now();

    const poll = async () => {
      try {
        const res = await fetch(
          `${import.meta.env.VITE_MIDDLEWARE_HOST}/recommend/results?username=${encodeURIComponent(username)}&run_id=${runId}`,
          { headers: { 'X-API-Key': import.meta.env.VITE_MIDDLEWARE_API_KEY } }
        );
        if (res.ok) {
          const data = await res.json();
          if (data?.error) {
            setLoadError(true);
            return;
          }
          if (data?.scrape_failed) {
            setScrapeWarning(true);
          }
          if (data && Array.isArray(data.user_recommendation) && data.user_recommendation.length > 0) {
            setIsFinishing(true);
            setTimeout(() => {
              navigate('/results', {
                state: {
                  formType: 'letterboxd',
                  username,
                  movies: data.user_recommendation,
                  analytics: data.user_analytics ?? {},
                },
              });
            }, FINISHING_UP_DURATION_MS);
            return;
          }
        }
      } catch (err) {
        console.error('Error polling results:', err);
      }

      if (Date.now() - pollStartRef.current < MAX_POLL_DURATION_MS) {
        pollTimeoutRef.current = setTimeout(poll, POLL_INTERVAL_MS);
      } else {
        setLoadError(true);
      }
    };

    poll();
  };

  const handleGenresSubmit = async (genres: string[], minRating: number) => {
    setFormType("genres");
    setIsLoading(true);
    try {
      const response = await fetch(`${import.meta.env.VITE_MIDDLEWARE_HOST}/recommend/fallback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': import.meta.env.VITE_MIDDLEWARE_API_KEY,
        },
        body: JSON.stringify({ genres, minimum_rating: minRating }),
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const movies = await response.json();
      navigate('/results', { state: { formType: 'genres', movies } });
    } catch (err) {
      console.error('Error fetching genre recommendations:', err);
      setLoadError(true);
    }
  };

  if (isLoading) {
    const config = formType === "letterboxd" ? LETTERBOXD_CONFIG : GENRES_CONFIG;
    const lastDescription = config.descriptions[config.descriptions.length - 1];
    const currentDescription = isFinishing ? lastDescription : config.descriptions[messageIndex];

    return (
      <div className="flex flex-col min-h-screen bg-black text-white">
        <Header />
        <div className="flex-grow flex items-center justify-center px-4">
          <Empty className="flex items-center justify-center w-full h-96">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Spinner />
              </EmptyMedia>
              <EmptyTitle>{loadError ? "Something went wrong" : `${config.title}...`}</EmptyTitle>
              <EmptyDescription>
                {loadError ? "We couldn't generate your recommendations. Please try again." : currentDescription}
              </EmptyDescription>
              {scrapeWarning && !loadError && (
                <p className="mt-3 text-sm text-yellow-400">
                  We couldn't find your Letterboxd reviews — recommendations will be less personalized.
                </p>
              )}
            </EmptyHeader>
          </Empty>
        </div>
        <Footer />
      </div>
    );
  }

  return (
    <div className="bg-black min-h-screen flex flex-col">
      <Header />
      <div className="max-w-screen-xl w-full mx-auto pb-16 flex-1 mt-6 sm:mt-10 px-4 text-white">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Movie Recommender</h1>
          <p className="text-white/60">Get personalized movie recommendation based on your own taste</p>
        </div>
        <div className="rounded-md w-full text-[#e5e3e2]">
          <div className="flex flex-row items-start justify-between h-full bg-[#111111] p-4 rounded-xl gap-6">
            <div className="flex-1 max-w-lg">
              <InputLbRecForm onSubmit={handleLetterboxdSubmit} />
            </div>
            <div className="hidden md:block w-px bg-white/20 self-stretch" />
            <div className="flex-1 max-w-lg">
              <InputRecForm onSubmit={handleGenresSubmit} />
            </div>
          </div>
        </div>
      </div>
      <Footer />
    </div>
  );
};

export default RecommendationsPage;
