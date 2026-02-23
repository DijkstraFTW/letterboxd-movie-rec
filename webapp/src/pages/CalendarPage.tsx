'use client';

import { useState, useMemo, useEffect, useCallback } from 'react';
import Header from "../components/Header.tsx";
import Footer from "../components/Footer.tsx";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../shadcn/components/ui/tabs.tsx";
import { Card, CardContent } from "../../shadcn/components/ui/card.tsx";
import { Button } from "../../shadcn/components/ui/button.tsx";
import { MonitorPlayIcon, Film } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import MovieCard from "../components/MovieCard.tsx";
import { Spinner } from "../../shadcn/components/ui/spinner.tsx";
import {
    Empty,
    EmptyDescription,
    EmptyHeader,
    EmptyMedia,
    EmptyTitle,
} from "../../shadcn/components/ui/empty.tsx";
import { ReloadIcon, ExclamationTriangleIcon } from "@radix-ui/react-icons";

const MIDDLEWARE_HOST = import.meta.env.VITE_MIDDLEWARE_HOST
const MIDDLEWARE_API_KEY = import.meta.env.VITE_MIDDLEWARE_API_KEY

type Release = {
    title: string;
    slug: string;
    url: string;
    release_date: string;
    release_type: string;
    year: string;
    poster_url: string;
};

