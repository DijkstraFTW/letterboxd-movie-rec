import { useState, useEffect } from 'react';
import { InfiniteSlider } from '../../components/motion-primitives/infinite-slider.tsx';
import MovieCard from "./MovieCard.tsx";
import { Skeleton } from "../../shadcn/components/ui/skeleton.tsx";

type Movie = {
  id?: string | number;
  movie_title_formatted?: string;
  movie_title?: string;
  [key: string]: any;
};

type MovieCarouselProps = {
  movies: Movie[];
  sectionTitle?: string;
};

export default function MovieCarousel({ movies, sectionTitle }: MovieCarouselProps) {
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

    const images = urls.map((url: string) => {
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

  const skeletonCount = movies.length || 8;

  return (
    <div className="mb-12">
      <h3 className="text-2xl text-white mb-4 w-fit justify-left">{sectionTitle}</h3>
      {!allLoaded ? (
        <div className="flex gap-5 overflow-hidden py-2">
          {Array.from({ length: skeletonCount }).map((_, i) => (
            <div key={i} className="w-[180px] flex-shrink-0">
              <Skeleton className="h-[270px] w-full rounded-xl" />
            </div>
          ))}
        </div>
      ) : (
        <InfiniteSlider speedOnHover={20} gap={20} className='py-2'>
          {movies.map((movie: any, index: number) => (
            <div key={`${movie.id ?? movie.movie_title_formatted ?? movie.movie_title ?? ''}-${index}`} className="w-[180px] flex-shrink-0">
              <MovieCard {...movie} />
            </div>
          ))}
        </InfiniteSlider>
      )}
    </div>
  );
}
