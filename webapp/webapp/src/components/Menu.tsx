import {
    DropdownMenu,
    DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem,
    DropdownMenuLabel, DropdownMenuSeparator,
    DropdownMenuTrigger
} from "../../shadcn/components/ui/dropdown-menu.tsx";
import {HomeIcon, InfoCircledIcon} from "@radix-ui/react-icons";


export function Menu() {
    return (
        <div>
            <DropdownMenu>
                <DropdownMenuTrigger
                    className="flex  items-center space-x-1.5 font-semibold text-gray-800 border-2 rounded-3xl px-2">
                    <img width="32" height="32" src="https://img.icons8.com/nolan/64/movie.png"
                         alt="movie"/>
                    <span>flicks</span>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="bg-white z-20 p-2 w-56" align="end" forceMount>
                    <DropdownMenuLabel>Menu</DropdownMenuLabel>
                    <DropdownMenuGroup>
                        <a href="/home">
                            <DropdownMenuItem>
                                <HomeIcon className="mr-2"/>
                                <span>Home</span>
                            </DropdownMenuItem>
                        </a>
                    </DropdownMenuGroup>
                    <DropdownMenuGroup>
                        <a href="/recommender">
                            <DropdownMenuItem>
                                <img className="mr-2" width="18" height="18"
                                     src="https://img.icons8.com/ios/50/dice.png" alt="dice"/>
                                <span>Recommender</span>
                            </DropdownMenuItem>
                        </a>
                        <a href="/streaming">
                            <DropdownMenuItem>
                                <img className="mr-2" width="18" height="18"
                                     src="https://img.icons8.com/ios/50/online--v1.png" alt="online--v1"/>
                                <span>Streaming</span>
                            </DropdownMenuItem>
                        </a>
                        <DropdownMenuSeparator/>
                        <a href="/about">
                            <DropdownMenuItem>
                                <InfoCircledIcon className="mr-2"/>
                                <span>About</span>
                            </DropdownMenuItem>
                        </a>
                    </ DropdownMenuGroup>
                </DropdownMenuContent>
            </DropdownMenu>
        </div>
    )
}