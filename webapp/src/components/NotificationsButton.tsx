import { BellIcon } from "lucide-react";
import { Button } from "../../shadcn/components/ui/button.tsx";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "../../shadcn/components/ui/dropdown-menu";
import { DropdownMenuGroup } from "@radix-ui/react-dropdown-menu";
import { useState, useEffect } from "react";

const MIDDLEWARE_HOST = import.meta.env.VITE_MIDDLEWARE_HOST
const MIDDLEWARE_API_KEY = import.meta.env.VITE_MIDDLEWARE_API_KEY

interface Announcement {
  title: string;
  description: string;
  date: string;
}

export default function NotificationsButton() {
  const [notifications, setNotifications] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnnouncements = async () => {
      try {
        const response = await fetch(`${MIDDLEWARE_HOST}/announcements`, {
          headers: {
            'X-API-Key': MIDDLEWARE_API_KEY,
          },
        });
        if (response.ok) {
          const data = await response.json();
          setNotifications(data);
        } else {
          console.error("Failed to fetch announcements");
        }
      } catch (error) {
        console.error("Error fetching announcements:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchAnnouncements();
  }, []);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger>
        <Button className="relative inline-flex items-center justify-center whitespace-nowrap transition-colors focus-visible:outline-none cursor-pointer disabled:pointer-events-none disabled:opacity-50 border px-3 py-1.5 bg-white/5 hover:bg-white/10 text-white/80 border-white/5 rounded-full text-sm h-8 font-medium">
          <BellIcon />
            <span className="absolute top-1.5 right-1.5 block h-2 w-2 rounded-full bg-red-500"></span>
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        className="absolute right-0 z-50 w-80 rounded-lg border border-white/10 bg-[#121212] text-white/80"
        align="end"
      >
        <DropdownMenuLabel className="text-sm font-medium border-b border-white/10">
          Announcements
        </DropdownMenuLabel>
        <DropdownMenuGroup>
          {loading ? (
            <DropdownMenuItem className="hover:bg-white/5 focus:bg-white/5 pointer-events-none focus:outline-none">
              <div className="rounded-md bg-[#1e1e1e] p-3 text-center w-full">
                <div className="text-sm text-white/60">Loading announcements...</div>
              </div>
            </DropdownMenuItem>
          ) : notifications.length === 0 ? (
            <DropdownMenuItem className="hover:bg-white/5 focus:bg-white/5 pointer-events-none focus:outline-none">
              <div className="rounded-md bg-[#1e1e1e] p-3 text-center w-full">
                <div className="text-sm text-white/60">No new announcements</div>
              </div>
            </DropdownMenuItem>
          ) : (
            notifications.map((notif, index) => (
              <DropdownMenuItem
                key={index}
                className="hover:bg-white/5 focus:bg-white/5 pointer-events-none focus:outline-none"
              >
                <div className="rounded-md bg-[#1e1e1e] cursor-pointer [&:not(:last-child)]:mb-2 p-3">
                  <div className="text-sm text-white/80 font-semibold mb-0.5">
                    {notif.title}
                  </div>
                  <div className="text-xs text-white/60 leading-snug">
                    {notif.description}
                  </div>
                </div>
              </DropdownMenuItem>
            ))
          )}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
