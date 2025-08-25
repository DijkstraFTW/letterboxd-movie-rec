import {Menu} from "./Menu.tsx";

export const Header = () => {
    return (
        <div
            className="flex flex-row bg-neutral-100 p-4 top-0 w-full z-10 backdrop-filter backdrop-blur-lg bg-opacity-60 items-center justify-between">
            <Menu/>
            {/* search bar + light dark button*/}
            {/*<div className="flex flex-row justify-between space-x-4">
                <h3>Database</h3>
                <div className="flex flex-row items-center space-x-1">
                    <h3 className="text-gray-800 font-semibold">1000 users</h3>
                </div>
                <div className="flex flex-row items-center space-x-1">
                    <h3 className="text-gray-800 font-semibold">1000 reviews</h3>
                </div>
                <div className="flex flex-row items-center space-x-1">
                    <h3 className="text-gray-800 font-semibold">1000 movies</h3>
                </div>
                <div className="flex flex-row items-center space-x-1">
                    <h3 className="text-gray-800 font-semibold">1000 shows</h3>
                </div>
            </div>*/}
        </div>
    )
}

export default Header;