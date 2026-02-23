import { useState, useEffect } from "react";
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

const getRandomInterval = () => Math.floor(Math.random() * 4000) + 4000;

const RecommendationsPage = () => {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [formType, setFormType] = useState<FormType>(null);
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    if (!isLoading) return;

    const config = formType === "letterboxd" ? LETTERBOXD_CONFIG : GENRES_CONFIG;

    const scheduleNextMessage = () => {
      const interval = getRandomInterval();
      return setTimeout(() => {
        setMessageIndex((prev) => (prev + 1) % config.descriptions.length);
        scheduleNextMessage();
      }, interval);
    };

    const timer = scheduleNextMessage();
    return () => clearTimeout(timer);
  }, [isLoading, formType]);

  useEffect(() => {
    if (isLoading) {
      setMessageIndex(0);
    }
  }, [isLoading]);

  const handleLetterboxdSubmit = () => {
    setFormType("letterboxd");
    setIsLoading(true);
    // TODO: When API call is implemented, move navigation to happen after successful response
    // For now, simulate loading and navigate after a delay
    setTimeout(() => {
      navigate('/results', { state: { formType: 'letterboxd' } });
    }, 16000);
  };

  const handleGenresSubmit = () => {
    setFormType("genres");
    setIsLoading(true);
    // TODO: When API call is implemented, move navigation to happen after successful response
    // For now, simulate loading and navigate after a delay
    setTimeout(() => {
      navigate('/results', { state: { formType: 'genres' } });
    }, 16000);
  };

  if (isLoading) {
    const config = formType === "letterboxd" ? LETTERBOXD_CONFIG : GENRES_CONFIG;
    const currentDescription = config.descriptions[messageIndex];

    return (
      <div className="flex flex-col min-h-screen bg-black text-white">
        <Header />
        <div className="flex-grow flex items-center justify-center px-4">
          <Empty className="flex items-center justify-center w-full h-96">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Spinner />
              </EmptyMedia>
              <EmptyTitle>{config.title}...</EmptyTitle>
              <EmptyDescription>
                {currentDescription}
              </EmptyDescription>
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
