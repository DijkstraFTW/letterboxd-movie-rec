
import {Badge} from "../../shadcn/components/ui/badge.tsx";
import {
    CounterClockwiseClockIcon,
    GlobeIcon,
    HeartFilledIcon,
    Pencil2Icon,
    StarFilledIcon
} from "@radix-ui/react-icons";
import RatingsLineChart from "./RatingsLineChart.tsx";
import {useState} from "react";
import {HoverCard, HoverCardContent, HoverCardTrigger} from "../../shadcn/components/ui/hover-card.tsx";

function formatLanguages(spoken_languages: string[]) {
    const sortedLanguages = spoken_languages.sort((a, b) => {
        if (a === 'English') return -1;
        if (b === 'English') return 1;
        return 0;
    });
    const displayLanguages = sortedLanguages.slice(0, 2);
    return displayLanguages.join(', ');
}

function convertRuntime(minutes: string) {
    const hours = Math.floor(parseInt(minutes) / 60);
    const remainingMinutes = parseInt(minutes) % 60;
    const formattedMinutes = remainingMinutes < 10 ? `0${remainingMinutes}` : remainingMinutes;
    return `${hours}h${formattedMinutes}`;
}

export function formatNumber(num: number) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(2) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(0) + 'k';
    } else {
        return num.toString();
    }
}


// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-expect-error
const MovieCard = ({movie_title, year_released, runtime, poster_url, lb_rating, histogram, genres, overview, spoken_languages}) => {
    const MAX_LENGTH = 300;
    const [showFullOverview, setShowFullOverview] = useState(false);

    const toggleOverview = () => {
        setShowFullOverview(!showFullOverview);
    };

    const displayOverview = showFullOverview || overview.length <= MAX_LENGTH
        ? overview
        : overview.substring(0, MAX_LENGTH) + "...";

    return ( <div>
        <HoverCard>
            <HoverCardTrigger asChild>
                <div className="rounded-2xl hover:shadow-2xl hover:bg-white hover:bg-opacity-10">
                    <div className="flex justify-center items-center p-3">
                        <img className="block h-full mx-auto rounded-2xl shadow-2xl" src={poster_url}
                             alt={`${movie_title}`}/>
                    </div>
                    <div
                        className=" text-center mb-1 line-clamp-1 max-h-[1.7rem] text-ellipsis break-words font-bold text-white">
                        <div className="text-white text-sm p-1.5 mb-2 line-clamp-1">{movie_title}</div>
                    </div>
                </div>
            </HoverCardTrigger>
            <HoverCardContent className="w-120 bg-white shadow-lg rounded-lg"
                              key={showFullOverview.valueOf().toString()}>
                <div className="flex justify-between space-x-4 max-w-30">
                    <div className="flex flex-col items-left">
                        <RatingsLineChart data={histogram}/>
                        <div className="flex justify-between space-x-2 m-2 text-gray-500">
                            <div className="flex items-center space-x-1">
                                <Pencil2Icon/>
                                <span className={"text-sm"}>{formatNumber(histogram.total)} ratings</span>
                            </div>
                            <div className="flex items-center space-x-1">
                                <HeartFilledIcon/>
                                <span className={"text-sm"}>{formatNumber(histogram.fans)} fans</span>
                            </div>
                        </div>

                    </div>
                    <div className="flex flex-col p-1.5">
                        <h4 className="text-sm font-bold text-black">{movie_title} ({year_released})</h4>
                        <div className="flex space-x-3 text-sm text-gray-500 mt-1">
                            <div className="flex items-center">
                                <StarFilledIcon/>
                                <span className="ml-1">{(lb_rating * 2).toFixed(1)}</span>
                            </div>
                            <div className="flex items-center">
                                <CounterClockwiseClockIcon/>
                                <span className="ml-1">{convertRuntime(runtime)}</span>
                            </div>
                            <div className="flex items-center">
                                <GlobeIcon/>
                                <span className="ml-1">{formatLanguages(spoken_languages)}</span>
                            </div>
                        </div>
                        <div className="max-w-80 h-fit text-sm text-gray-500 mt-2">
                            {displayOverview}
                            {overview.length > MAX_LENGTH && !showFullOverview && (
                                <span className="text-blue-500 text-xs cursor-pointer" onClick={toggleOverview}> Show More</span>
                            )}
                        </div>
                        {showFullOverview && overview.length > MAX_LENGTH && (
                            <button onClick={toggleOverview} className="flex justify-left text-blue-500 text-xs mt-1">
                                Show Less
                            </button>
                        )}
                        <div className="flex flex-row space-x-1 mt-2">
                            {genres.slice(0, 3).map((theme: string) => (
                                <Badge
                                    className="w-fit text-center rounded-3xl p-1 text-gray-800 border-0 shadow-sm"
                                    key={theme}
                                    style={{backgroundColor: "lightgray"}}>
                                    {theme}
                                </Badge>
                            ))}
                        </div>
                    </div>
                </div>
            </HoverCardContent>
        </HoverCard>
        </div>
    );
}

export default MovieCard;