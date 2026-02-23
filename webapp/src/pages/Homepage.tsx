import { useState, useEffect } from "react";
import Header from "../components/Header.tsx";
import HomeMovieGrid from "../components/HomeMovieGrid.tsx";
import MovieCarousel from "../components/MovieCarousel.tsx";
import Footer from "../components/Footer.tsx";
import PosterInfo from "../components/PosterInfo.tsx";

const MIDDLEWARE_HOST = import.meta.env.VITE_MIDDLEWARE_HOST
const MIDDLEWARE_API_KEY = import.meta.env.VITE_MIDDLEWARE_API_KEY


interface TopPick {
    movie_title_formatted: string;
    poster_url: string;
    pick_count: number;
}

const Homepage = () => {
    const [topPicks, setTopPicks] = useState<string[]>([]);
    const [recentMovies, setRecentMovies] = useState<any[]>([]);
    const [popularMovies, setPopularMovies] = useState<any[]>([]);

    useEffect(() => {
        const fetchTopPicks = async () => {
            try {
                const response = await fetch(`${MIDDLEWARE_HOST}/recommend/top-picks`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': MIDDLEWARE_API_KEY,
                    },
                });
                if (!response.ok) {
                    throw new Error('Failed to fetch top picks');
                }
                const data: TopPick[] = await response.json();
                const poster_urls = data.map(movie => movie.poster_url);
                setTopPicks(poster_urls);
            } catch (err) {
                console.error('Error fetching top picks:', err);
            }
        };

        fetchTopPicks();
    }, []);

    useEffect(() => {
        const fetchRecentMovies = async () => {
            try {
                const response = await fetch(`${MIDDLEWARE_HOST}/recommend/recent`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': MIDDLEWARE_API_KEY,
                    },
                });
                if (!response.ok) {
                    throw new Error('Failed to fetch recent movies');
                }
                const data = await response.json();
                setRecentMovies(data);
            } catch (err) {
                console.error('Error fetching recent movies:', err);
            }
        };

        fetchRecentMovies();
    }, []);

    useEffect(() => {
        const fetchPopularMovies = async () => {
            try {
                const response = await fetch(`${MIDDLEWARE_HOST}/recommend/popular`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': MIDDLEWARE_API_KEY,
                    },
                });
                if (!response.ok) {
                    throw new Error('Failed to fetch popular movies');
                }
                const data = await response.json();
                setPopularMovies(data);
            } catch (err) {
                console.error('Error fetching popular movies:', err);
            }
        };

        fetchPopularMovies();
    }, []);

    return (
        <div className="bg-black">
            <Header/>
            <div className="max-w-screen-xl w-full mx-auto pb-16 flex-1 mt-6 sm:mt-10 px-4">
                <PosterInfo posters={topPicks}/>
                <MovieCarousel movies={recentMovies} sectionTitle="Recently recommended"/>
                <HomeMovieGrid movies={popularMovies} sectionTitle="Trending this week"/>
            </div>
            <Footer/>
        </div>
    );
}

export default Homepage;