const CalendarPage = () => {
    const [selectedMonth, setSelectedMonth] = useState<string>('all');
    const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
    const [streamingReleases, setStreamingReleases] = useState<Release[]>([]);
    const [theatricalReleases, setTheatricalReleases] = useState<Release[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const months = useMemo(() => {
        const monthsArray = [{ value: 'all', label: 'All Releases' }];
        const currentDate = new Date();

        for (let i = 0; i < 3; i++) {
            const date = new Date(currentDate.getFullYear(), currentDate.getMonth() + i, 1);
            const yearMonth = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
            const monthName = date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
            monthsArray.push({ value: yearMonth, label: monthName });
        }

        return monthsArray;
    }, []);

    const fetchCalendarReleases = useCallback(async () => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await fetch(`${MIDDLEWARE_HOST}/calendar/releases`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': MIDDLEWARE_API_KEY,
                },
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            const allStreaming: Release[] = [];
            const allTheatrical: Release[] = [];

            if (Array.isArray(data)) {
                data.forEach((dateEntry: any) => {
                    if (Array.isArray(dateEntry.streaming_releases)) {
                        allStreaming.push(...dateEntry.streaming_releases);
                    }
                    if (Array.isArray(dateEntry.theater_releases)) {
                        allTheatrical.push(...dateEntry.theater_releases);
                    }
                });
            }

            setStreamingReleases(allStreaming);
            setTheatricalReleases(allTheatrical);
            setTimeout(() => {
                setIsLoading(false);
            }, 2000);
        } catch (err) {
            console.error('Error fetching calendar releases:', err);
            setError(err instanceof Error ? err.message : 'Failed to fetch releases');
        } finally {
            setTimeout(() => {
                setIsLoading(false);
            }, 2000);
        }
    }, []);

    useEffect(() => {
        fetchCalendarReleases();
    }, [fetchCalendarReleases]);

    const filterByMonth = (releases: Release[]) => {
        if (selectedMonth === 'all') return releases;
        return releases.filter(release => release.release_date.startsWith(selectedMonth));
    };

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    };

    const groupByWeek = (releases: Release[]) => {
        const groups: { [key: string]: Release[] } = {};
        releases.forEach(release => {
            const date = new Date(release.release_date);
            const weekStart = new Date(date);
            weekStart.setDate(date.getDate() - date.getDay());
            const weekKey = weekStart.toISOString().split('T')[0];
            if (!groups[weekKey]) {
                groups[weekKey] = [];
            }
            groups[weekKey].push(release);
        });
        return groups;
    };

    const ReleaseCard = ({ release }: { release: Release }) => (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
        >
            <MovieCard
                poster_url={release.poster_url}
                movie_title={release.title}
                runtime={""}
                genres={[]}
                showTopPickButton={false}
            />
        </motion.div>
    );

    const GridView = ({ releases }: { releases: Release[] }) => {
        const groupedByWeek = groupByWeek(releases);
        const sortedWeeks = Object.keys(groupedByWeek).sort();

        return (
            <div className="space-y-8">
                {sortedWeeks.map(weekKey => (
                    <div key={weekKey}>
                        <h3 className="text-xl font-semibold text-white mb-4">
                            Week of {formatDate(weekKey)}
                        </h3>
                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                            <AnimatePresence mode="wait">
                                {groupedByWeek[weekKey]
                                    .sort((a, b) => new Date(a.release_date).getTime() - new Date(b.release_date).getTime())
                                    .map(release => (
                                        <ReleaseCard key={release.slug} release={release} />
                                    ))}
                            </AnimatePresence>
                        </div>
                    </div>
                ))}
            </div>
        );
    };

    const ListView = ({ releases }: { releases: Release[] }) => {
        const sortedReleases = [...releases].sort((a, b) =>
            new Date(a.release_date).getTime() - new Date(b.release_date).getTime()
        );

        return (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                <AnimatePresence mode="wait">
                    {sortedReleases.map(release => (
                        <ReleaseCard key={release.slug} release={release} />
                    ))}
                </AnimatePresence>
            </div>
        );
    };

    if (isLoading) {
        return (
            <div className="bg-black min-h-screen flex flex-col">
                <Header />
                <div className="max-w-screen-xl w-full mx-auto pb-16 flex-1 mt-6 sm:mt-10 px-4 text-white">
                    <div className="mb-8">
                        <h1 className="text-4xl font-bold text-white mb-2">Upcoming Releases</h1>
                        <p className="text-white/60">Track upcoming streaming and theatrical releases</p>
                    </div>
                    <Empty className="flex items-center justify-center w-full h-96">
                        <EmptyHeader>
                            <EmptyMedia variant="icon">
                                <Spinner />
                            </EmptyMedia>
                            <EmptyTitle>Loading upcoming movies...</EmptyTitle>
                            <EmptyDescription>
                                Please wait while we process your request. Do not refresh the page.
                            </EmptyDescription>
                        </EmptyHeader>
                    </Empty>
                </div>
                <Footer />
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-black min-h-screen flex flex-col">
                <Header />
                <div className="max-w-screen-xl w-full mx-auto pb-16 flex-1 mt-6 sm:mt-10 px-4">
                    <div className="mb-8">
                        <h1 className="text-4xl font-bold text-white mb-2">Upcoming Releases</h1>
                        <p className="text-white/60">Track upcoming streaming and theatrical releases</p>
                    </div>
                    <Empty className="flex items-center justify-center w-full h-96">
                        <EmptyHeader>
                            <EmptyMedia variant="icon">
                                <ExclamationTriangleIcon className="w-12 h-12 text-red-400/80" />
                            </EmptyMedia>
                            <EmptyTitle className="text-red-400">Failed to Load Releases</EmptyTitle>
                            <EmptyDescription className="space-y-2">
                                <p className="text-white/60">
                                    Unable to connect to the server. Please check your connection and try again.
                                </p>
                                <Button
                                    onClick={fetchCalendarReleases}
                                    className="inline-flex items-center justify-center gap-2 whitespace-nowrap transition-colors focus-visible:outline-none cursor-pointer border px-4 py-2 bg-white/5 hover:bg-white/10 text-white border-white/10 rounded-lg text-sm font-medium mt-4"
                                >
                                    <ReloadIcon className="w-4 h-4" />
                                    Try Again
                                </Button>
                            </EmptyDescription>
                        </EmptyHeader>
                    </Empty>
                </div>
                <Footer />
            </div>
        );
    }

    return (
        <div className="bg-black min-h-screen flex flex-col">
            <Header />
            <div className="max-w-screen-xl w-full mx-auto pb-16 flex-1 mt-6 sm:mt-10 px-4">
                <div className="mb-8">
                    <h1 className="text-4xl font-bold text-white mb-2">Upcoming Releases</h1>
                    <p className="text-white/60">Track upcoming streaming and theatrical releases</p>
                </div>

                <div className="flex flex-col sm:flex-row gap-4 mb-6">
                    <div className="flex gap-2 flex-wrap">
                        {months.map(month => (
                            <Button
                                key={month.value}
                                onClick={() => setSelectedMonth(month.value)}
                                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${selectedMonth === month.value
                                        ? 'bg-white text-black hover:bg-gray-100'
                                        : 'bg-white/5 hover:bg-white/10 text-white/80 border-white/10'
                                    }`}
                            >
                                {month.label}
                            </Button>
                        ))}
                    </div>
                    <div className="flex gap-2 sm:ml-auto">
                        <Button
                            onClick={() => setViewMode('grid')}
                            className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${viewMode === 'grid'
                                    ? 'bg-white text-black hover:bg-gray-100'
                                    : 'bg-white/5 hover:bg-white/10 text-white/80 border-white/10'
                                }`}
                        >
                            By Week
                        </Button>
                        <Button
                            onClick={() => setViewMode('list')}
                            className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${viewMode === 'list'
                                    ? 'bg-white text-black hover:bg-gray-100'
                                    : 'bg-white/5 hover:bg-white/10 text-white/80 border-white/10'
                                }`}
                        >
                            All Releases
                        </Button>
                    </div>
                </div>

                <Tabs defaultValue="streaming" className="w-full">
                    <TabsList className="bg-white/5 border-white/10 mb-6">
                        <TabsTrigger
                            value="streaming"
                            className="data-[state=active]:bg-white data-[state=active]:text-black text-white/80"
                        >
                            <MonitorPlayIcon className="w-4 h-4 mr-2" />
                            Streaming
                        </TabsTrigger>
                        <TabsTrigger
                            value="theatrical"
                            className="data-[state=active]:bg-white data-[state=active]:text-black text-white/80"
                        >
                            <Film className="w-4 h-4 mr-2" />
                            Theatrical
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="streaming" className="mt-0">
                        {viewMode === 'grid' ? (
                            <GridView releases={filterByMonth(streamingReleases)} />
                        ) : (
                            <ListView releases={filterByMonth(streamingReleases)} />
                        )}
                        {filterByMonth(streamingReleases).length === 0 && (
                            <Card className="bg-white/5 border-white/10 p-12 text-center">
                                <CardContent>
                                    <MonitorPlayIcon className="w-12 h-12 text-white/30 mx-auto mb-4" />
                                    <p className="text-white/60">No streaming releases for this period</p>
                                </CardContent>
                            </Card>
                        )}
                    </TabsContent>

                    <TabsContent value="theatrical" className="mt-0">
                        {viewMode === 'grid' ? (
                            <GridView releases={filterByMonth(theatricalReleases)} />
                        ) : (
                            <ListView releases={filterByMonth(theatricalReleases)} />
                        )}
                        {filterByMonth(theatricalReleases).length === 0 && (
                            <Card className="bg-white/5 border-white/10 p-12 text-center">
                                <CardContent>
                                    <Film className="w-12 h-12 text-white/30 mx-auto mb-4" />
                                    <p className="text-white/60">No theatrical releases for this period</p>
                                </CardContent>
                            </Card>
                        )}
                    </TabsContent>
                </Tabs>
            </div>
            <Footer />
        </div>
    );
}

export default CalendarPage;
