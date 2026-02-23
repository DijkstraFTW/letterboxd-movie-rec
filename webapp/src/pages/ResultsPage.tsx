import { useLocation } from "react-router-dom";
import Header from "../components/Header.tsx";
import MovieGrid from "../components/MovieGrid.tsx";
import Footer from "../components/Footer.tsx";
import { UserMetrics } from "../components/UserMetrics.tsx";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../shadcn/components/ui/tabs.tsx";
import { FilmIcon, AreaChartIcon, CandlestickChartIcon } from "lucide-react";
import { AdvancedUserMetrics } from "../components/AdvancedUserMetrics.tsx";

const ResultsPage = () => {
    const location = useLocation();
    const formType = location.state?.formType as 'letterboxd' | 'genres' | undefined;
    const stateMovies = location.state?.movies ?? [];
    const stateAnalytics = location.state?.analytics ?? {};
    const stateUsername = location.state?.username as string | undefined;

    const displayMovies = stateMovies;
    const displayMetrics = stateAnalytics;

    const displayAdvancedMetrics = {
        consensusData: displayMetrics.rating_vs_consensus ?? [],
        histogramData: displayMetrics.histogram_superposition ?? [],
        popularityData: displayMetrics.popularity_vs_rating ?? [],
        trendData: displayMetrics.rating_trend ?? [],
        themeData: displayMetrics.theme_explorer ?? [],
        positiveCorrelations: displayMetrics.nanogenre_correlations?.positive ?? [],
        negativeCorrelations: displayMetrics.nanogenre_correlations?.negative ?? [],
    };

    const hasAnalytics = formType === 'letterboxd'
        ? Object.keys(displayMetrics).length > 0
        : true;
    const showAnalyticsTabs = formType !== 'genres' && hasAnalytics;

    const username: string = stateUsername ?? ""
    return (
        <div className="bg-black min-h-screen flex flex-col">
            <Header />
            <div className="max-w-screen-xl w-full mx-auto pb-16 flex-1 mt-6 sm:mt-10 px-4">
                <div className="mb-8">
                    {formType === 'genres' ? (
                        <>
                            <h1 className="text-4xl font-bold text-white mb-2">Your Recommendations</h1>
                            <p className="text-white/60">Discover movies tailored to your selected genres and preferences.</p>
                        </>
                    ) : (
                        <>
                            <h1 className="text-4xl font-bold text-white mb-2">{username}'s profile</h1>
                            <p className="text-white/60">Discover personalized recommendations and insights from your viewing history.</p>
                        </>
                    )}
                </div>
                <Tabs defaultValue="recs" className="w-full">
                    <TabsList className="bg-white/5 border-white/10 mb-6">
                        <TabsTrigger value="recs" className="data-[state=active]:bg-white data-[state=active]:text-black text-white/80">
                            <FilmIcon className="w-4 h-4 mr-2" />
                            Recommendations
                        </TabsTrigger>
                        {showAnalyticsTabs && (
                            <TabsTrigger value="metrics" className="data-[state=active]:bg-white data-[state=active]:text-black text-white/80">
                                <AreaChartIcon className="w-4 h-4 mr-2" />
                                Statistics
                            </TabsTrigger>
                        )}
                        {showAnalyticsTabs && (
                            <TabsTrigger value="cohort" className="data-[state=active]:bg-white data-[state=active]:text-black text-white/80">
                                <CandlestickChartIcon className="w-4 h-4 mr-2" />
                                Advanced
                            </TabsTrigger>
                        )}
                    </TabsList>
                    <TabsContent value="recs" className="mt-0">
                        <MovieGrid movies={displayMovies} sectionTitle="" />
                    </TabsContent>
                    {showAnalyticsTabs && (
                        <TabsContent value="metrics" className="mt-0">
                            <UserMetrics data={displayMetrics} sectionTitle="" />
                        </TabsContent>
                    )}
                    {showAnalyticsTabs && (
                        <TabsContent value="cohort" className="mt-0">
                            <AdvancedUserMetrics
                                sectionTitle=""
                                consensusData={displayAdvancedMetrics.consensusData}
                                histogramData={displayAdvancedMetrics.histogramData}
                                popularityData={displayAdvancedMetrics.popularityData}
                                trendData={displayAdvancedMetrics.trendData}
                                themeData={displayAdvancedMetrics.themeData}
                                positiveCorrelations={displayAdvancedMetrics.positiveCorrelations}
                                negativeCorrelations={displayAdvancedMetrics.negativeCorrelations}
                            />
                        </TabsContent>
                    )}
                </Tabs>
            </div>
            <Footer />
        </div>
    )
        ;
}

export default ResultsPage;