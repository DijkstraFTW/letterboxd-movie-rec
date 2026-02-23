import Header from "../components/Header.tsx";
import Footer from "../components/Footer.tsx";
import { Construction } from "lucide-react";

const RecommendationsPage = () => {
    return (
        <div className="bg-black min-h-screen flex flex-col">
            <Header/>
            <div className="max-w-screen-xl w-full mx-auto pb-16 flex-1 mt-6 sm:mt-10 px-4">
                <div className="mb-8">
                    <h1 className="text-4xl font-bold text-white mb-2">Smart Search</h1>
                    <p className="text-white/60">Describe your ideal movie of the moment and let us find the closest matchs</p>
                </div>

                <div className="flex items-center justify-center min-h-[400px]">
                    <div className="text-center">
                        <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-white/5 border border-white/10 mb-6">
                            <Construction className="w-10 h-10 text-white/40" />
                        </div>
                        <h2 className="text-2xl font-semibold text-white mb-3">Work in Progress</h2>
                        <p className="text-white/60 max-w-md">
                            We're currently still building this feature.
                            Check back soon!
                        </p>
                    </div>
                </div>
            </div>
            <Footer/>
        </div>
    );
}

export default RecommendationsPage;