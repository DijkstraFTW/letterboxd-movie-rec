import { Link } from "react-router-dom";
import { Button } from "../../shadcn/components/ui/button.tsx";
import { CalendarIcon, LightningBoltIcon } from "@radix-ui/react-icons";
import PosterStack from "./PosterStack.tsx";

type PosterInfoProps = {
  posters: any[];
};

const PosterInfo = ({ posters }: PosterInfoProps) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-1 md:grid-cols-1 lg:grid-cols-2 gap-10 text-[#e5e3e2]">

      <div className="flex flex-col gap-4 mt-16">
        <p className="text-yellow-600 bg-[#19160c] border border-yellow-400/10 font text-xs sm:text-sm bg-yellow-400/5 px-3 sm:px-4 py-2 w-fit rounded-md block sm:flex items-center gap-1">
          Enhanced description based suggestions. <Link to="/search"><a className="flex items-center gap-1 text-white/80 underline">Try it out <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" className="lucide lucide-arrow-up-right h-3 w-3 sm:h-4 sm:w-4" aria-hidden="true"><path d="M7 7h10v10"></path><path d="M7 17 17 7"></path></svg></a></Link>
        </p>
        <h1 className="text-2xl sm:text-3xl text-white/90 leading-tight">
          <span className="rounded-md">Discover what to watch next with</span> <br className="sm:hidden" /> <br className="hidden sm:block" /><span className="underline decoration-blue-500 decoration-2 underline-offset-4">our enhanced movie-matching</span> model.
        </h1>

        <div className="flex gap-4">
          <Link to="/recommender">
            <Button className="group bg-white text-black inline-flex items-center justify-center whitespace-nowrap transition-colors focus-visible:outline-none cursor-pointer disabled:pointer-events-none disabled:opacity-50 border-white/10 h-9 border-0 py-4 sm:py-5 px-4 sm:px-5 rounded-full text-sm font-medium w-full sm:w-auto" variant="ghost" size="sm">
              <LightningBoltIcon className="mr-1" />
              Get recommendations
            </Button>
          </Link>
          <Link to="/calendar">
            <Button className="bg-white text-black inline-flex items-center justify-center whitespace-nowrap transition-colors focus-visible:outline-none cursor-pointer disabled:pointer-events-none disabled:opacity-50 border-white/10 h-9 border-0 py-4 sm:py-5 px-4 sm:px-5 rounded-full text-sm font-medium w-full sm:w-auto" variant="ghost" size="sm">
              <CalendarIcon className="mr-1" />
              Check upcoming releases
            </Button>
          </Link>
        </div>
      </div>

      <div>
        <PosterStack posterUrls={posters} />
      </div>

    </div>
  );
};

export default PosterInfo;
