import { useState, useEffect } from "react";
import MovieCard from "./MovieCard.tsx";
import { Skeleton } from "../../shadcn/components/ui/skeleton.tsx";

type RandomMovieGridProps = {
    movies: any[];
    sectionTitle?: string;
};

const RandomMovieGrid = ({ movies, sectionTitle }: RandomMovieGridProps) => {
    const [allLoaded, setAllLoaded] = useState(false);

    useEffect(() => {
        setAllLoaded(false);

        if (movies.length === 0) return;

        const urls = movies.map(m => m.poster_url).filter(Boolean);
        if (urls.length === 0) {
            setAllLoaded(true);
            return;
        }

        let settled = 0;
        let cancelled = false;

        const images = urls.map(url => {
            const img = new Image();
            img.onload = img.onerror = () => {
                settled++;
                if (!cancelled && settled >= urls.length) setAllLoaded(true);
            };
            img.src = url;
            return img;
        });

        return () => {
            cancelled = true;
            images.forEach(img => { img.onload = null; img.onerror = null; });
        };
    }, [movies]);

    return (
        <div className="mb-4">
            <div className="flex flex-col h-full">
                <h3 className="text-2xl mb-4 text-white w-fit justify-left">{sectionTitle}</h3>
                <div className="grid grid-cols-2 gap-5 sm:grid-cols-4 md:grid-cols-4 lg:grid-cols-6">
                    {!allLoaded
                        ? Array.from({ length: movies.length || 24 }).map((_, i) => (
                            <div key={i}>
                                <Skeleton className="h-[250px] w-full rounded-xl" />
                            </div>
                        ))
                        : movies.map((movie: any) => (
                            <MovieCard
                                key={movie.id ?? movie.movie_title_formatted ?? movie.movie_title}
                                {...movie}
                            />
                        ))
                    }
                </div>
            </div>
        </div>
    );
};

export default RandomMovieGrid;
