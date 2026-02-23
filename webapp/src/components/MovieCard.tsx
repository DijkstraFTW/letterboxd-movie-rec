'use client';

import { useState } from 'react';
import { motion } from 'motion/react';
import { StarFilledIcon, CounterClockwiseClockIcon, HeartIcon, HeartFilledIcon } from '@radix-ui/react-icons';
import { ProgressiveBlur } from '../../components/motion-primitives/progressive-blur.tsx';
import { Badge } from "../../shadcn/components/ui/badge.tsx";
import { Tooltip, TooltipTrigger, TooltipContent } from "../../shadcn/components/ui/tooltip.tsx";
import RatingsLineChart from './RatingsLineChart.tsx';

export function formatNumber(num: number) { 
  if (num >= 1_000_000) return (num / 1_000_000).toFixed(2) + "M"; 
  if (num >= 1_000) return Math.round(num / 1_000) + "k"; 
  return num.toString(); 
}

const MIDDLEWARE_HOST = import.meta.env.VITE_MIDDLEWARE_HOST;
const MIDDLEWARE_API_KEY = import.meta.env.VITE_MIDDLEWARE_API_KEY;

export function MovieCard({
  poster_url,
  movie_title,
  movie_title_formatted,
  runtime,
  lb_rating,
  genres,
  histogram,
  showTopPickButton = true,
  onImageSettle,
}: {
  poster_url: string;
  movie_title: string;
  movie_title_formatted?: string;
  runtime?: string;
  lb_rating?: number;
  genres?: string[] | string;
  histogram?: { total: number; fans: number } | string;
  showTopPickButton?: boolean;
  onImageSettle?: () => void;
}) {
  const [isHover, setIsHover] = useState(false);

  const parsedHistogram: { total: number; fans: number } | null = (() => {
    if (!histogram) return null;
    if (typeof histogram === 'string') {
      try { return JSON.parse(histogram); } catch { return null; }
    }
    return histogram;
  })();

  const parsedGenres: string[] = Array.isArray(genres)
    ? genres
    : typeof genres === 'string' && genres
      ? (genres.match(/'([^']+)'/g)?.map(s => s.replace(/'/g, '')) ?? [])
      : [];
  const [isTopPick, setIsTopPick] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const convertRuntime = (minutes?: string) => {
    if (!minutes) return '';
    const hrs = Math.floor(parseInt(minutes) / 60);
    const mins = parseInt(minutes) % 60;
    return `${hrs}h${mins.toString().padStart(2, '0')}`;
  };

  const handleTopPickToggle = async () => {
    if (isLoading || !movie_title_formatted) return;

    setIsLoading(true);
    const newTopPickState = !isTopPick;

    try {
      const endpoint = newTopPickState
        ? `${MIDDLEWARE_HOST}/recommend/add-top-pick`
        : `${MIDDLEWARE_HOST}/recommend/remove-top-pick`;

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': MIDDLEWARE_API_KEY,
        },
        body: JSON.stringify({
          movie_title: movie_title,
          movie_title_formatted: movie_title_formatted,
          poster_url: poster_url,
          lb_rating: lb_rating ?? 0.0,
          genres: parsedGenres,
          histogram: parsedHistogram ?? {},
          runtime: runtime ? parseInt(runtime) : 0,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      setIsTopPick(newTopPickState);
    } catch (error) {
      console.error('Error updating top pick:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className='relative aspect-[2/3] overflow-hidden rounded-lg shadow-md cursor-pointer transition-transform duration-300 hover:scale-[1.03]'
      onMouseEnter={() => setIsHover(true)}
      onMouseLeave={() => setIsHover(false)}
    >
      <img
        src={poster_url}
        alt={movie_title}
        className="absolute inset-0 w-full h-full object-cover rounded-lg border border-white/50 shadow-sm"
        onLoad={onImageSettle}
        onError={onImageSettle}
      />
      {showTopPickButton && (
        <Tooltip>
          <motion.div
            className='absolute top-2 right-2 z-10 text-white'
            animate={isHover ? 'visible' : 'hidden'}
            initial="hidden"
            variants={{
              hidden: { opacity: 0, scale: 0.8 },
              visible: { opacity: 1, scale: 1 },
            }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
          >
            <TooltipTrigger asChild>
              <button
                className='p-3 cursor-pointer bg-transparent border-none'
                onClick={(e) => {
                  e.stopPropagation();
                  handleTopPickToggle();
                }}
              >
                {isTopPick ? (
                  <HeartFilledIcon className='w-5 h-5 text-red-500 drop-shadow-[0_2px_3px_rgba(0,0,0,0.8)]' />
                ) : (
                  <HeartIcon className='w-5 h-5 text-gray-300 drop-shadow-[0_2px_3px_rgba(0,0,0,0.8)]' />
                )}
              </button>
            </TooltipTrigger>
          </motion.div>
          <TooltipContent side="bottom" sideOffset={8}>
            {isTopPick ? 'Unrate as a top pick' : 'Rate as a top-pick'}
          </TooltipContent>
        </Tooltip>
      )}

      <ProgressiveBlur
        initial="hidden"
        className='pointer-events-none absolute bottom-0 left-0 h-[65%] w-full'
        blurIntensity={0.7}
        animate={isHover ? 'visible' : 'hidden'}
        variants={{ hidden: { opacity: 0 }, visible: { opacity: 1 } }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
      />

      <motion.div
        className='absolute bottom-0 left-0 p-4 w-full text-white drop-shadow-[0_2px_3px_rgba(0,0,0,0.8)]'
        animate={isHover ? 'visible' : 'hidden'}
        initial="hidden"
        variants={{
          hidden: { opacity: 0, y: 15 },
          visible: { opacity: 1, y: 0 },
        }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
      >
        <h3 className='text-base font-semibold leading-tight line-clamp-2'>
          {movie_title}
        </h3>

        <div className='flex items-center gap-3 text-sm font-light tracking-tight text-white/90 mt-1'>
          {lb_rating !== undefined && (
            <div className='flex items-center gap-1'>
              <StarFilledIcon className='w-4 h-4' />
              {(lb_rating * 2).toFixed(1)}
            </div>
          )}
          {runtime && (
            <div className='flex items-center gap-1'>
              <CounterClockwiseClockIcon className='w-4 h-4' />
              {convertRuntime(runtime)}
            </div>
          )}
        </div>

        {parsedHistogram !== null && <RatingsLineChart data={parsedHistogram} />}

        {parsedGenres.length > 0 && (
          <div className='flex flex-wrap gap-1 mt-3'>
            {parsedGenres.slice(0, 2).map((genre: string) => (
              <Badge
                key={genre}
                className='text-xs px-2 py-0.5 bg-white/25 backdrop-blur-sm text-white rounded-full shadow-sm'
              >
                {genre}
              </Badge>
            ))}
          </div>
        )}
      </motion.div>
    </div>
  );
}

export default MovieCard;
