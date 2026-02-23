import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { Button } from "../../shadcn/components/ui/button";
import { InfoIcon } from "lucide-react";
import NotificationsButton from "./NotificationsButton";

export const Header = () => {

  const navigate = useNavigate();
  const location = useLocation();

  const handleRandomClick = () => {
    if (location.pathname === "/random") {
      navigate("/random", { replace: true });
    } else {
      navigate("/random");
    }
  };

  return (
    <div className="bg-[#111111] w-full sm:p-3 py-4 z-0">
      <div className="max-w-7xl mx-auto flex justify-between items-center">
        <NavLink to="/" className="text-2xl font-bold text-gray-800">
          <span className="text-xl font-light tracking-tight text-white/80 mr-2">
            <span>my</span>
            <span className="text-[#00e054]">letter</span>
            <span className="text-[#ff8000]">bo</span>
            <span className="text-[#40bcf4]">xd</span>
            <span>flicks</span> 
          </span>
        </NavLink>
        <nav className="space-x-2 justify-center items-center flex">
          <NotificationsButton />
          <NavLink
            to="/about"
            className="text-gray-600 hover:text-gray-800"
          >
            <Button className="inline-flex items-center justify-center whitespace-nowrap transition-colors focus-visible:outline-none cursor-pointer disabled:pointer-events-none disabled:opacity-50 border px-3 py-1.5 bg-white/5 hover:bg-white/10 text-white/80 border-white/5 rounded-full text-sm h-8 font-medium">
              <InfoIcon></InfoIcon>About
            </Button>
          </NavLink>
          <NavLink
            to="/recommender"
            className="text-gray-600 hover:text-gray-800"
          >
            <Button className="inline-flex items-center justify-center whitespace-nowrap transition-colors focus-visible:outline-none cursor-pointer disabled:pointer-events-none disabled:opacity-50 border px-3 py-1.5 bg-white/5 hover:bg-white/10 text-white/80 border-white/5 rounded-full text-sm h-8 font-medium">
              Get Recommendations <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" className="lucide lucide-arrow-up-right h-3 w-3 sm:h-4 sm:w-4" aria-hidden="true"><path d="M7 7h10v10"></path><path d="M7 17 17 7"></path></svg>
            </Button>
          </NavLink>
          <NavLink
            to="/random"
            className="text-gray-600 hover:text-gray-800"
          >
            <Button
              onClick={handleRandomClick}
              className="inline-flex items-center justify-center whitespace-nowrap text-sm focus-visible:outline-none cursor-pointer disabled:pointer-events-none disabled:opacity-50 py-1.5 rounded-full px-4 h-8 bg-white text-black font-medium hover:bg-gray-100 transition-colors"
            >
              Random Pick
            </Button>

          </NavLink>
        </nav>
      </div>
    </div>
  );
};

export default Header;
