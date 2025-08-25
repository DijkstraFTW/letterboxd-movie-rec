import MovieCard from "./MovieCard.tsx";

// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-expect-error
const MovieGrid = ({sectionTitle, movies}) => {
    return (<div
        className="flex rounded-md p-4 bg-gray-200 text-gray-700">
        <div className="flex flex-col h-full">
            <h1 className="text-2xl font-bold mb-4 w-fit justify-left">{sectionTitle}</h1>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-8">
                {movies.map((movie: any) => (<MovieCard key={movie.id} {...movie} />))}
            </div>
        </div>
    </div>)
}
export default MovieGrid;