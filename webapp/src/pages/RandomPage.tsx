import { useState, useEffect } from "react";
import Header from "../components/Header.tsx";
import RandomMovieGrid from "../components/RandomMovieGrid.tsx";
import Footer from "../components/Footer.tsx";
import {
    Empty,
    EmptyDescription,
    EmptyHeader,
    EmptyMedia,
    EmptyTitle,
} from "../../shadcn/components/ui/empty.tsx";
import { Button } from "../../shadcn/components/ui/button.tsx";
import { ReloadIcon, ExclamationTriangleIcon } from "@radix-ui/react-icons";

const MIDDLEWARE_HOST = import.meta.env.VITE_MIDDLEWARE_HOST
const MIDDLEWARE_API_KEY = import.meta.env.VITE_MIDDLEWARE_API_KEY


export default function HomePage() {
    const [fetching, setFetching] = useState(false);
    const [moviesdata, setMovies] = useState<any[]>([]);
    const [error, setError] = useState<string | null>(null);

    const generateMovies = async () => {
        setFetching(true);
        if (moviesdata.length > 0) setMovies([]);
        setError(null);

        try {
            const response = await fetch(`${MIDDLEWARE_HOST}/recommend/random`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': MIDDLEWARE_API_KEY,
                },
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            setMovies(Array.isArray(data) ? data : []);
        } catch (err) {
            console.error('Error fetching random movies:', err);
            setError(err instanceof Error ? err.message : 'Failed to fetch random movies');
        } finally {
            setFetching(false);
        }
    };

    useEffect(() => {
        generateMovies();
    }, []);

    return (
        <div className="bg-black min-h-screen flex flex-col">
            <Header />
            <div className="max-w-screen-xl w-full mx-auto pb-16 flex-1 mt-6 sm:mt-10 px-4 text-white">
                <div className="mb-4">
                    <div className="flex items-center gap-3">
                        <h1 className="text-4xl font-bold text-white">Movie Roulette</h1>
                        <Button onClick={generateMovies} disabled={fetching} className="inline-flex items-center justify-center whitespace-nowrap transition-colors focus-visible:outline-none cursor-pointer disabled:pointer-events-none disabled:opacity-50 border px-3 py-1.5 bg-white/5 hover:bg-white/10 text-white/80 border-white/5 rounded-full text-sm h-8 font-medium mt-2">
                            Retry <ReloadIcon />
                        </Button>
                    </div>
                    <p className="text-white/60 mt-2">Get a selection of randomly choosen movies.</p>
                </div>
                {error ? (
                    <Empty className="flex items-center justify-center w-full h-96">
                        <EmptyHeader>
                            <EmptyMedia variant="icon">
                                <ExclamationTriangleIcon className="w-12 h-12 text-red-400/80" />
                            </EmptyMedia>
                            <EmptyTitle className="text-red-400">Failed to Load Movies</EmptyTitle>
                            <EmptyDescription className="space-y-2">
                                <p className="text-white/60">
                                    Unable to connect to the server. Please check your connection and try again.
                                </p>
                            </EmptyDescription>
                        </EmptyHeader>
                    </Empty>
                ) : (
                    <RandomMovieGrid movies={moviesdata} sectionTitle="" />
                )}
            </div>
            <Footer />
        </div>
    );
}
