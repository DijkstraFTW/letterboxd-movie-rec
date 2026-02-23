import './index.css'
import {BrowserRouter, Routes, Route} from "react-router-dom";
import RecommendationsPage from "./pages/RecommendationsPage.tsx";
import Homepage from "./pages/Homepage.tsx";
import ResultsPage from "./pages/ResultsPage.tsx";
import RandomPage from "./pages/RandomPage.tsx";
import AboutPage from "./pages/AboutPage.tsx";
import CalendarPage from './pages/CalendarPage.tsx';
import SearchPage from './pages/SearchPage.tsx';


const App = () => (
    <BrowserRouter>
        <Routes>
            <Route path="/" element={<Homepage/>}/>
            <Route path="/home" element={<Homepage/>}/>
            <Route path="/search" element={<SearchPage/>}/>
            <Route path="/about" element={<AboutPage/>}/>
            <Route path="/recommender" element={<RecommendationsPage/>}/>
            <Route path="/random" element={<RandomPage/>}/>
            <Route path="/calendar" element={<CalendarPage/>}/>
            <Route path="/results" element={<ResultsPage/>}/>
        </Routes>
    </BrowserRouter>
);

export default App;

