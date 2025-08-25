import {GitHubLogoIcon, TwitterLogoIcon} from "@radix-ui/react-icons";
import LetterboxdLogo from "../assets/letterboxd-logo-B0DAE2EC0E-seeklogo.com.png";
import TMDBLogo from "../assets/1280px-Tmdb.new.logo.svg.png";
import WTSLogo from "../assets/J0GoySfX_400x400.png";

const Footer = () => {
    return (
        <footer>
            <div className=" flex flex-row bg-neutral-100 justify-between top-0 w-full z-10 p-3 text-center text-gray-500">
                <div className="flex flex-row space-x-2 items-center">
                    <a href="https://twitter.com/dijkstra_ftw" target="_blank"
                       rel="noopener noreferrer">
                        <TwitterLogoIcon className="h-5 w-5 hover:text-gray-700"/>
                    </a>
                    <a href="https://github.com/DijkstraFTW/letterboxd-movie-rec" target="_blank"
                       rel="noopener noreferrer">
                        <GitHubLogoIcon className="h-5 w-5 hover:text-gray-700"/>
                    </a>
                </div>
                <div className="text-black text-xs">
                    <div className="flex flex-row space-x-6 items-center">
                        <span>Powered by</span>
                        <a href="https://letterboxd.com" target="_blank" rel="noopener noreferrer">
                            <img className="h-8 hover:opacity-90" src={LetterboxdLogo} alt="Letterboxd Logo"></img>
                        </a>
                        <a href="https://www.themoviedb.org" target="_blank" rel="noopener noreferrer">
                            <img className="h-8 hover:opacity-90" src={TMDBLogo} alt="TMDB Logo"></img>
                        </a>
                        <a href="http://www.whentostream.com/" target="_blank" rel="noopener noreferrer">
                            <img className="h-10 hover:opacity-90" src={WTSLogo} alt="WTS Logo"></img>
                        </a>
                    </div>
                </div>
            </div>
        </footer>
    );
}

export default Footer;