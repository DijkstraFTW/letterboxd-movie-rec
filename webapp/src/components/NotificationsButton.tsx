import { BellIcon } from "lucide-react";
import { Button } from "../../shadcn/components/ui/button.tsx";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "../../shadcn/components/ui/dropdown-menu";
import { DropdownMenuGroup } from "@radix-ui/react-dropdown-menu";
import { useState, useEffect } from "react";

const MIDDLEWARE_HOST = import.meta.env.VITE_MIDDLEWARE_HOST
const MIDDLEWARE_API_KEY = import.meta.env.VITE_MIDDLEWARE_API_KEY

interface Announcement {
  id: string;
  title: string;
  message: string;
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
            <div className="px-3 py-6 text-center text-sm text-white/40">
              Loading announcements...
            </div>
          ) : notifications.length === 0 ? (
            <div className="px-3 py-6 text-center text-sm text-white/40">
              No new announcements
            </div>
          ) : (
            <div className="py-1">
              {notifications.map((notif, index) => (
                <div
                  key={index}
                  className={`px-3 py-3 ${index !== notifications.length - 1 ? "border-b border-white/5" : ""}`}
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <span className="text-sm font-semibold text-white leading-tight">{notif.title}</span>
                  </div>
                  <p className="text-xs text-white/50 leading-relaxed">{notif.message}</p>
                </div>
              ))}
            </div>
          )}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
