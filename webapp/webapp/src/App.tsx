import RecommendationsPage from "./pages/RecommendationsPage.tsx";
import {BrowserRouter, Routes, Route} from "react-router-dom";
import Homepage from "./pages/Homepage.tsx";
import ResultsPage from "./pages/ResultsPage.tsx";
import './index.css'


const App = () => (
    <BrowserRouter>
        <Routes>
            <Route path="/" element={<Homepage/>}/>
            <Route path="/home" element={<Homepage/>}/>
            <Route path="/recommender" element={<RecommendationsPage/>}/>
            <Route path="/results" element={<ResultsPage/>}/>
        </Routes>
    </BrowserRouter>
);

export default App;

