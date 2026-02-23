import { useState, useLayoutEffect, useCallback, useRef } from "react";
import MovieCard from "./MovieCard.tsx";
import { Skeleton } from "../../shadcn/components/ui/skeleton.tsx"

type Movie = {
    id: string | number;
    [key: string]: any;
};

type MovieGridProps = {
    movies: Movie[];
    sectionTitle?: string;
};

const MovieGrid = ({ movies, sectionTitle }: MovieGridProps) => {
    const [allLoaded, setAllLoaded] = useState(false);
    const loadedCount = useRef(0);

    const imageCount = movies.filter(m => m.poster_url).length;

    useLayoutEffect(() => {
        loadedCount.current = 0;
        setAllLoaded(movies.length > 0 && imageCount === 0);
    }, [movies, imageCount]);

    const handleImageSettle = useCallback(() => {
        loadedCount.current += 1;
        if (loadedCount.current >= imageCount) {
            setAllLoaded(true);
        }
    }, [imageCount]);

    const skeletonCount = movies.length || 24;

    return (
        <div className="mb-4">
            <div className="flex flex-col h-full">
                <h3 className="text-2xl mb-4 text-white w-fit justify-left">{sectionTitle}</h3>
                <div className="grid grid-cols-2 gap-5 sm:grid-cols-4 md:grid-cols-4 lg:grid-cols-6">
                    {!allLoaded && Array.from({ length: skeletonCount }).map((_, index) => (
                        <div key={index}>
                            <Skeleton className="h-[250px] w-full rounded-xl" />
                        </div>
                    ))}
                    <div className={allLoaded ? "contents" : "h-0 overflow-hidden"}>
                        {movies.map((movie: any) => (
                            <MovieCard
                                key={movie.id ?? movie.movie_title_formatted ?? movie.movie_title}
                                {...movie}
                                onImageSettle={handleImageSettle}
                            />
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MovieGrid;
