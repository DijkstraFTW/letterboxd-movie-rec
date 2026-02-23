import Header from "../components/Header.tsx";
import Footer from "../components/Footer.tsx";

const AboutPage = () => {
    return (
        <div className="bg-black min-h-screen flex flex-col">
            <Header />
            <div className="max-w-screen-xl w-full mx-auto pb-16 flex-1 mt-6 sm:mt-10 px-4">
                <div className="mb-8">
                    <h1 className="text-4xl font-bold text-white mb-4">About This Project</h1>
                    <p className="text-white/80 text-lg leading-relaxed">
                        Discover your next favorite film with personalized recommendations powered by your Letterboxd viewing history and ratings.
                    </p>
                </div>

                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                        <div className="bg-white/5 border border-white/10 rounded-lg p-6">
                            <h2 className="text-2xl font-semibold text-white mb-3">What We Do</h2>
                            <p className="text-white/70 leading-relaxed">
                                We analyze your Letterboxd profile to understand your unique taste in cinema. By examining your ratings, reviews, and favorite films,
                                our recommendation engine suggests movies you're likely to love but haven't discovered yet.
                            </p>
                        </div>

                        <div className="bg-white/5 border border-white/10 rounded-lg p-6">
                            <h2 className="text-2xl font-semibold text-white mb-3">How It Works</h2>
                            <p className="text-white/70 leading-relaxed mb-4">
                                Our system uses advanced data processing and machine learning to provide tailored recommendations:
                            </p>
                            <ul className="space-y-2 text-white/70">
                                <li className="flex items-start">
                                    <span className="text-white/80 mr-2">•</span>
                                    <span>Connect your Letterboxd username to import your viewing history</span>
                                </li>
                                <li className="flex items-start">
                                    <span className="text-white/80 mr-2">•</span>
                                    <span>Our engine analyzes patterns in your ratings and preferences</span>
                                </li>
                                <li className="flex items-start">
                                    <span className="text-white/80 mr-2">•</span>
                                    <span>Get personalized recommendations based on genres, themes, and similar films</span>
                                </li>
                                <li className="flex items-start">
                                    <span className="text-white/80 mr-2">•</span>
                                    <span>Explore curated collections, trending picks, and randomized selections</span>
                                </li>
                            </ul>
                        </div>

                        <div className="bg-white/5 border border-white/10 rounded-lg p-6">
                            <h2 className="text-2xl font-semibold text-white mb-3">Privacy & Data</h2>
                            <p className="text-white/70 leading-relaxed">
                                Your privacy matters. We only access publicly available information from your Letterboxd profile.
                                You can opt out of data sharing at any time, and we never store sensitive personal information.
                            </p>
                        </div>
                    </div>
                </div>
            <Footer />
        </div>
    );
}

export default AboutPage;