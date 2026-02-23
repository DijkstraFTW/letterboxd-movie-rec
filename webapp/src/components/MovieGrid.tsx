import { useState, useEffect } from "react";
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
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const timer = setTimeout(() => setLoading(false), 450);
        return () => clearTimeout(timer);
    }, []);

    const skeletonCount = movies.length || 8;

    return (
        <div className="mb-4">
            <div className="flex flex-col h-full">
                <h3 className="text-2xl mb-4 text-white w-fit justify-left">{sectionTitle}</h3>
                <div className="grid grid-cols-2 gap-5 sm:grid-cols-4 md:grid-cols-4 lg:grid-cols-6">
                    {loading
                        ? Array.from({ length: skeletonCount }).map((_, index) => (
                              <div key={index}>
                                  <Skeleton className="h-[250px] w-full rounded-xl" />
                              </div>
                          ))
                        : movies.map((movie: any) => <MovieCard key={movie.id} {...movie} />)}
                </div>
            </div>
        </div>
    );
};

export default MovieGrid;
