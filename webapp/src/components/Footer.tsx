import { HeartFilledIcon } from "@radix-ui/react-icons";
import LetterboxdLogo from "../assets/letterboxd-logo-B0DAE2EC0E-seeklogo.com.png";
import MoroccoFlag from "../assets/Flag_of_Morocco.svg.webp";
import TMDBLogo from "../assets/1280px-Tmdb.new.logo.svg.png";
import WhenToStream from "../assets/whentostream.png";

const Footer = () => {
    return (
        <footer>
            <div className=" bottom-0 z-[60] bg-black/10 backdrop-blur supports-[backdrop-filter]:bg-[#111111] border-t border-white/10 mt-auto">
                <div className="px-3 sm:px-10 py-4 sm:py-5">
                    <div className="mx-auto">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 sm:gap-6">
                            <div className="flex items-center text-sm text-white/50">
                                <img className="h-5 w-8 mr-2 rounded" src={MoroccoFlag} alt="logo" />
                                <span className="flex items-center justify-center">
                                    Made with <HeartFilledIcon className="ml-1" />
                                </span>
                            </div>
                            <div className="flex flex-wrap gap-4 sm:gap-6 text-sm justify-center items-center text-white/50">
                                <span>Powered by</span>
                                <a href="https://letterboxd.com" target="_blank" rel="noopener noreferrer">
                                    <img className="h-8 hover:opacity-85 rounded" src={LetterboxdLogo} alt="Letterboxd Logo"></img>
                                </a>
                                <a href="https://www.themoviedb.org" target="_blank" rel="noopener noreferrer">
                                    <img className="h-8 hover:opacity-85" src={TMDBLogo} alt="TMDB Logo"></img>
                                </a>
                                <a href="https://whentostream.com/" target="_blank" rel="noopener noreferrer">
                                    <img className="h-12 hover:opacity-85 rounded" src={WhenToStream} alt="WhenToStream Logo"></img>
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </footer >
    );
}

export default Footer;