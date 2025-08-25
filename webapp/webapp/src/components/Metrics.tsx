import Background from "../assets/felix-mooneeram-evlkOfkQ5rE-unsplash.jpg";
import DOWBarChart from "./DOWBarChart.tsx";
import RPYBarChart from "./RPYBarChart.tsx";
import TopCountriesBarChart from "./TopCountriesBarChart.tsx";
import RPRYBarChart from "./RPRYBarChart.tsx";
import ARPYBarChart from "./ARPYBarChart.tsx";
import ARPDBarChart from "./ARPDBarChart.tsx";

// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-expect-error
export const Metrics = ({data, sectionTitle}) => {
    return (<div
            className="bg-neutral-100 min-h-screen bg-fixed top-0 z-0 h-full w-screen bg-cover bg-center text-white p-8"
            style={{backgroundImage: `url(${Background})`}}>
            <div className="flex flex-col h-full">
                <h1 className="text-2xl font-bold mb-4 justify-left">{sectionTitle}</h1>
                <div className="flex flex-row p-4 m-2 space-x-6 justify-center">
                    <div className="flex items-center space-x-2">
                        <span className="text-center font-bold text-4xl">{data.movies_reviewed}</span>
                        <span className="text-left"> movies</span>
                    </div>
                    <div className="flex items-center space-x-2">
                        <span className="text-center font-bold text-4xl">{data.shows_reviewed}</span>
                        <span className="text-left"> shows</span>
                    </div>
                    <div className="flex items-center space-x-2">
                        <span className="text-center font-bold text-4xl">{data.hours_watched}</span>
                        <span className="text-left"> total hours</span>
                    </div>
                    <div className="flex items-center space-x-2">
                        <span className="text-center font-bold text-4xl">{data.number_daily_reviews_over_mean}</span>
                        <span className="text-left">+{data.mean_daily_reviews} review days</span>
                    </div>
                    <div className="flex items-center space-x-2">
                        <span className="text-center font-bold text-4xl">{data.longest_streak}</span>
                        <span className="text-left"> longest week streak</span>
                    </div>
                </div>
                <div className="flex flex-row p-4 m-2">
                    <div className="flex flex-col w-1/3 justify-center ">
                        <DOWBarChart data={data.average_watched_per_day_of_week}
                                         y_field={"average_movies_watched"}/>
                    </div>
                    <div className="flex flex-col w-1/3 justify-center ">
                        <RPYBarChart data={data.logged_per_year} x_field={"year"}
                                         y_field={"num_reviews"}/>
                    </div>
                    <div className="flex flex-col w-1/3 justify-center ">
                        <TopCountriesBarChart data={data.most_common_countries} x_field={"country"}
                                         y_field={"count"}/>
                    </div>
                </div>
            </div>
            <div className="flex flex-col items-center justify-center h-full">
                <div className="flex flex-row p-4 m-2">
                    <div className="flex flex-col w-1/3 justify-center">
                        <RPRYBarChart data={data.logged_per_release_year} x_field={"year_released"}
                                         y_field={"num_movies"}/>
                    </div>
                    <div className="flex flex-col w-1/3 justify-center">
                        <ARPYBarChart data={data.average_rating_per_year} x_field={"year_released"}
                                         y_field={"average_rating"}/>
                    </div>
                    <div className="flex flex-col w-1/3 justify-center">
                        <span className="text-center"> Average rating per decade</span>
                        <ARPDBarChart data={data.average_rating_decade} x_field={"decade"}
                                         y_field={"average_rating"}/>
                    </div>
                </div>
            </div>
        </div>
    )

}