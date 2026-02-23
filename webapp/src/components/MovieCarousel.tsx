import { InfiniteSlider } from '../../components/motion-primitives/infinite-slider.tsx';
import MovieCard from "./MovieCard.tsx";

type Movie = {
  id: string | number;
  [key: string]: any;
};

type MovieCarouselProps = {
  movies: Movie[];
  sectionTitle?: string;
};

export default function MovieCarousel({ movies, sectionTitle }: MovieCarouselProps) {
  return (
    <div className="mb-12">
      <h3 className="text-2xl text-white mb-4 w-fit justify-left"> {sectionTitle}</h3>
      <div className="overflow-visible" >
        <InfiniteSlider speedOnHover={20} gap={20} className='py-2'>
          {movies.map((movie: any) => (
            <div key={movie.id} className="w-[180px] flex-shrink-0">
              <MovieCard {...movie} />
            </div>
          ))}
        </InfiniteSlider>
      </div>
    </div>
  );
}
