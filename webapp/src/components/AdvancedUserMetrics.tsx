import { useState, useMemo } from "react";
import {
  ScatterChart, Scatter, XAxis, YAxis, Tooltip, Cell, ReferenceLine,
  Line, Area, AreaChart,
  Treemap, ResponsiveContainer, CartesianGrid, Customized,
} from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../shadcn/components/ui/card.tsx";

const GENRE_COLORS: Record<string, string> = {
  "Action": "#ef4444",
  "Action & Adventure": "#f87171",
  "Adventure": "#3b82f6",
  "Animation": "#f97316",
  "Comedy": "#22c55e",
  "Crime": "#6366f1",
  "Documentary": "#84cc16",
  "Drama": "#8b5cf6",
  "Family": "#34d399",
  "Fantasy": "#06b6d4",
  "History": "#d97706",
  "Horror": "#dc2626",
  "Kids": "#fb923c",
  "Music": "#e879f9",
  "Mystery": "#a855f7",
  "News": "#94a3b8",
  "Reality": "#facc15",
  "Romance": "#ec4899",
  "Sci-Fi & Fantasy": "#0891b2",
  "Science Fiction": "#14b8a6",
  "Soap": "#f9a8d4",
  "Talk": "#a3a3a3",
  "Thriller": "#f59e0b",
  "TV Movie": "#475569",
  "War": "#78716c",
  "War & Politics": "#57534e",
  "Western": "#b45309",
  "Other": "#64748b",
};

const getGenreColor = (genre: string) => GENRE_COLORS[genre] || GENRE_COLORS["Other"];

const RATING_COLOR_STOPS = [
  { at: 0,  r: 59,  g: 130, b: 246 }, // blue      (1-2)
  { at: 4,  r: 139, g: 92,  b: 246 }, // violet    (3-4)
  { at: 6,  r: 245, g: 158, b: 11  }, // amber     (5-6)
  { at: 8,  r: 249, g: 115, b: 22  }, // orange    (7-8)
  { at: 10, r: 239, g: 68,  b: 68  }, // red       (9-10)
];

const getRatingColor = (rating: number) => {
  const clamped = Math.max(0, Math.min(10, rating));
  let lo = RATING_COLOR_STOPS[0];
  let hi = RATING_COLOR_STOPS[RATING_COLOR_STOPS.length - 1];
  for (let i = 0; i < RATING_COLOR_STOPS.length - 1; i++) {
    if (clamped >= RATING_COLOR_STOPS[i].at && clamped <= RATING_COLOR_STOPS[i + 1].at) {
      lo = RATING_COLOR_STOPS[i];
      hi = RATING_COLOR_STOPS[i + 1];
      break;
    }
  }
  const t = lo.at === hi.at ? 0 : (clamped - lo.at) / (hi.at - lo.at);
  const r = Math.round(lo.r + t * (hi.r - lo.r));
  const g = Math.round(lo.g + t * (hi.g - lo.g));
  const b = Math.round(lo.b + t * (hi.b - lo.b));
  return `rgb(${r}, ${g}, ${b})`;
};

type ConsensusItem = {
  title: string;
  userRating: number;
  publicRating: number;
  genre: string;
  posterUrl: string;
};

type HistogramItem = {
  rating: string;
  user: number;
  community: number;
};

type PopularityItem = {
  title: string;
  voteCount: number;
  userRating: number;
  genre: string;
  posterUrl: string;
};

type TrendItem = {
  date: string;
  rollingAvg: number;
  actual: number;
};

type ThemeItem = {
  name: string;
  size: number;
  avgRating: number;
};

type CorrelationItem = {
  tag: string;
  correlation: number;
  avgRating: number;
  count: number;
};

const ConsensusTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const d = payload[0].payload;
    return (
      <div className="rounded-lg border bg-background p-3 shadow-sm max-w-xs">
        <div className="flex items-start gap-3">
          {d.posterUrl && (
            <div className="flex-shrink-0">
              <img
                src={d.posterUrl} alt={d.title} loading="lazy"
                className="w-16 h-24 object-cover rounded shadow-md bg-muted"
                onError={(e) => { e.currentTarget.parentElement!.style.display = "none"; }}
              />
            </div>
          )}
          <div className="flex flex-col gap-1 min-w-0">
            <span className="text-sm text-muted-foreground font-bold leading-tight">{d.title}</span>
            <span className="text-sm text-muted-foreground">{d.genre}</span>
            <span className="text-sm text-muted-foreground">Your rating: <span className="font-bold">{d.userRating}/10</span></span>
            <span className="text-sm text-muted-foreground">Public: <span className="font-bold">{d.publicRating}/10</span></span>
          </div>
        </div>
      </div>
    );
  }
  return null;
};

const HistogramTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-lg border bg-background p-3 shadow-sm">
        <div className="flex flex-col gap-1">
          <span className="text-sm text-muted-foreground">Rating <span className="font-bold">{label}/10</span></span>
          {payload.map((p: any, i: number) => (
            <span key={i} className="text-sm text-muted-foreground">
              {p.name === "user" ? "You" : "Community"}: <span className="font-bold">{p.value} movies</span>
            </span>
          ))}
        </div>
      </div>
    );
  }
  return null;
};

const PopularityTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const d = payload[0].payload;
    return (
      <div className="rounded-lg border bg-background p-3 shadow-sm max-w-xs">
        <div className="flex items-start gap-3">
          {d.posterUrl && (
            <div className="flex-shrink-0">
              <img
                src={d.posterUrl} alt={d.title} loading="lazy"
                className="w-16 h-24 object-cover rounded shadow-md bg-muted"
                onError={(e) => { e.currentTarget.parentElement!.style.display = "none"; }}
              />
            </div>
          )}
          <div className="flex flex-col gap-1 min-w-0">
            <span className="text-sm text-muted-foreground font-bold leading-tight">{d.title}</span>
            <span className="text-sm text-muted-foreground">{d.genre}</span>
            <span className="text-sm text-muted-foreground">Your rating: <span className="font-bold">{d.userRating}/10</span></span>
            <span className="text-sm text-muted-foreground">Popularity: <span className="font-bold">{d.voteCount >= 1000 ? `${(d.voteCount / 1000).toFixed(1).replace(/\.0$/, "")}k` : d.voteCount} votes</span></span>
          </div>
        </div>
      </div>
    );
  }
  return null;
};

const formatDate = (dateStr: string) => {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
};

const TrendTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-lg border bg-background p-3 shadow-sm">
        <div className="flex flex-col gap-1">
          <span className="text-sm text-muted-foreground font-bold">{formatDate(label)}</span>
          <span className="text-sm text-muted-foreground">30-day film avg: <span className="font-bold">{payload[0]?.value}/10</span></span>
          {payload[1] && <span className="text-sm text-muted-foreground">Actual rating: <span className="font-bold">{payload[1]?.value}/10</span></span>}
        </div>
      </div>
    );
  }
  return null;
};

const getCorrelationColor = (avgRating: number) => {
  if (avgRating >= 6.5) {
    const t = Math.max(0, Math.min(1, (avgRating - 6.5) / (8.8 - 6.5)));
    const opacity = 0.25 + t * 0.75;
    return `rgba(34, 197, 94, ${opacity.toFixed(2)})`;
  }
  const t = Math.max(0, Math.min(1, (6.5 - avgRating) / 2.5));
  const opacity = 0.25 + t * 0.75;
  return `rgba(239, 68, 68, ${opacity.toFixed(2)})`;
};

const CorrelationTreemapContent = (props: any) => {
  const { x, y, width, height, name, avgRating } = props;
  if (width < 30 || height < 20) return null;
  const clipId = `ct-${Math.round(x)}-${Math.round(y)}`;
  const fontSize = width < 100 ? 9 : 11;
  const charsPerLine = Math.max(4, Math.floor((width - 12) / (fontSize * 0.58)));
  const label = (name?.length ?? 0) > charsPerLine ? name.slice(0, charsPerLine - 1) + "…" : name;
  const showRating = height >= 38;
  return (
    <g>
      <clipPath id={clipId}>
        <rect x={x + 1} y={y + 1} width={width - 2} height={height - 2} />
      </clipPath>
      <rect x={x} y={y} width={width} height={height} fill={getCorrelationColor(avgRating)} stroke="#111111" strokeWidth={2} rx={4} />
      <g clipPath={`url(#${clipId})`}>
        <text
          x={x + width / 2} y={showRating ? y + height / 2 - 7 : y + height / 2}
          textAnchor="middle" dominantBaseline="middle"
          fill="white" fontSize={fontSize} fontWeight="600"
        >
          {label}
        </text>
        {showRating && (
          <text
            x={x + width / 2} y={y + height / 2 + 8}
            textAnchor="middle" dominantBaseline="middle"
            fill="white" fontSize={9} fillOpacity={0.7}
          >
            {avgRating}/10
          </text>
        )}
      </g>
    </g>
  );
};

const TreemapTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const d = payload[0]?.payload;
    if (!d?.name) return null;
    return (
      <div className="rounded-lg border bg-background p-3 shadow-sm">
        <div className="flex flex-col gap-1">
          <span className="text-sm text-muted-foreground font-bold leading-tight">{d.name}</span>
          <span className="text-sm text-muted-foreground">Avg rating: <span className="font-bold">{d.avgRating}/10</span></span>
          <span className="text-sm text-muted-foreground">Movies watched: <span className="font-bold">{d.size}</span></span>
        </div>
      </div>
    );
  }
  return null;
};

const ScatterLegend = ({
  data,
  selectedGenres,
  onToggle,
}: {
  data: { genre: string }[];
  selectedGenres: Set<string>;
  onToggle: (genre: string) => void;
}) => {
  const genres = [...new Set(data.map(d => d.genre))];
  const noneSelected = selectedGenres.size === 0;
  return (
    <div className="flex flex-wrap gap-2 mt-3 justify-center">
      {genres.map(g => {
        const active = noneSelected || selectedGenres.has(g);
        return (
          <button
            key={g}
            onClick={() => onToggle(g)}
            className="flex items-center gap-1.5 text-xs rounded px-1.5 py-0.5 cursor-pointer transition-opacity"
            style={{ opacity: active ? 1 : 0.25 }}
          >
            <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: getGenreColor(g) }} />
            <span style={{ color: active ? "rgba(255,255,255,0.8)" : "rgba(255,255,255,0.4)" }}>{g}</span>
          </button>
        );
      })}
    </div>
  );
};

const HistogramLegend = () => (
  <div className="flex gap-4 mt-3 justify-center">
    <div className="flex items-center gap-1.5 text-xs text-white/60">
      <div className="w-2.5 h-2.5 rounded-sm bg-[#8b5cf6]" />
      You
    </div>
    <div className="flex items-center gap-1.5 text-xs text-white/60">
      <div className="w-2.5 h-2.5 rounded-sm bg-white/20" />
      Community
    </div>
  </div>
);

const QuadrantLabels = (props: any) => {
  const xAxis = props.xAxisMap?.[0];
  const yAxis = props.yAxisMap?.[0];
  if (!xAxis?.scale || !yAxis?.scale) return null;

  const [xMin, xMax] = xAxis.domain ?? [100, 30000];
  const xMidVal = Math.sqrt(xMin * xMax); // geometric midpoint for log scale
  const x0   = xAxis.scale(xMin);
  const xMid = xAxis.scale(xMidVal);
  const xEnd  = xAxis.scale(xMax);
  const yTop = yAxis.scale(10);
  const yMid = yAxis.scale(6);
  const yBot = yAxis.scale(0);

  if ([x0, xMid, xEnd, yTop, yMid, yBot].some(v => isNaN(v))) return null;

  const quadrants = [
    { label: "Hidden Gems",       x: (x0 + xMid) / 2,  y: (yTop + yMid) / 2 },
    { label: "Popular Favorites", x: (xMid + xEnd) / 2, y: (yTop + yMid) / 2 },
    { label: "Obscure Misses",    x: (x0 + xMid) / 2,  y: (yMid + yBot) / 2 },
    { label: "Mainstream Misses", x: (xMid + xEnd) / 2, y: (yMid + yBot) / 2 },
  ];

  return (
    <g pointerEvents="none">
      {quadrants.map(({ label, x, y }) => (
        <text key={label} x={x} y={y} textAnchor="middle" dominantBaseline="middle"
          fill="rgba(255,255,255,0.30)" fontSize={13} fontWeight="600" letterSpacing="0.5">
          {label}
        </text>
      ))}
    </g>
  );
};

const makeOutlierLabels = (outliers: { title: string; [key: string]: any }[], xKey: string = 'voteCount', yKey: string = 'userRating') =>
  function OutlierLabels(props: any) {
    const xAxis = props.xAxisMap?.[0];
    const yAxis = props.yAxisMap?.[0];
    if (!xAxis?.scale || !yAxis?.scale) return null;
    return (
      <g pointerEvents="none">
        {outliers.map((d) => {
          const cx = xAxis.scale(d[xKey]);
          const cy = yAxis.scale(d[yKey]);
          if (isNaN(cx) || isNaN(cy)) return null;
          const label = d.title.length > 18 ? d.title.slice(0, 17) + "…" : d.title;
          return (
            <g key={d.title}>
              <circle cx={cx} cy={cy} r={7} fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth={1.5} />
              <text x={cx} y={cy - 12} textAnchor="middle" fontSize={9} fill="rgba(255,255,255,0.7)">{label}</text>
            </g>
          );
        })}
      </g>
    );
  };

const CorrelationBar = ({ value, positive }: { value: number; positive: boolean }) => {
  const width = Math.abs(value) * 100;
  return (
    <div className="w-24 h-2 bg-white/5 rounded-full overflow-hidden">
      <div
        className="h-full rounded-full"
        style={{
          width: `${width}%`,
          backgroundColor: positive ? "#22c55e" : "#ef4444",
        }}
      />
    </div>
  );
};

type AdvancedUserMetricsProps = {
  sectionTitle: string;
  consensusData: ConsensusItem[];
  histogramData: HistogramItem[];
  popularityData: PopularityItem[];
  trendData: TrendItem[];
  themeData: ThemeItem[];
  positiveCorrelations: CorrelationItem[];
  negativeCorrelations: CorrelationItem[];
};

export const AdvancedUserMetrics = ({
  sectionTitle,
  consensusData = [],
  histogramData = [],
  popularityData = [],
  trendData = [],
  themeData = [],
  positiveCorrelations = [],
  negativeCorrelations = [],
}: AdvancedUserMetricsProps) => {
  const [selectedGenres, setSelectedGenres] = useState<Set<string>>(new Set());

  const toggleGenre = (genre: string) => {
    setSelectedGenres(prev => {
      const next = new Set(prev);
      next.has(genre) ? next.delete(genre) : next.add(genre);
      return next;
    });
  };

  const midpoint = themeData.length > 0 ? themeData.reduce((s, t) => s + t.avgRating, 0) / themeData.length : 3.75;
  const topThemes = [...themeData].filter(t => t.avgRating >= midpoint).sort((a, b) => b.avgRating - a.avgRating).slice(0, 6);
  const bottomThemes = [...themeData].filter(t => t.avgRating < midpoint).sort((a, b) => a.avgRating - b.avgRating).slice(0, 6);

  const topMax = topThemes[0]?.avgRating ?? midpoint;
  const topMin = topThemes[topThemes.length - 1]?.avgRating ?? midpoint;
  const topRange = topMax - topMin || 1;
  const bottomMin = bottomThemes[0]?.avgRating ?? 0;
  const bottomMax = bottomThemes[bottomThemes.length - 1]?.avgRating ?? midpoint;
  const bottomRange = bottomMax - bottomMin || 1;

  const filteredConsensusData = consensusData.filter(d =>
    d.genre && d.genre !== "nan" && d.genre !== "None" && d.publicRating > 0
  );

  const filteredPopularityData = popularityData.filter(d =>
    d.voteCount > 0 && d.userRating > 0 &&
    d.genre && d.genre !== "nan" && d.genre !== "None"
  );

  const visiblePopularityData = useMemo(
    () => selectedGenres.size === 0
      ? filteredPopularityData
      : filteredPopularityData.filter(d => selectedGenres.has(d.genre)),
    [filteredPopularityData, selectedGenres]
  );

  const popularityDomain: [number, number] = filteredPopularityData.length > 0
    ? [
        Math.pow(10, Math.floor(Math.log10(Math.min(...filteredPopularityData.map(d => d.voteCount))))),
        Math.pow(10, Math.ceil(Math.log10(Math.max(...filteredPopularityData.map(d => d.voteCount))))),
      ]
    : [100, 30000];

  const popMidVotes = filteredPopularityData.length > 0
    ? Math.sqrt(popularityDomain[0] * popularityDomain[1])
    : 1000;

  // Top outlier per quadrant to label directly on the chart
  const hiddenGem = [...filteredPopularityData]
    .filter(d => d.voteCount < popMidVotes && d.userRating >= 6)
    .sort((a, b) => (b.userRating - a.userRating) || (a.voteCount - b.voteCount))[0];
  const mainstreamMiss = [...filteredPopularityData]
    .filter(d => d.voteCount >= popMidVotes && d.userRating < 6)
    .sort((a, b) => (a.userRating - b.userRating) || (b.voteCount - a.voteCount))[0];
  const popularFav = [...filteredPopularityData]
    .filter(d => d.voteCount >= popMidVotes && d.userRating >= 6)
    .sort((a, b) => (b.userRating - a.userRating) || (b.voteCount - a.voteCount))[0];


  // Personalized insight
  const topRated = filteredPopularityData.filter(d => d.userRating >= 7);
  const topRatedNiche = topRated.filter(d => d.voteCount < popMidVotes).length;
  const nichePercent = topRated.length > 0 ? Math.round((topRatedNiche / topRated.length) * 100) : null;
  const popularityInsight = (() => {
    if (!nichePercent) return null;
    if (nichePercent >= 60) return `You're a hidden gem hunter — ${nichePercent}% of your top-rated films are niche.`;
    if (nichePercent <= 40) return `You lean mainstream — ${100 - nichePercent}% of your favourites are crowd-pleasers.`;
    return `You're eclectic — equally at home with cult films and blockbusters.`;
  })();

  // Consensus outliers
  const biggestContrarian = [...filteredConsensusData]
    .filter(d => d.userRating > 0 && d.publicRating > 0)
    .sort((a, b) => (b.userRating - b.publicRating) - (a.userRating - a.publicRating))[0];
  const biggestOverrated = [...filteredConsensusData]
    .filter(d => d.userRating > 0 && d.publicRating > 0)
    .sort((a, b) => (a.userRating - a.publicRating) - (b.userRating - b.publicRating))[0];

  const consensusInsight = (() => {
    if (filteredConsensusData.length === 0) return null;
    const gaps = filteredConsensusData.map(d => d.userRating - d.publicRating);
    const avgGap = gaps.reduce((s, v) => s + v, 0) / gaps.length;
    const sign = avgGap >= 0 ? '+' : '';
    if (avgGap > 0.5) return `You're a generous rater — on average ${sign}${avgGap.toFixed(1)} above the Letterboxd crowd.`;
    if (avgGap < -0.5) return `You're a harsh critic — on average ${avgGap.toFixed(1)} below the Letterboxd crowd.`;
    return `Your taste aligns closely with the Letterboxd crowd (avg gap: ${sign}${avgGap.toFixed(1)}).`;
  })();

  const trendInterval = Math.max(1, Math.floor(trendData.length / 8));
  const correlationTreemapData = [
    ...positiveCorrelations.map(c => ({ name: c.tag, size: c.count, avgRating: c.avgRating })),
    ...negativeCorrelations.map(c => ({ name: c.tag, size: c.count, avgRating: c.avgRating })),
  ];
  return (
    <div className="rounded-md text-[#e5e3e2]">
      <div className="flex flex-col h-full bg-[#111111] p-4 rounded-xl">
        {sectionTitle && <h1 className="text-2xl font-bold mb-4 text-left">{sectionTitle}</h1>}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="bg-[#111111] border-0">
            <CardHeader>
              <CardTitle className="text-white text-base">Rating vs. Public Consensus</CardTitle>
              <CardDescription className="text-white/50 text-xs">Points above the line = you loved it more than the public</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={320}>
                <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    type="number" dataKey="publicRating" name="Public Rating"
                    domain={[0, 10]} tickCount={6}
                    tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    label={{ value: "Public Rating", position: "bottom", offset: 0, fill: "rgba(255,255,255,0.3)", fontSize: 11 }}
                  />
                  <YAxis
                    type="number" dataKey="userRating" name="Your Rating"
                    domain={[0, 10]} tickCount={6}
                    tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    label={{ value: "Your Rating", angle: -90, position: "insideLeft", offset: 10, fill: "rgba(255,255,255,0.3)", fontSize: 11 }}
                  />
                  <ReferenceLine
                    segment={[{ x: 0, y: 0 }, { x: 10, y: 10 }]}
                    stroke="rgba(255,255,255,0.15)" strokeDasharray="5 5"
                  />
                  <Tooltip content={<ConsensusTooltip />} cursor={{ strokeDasharray: "3 3", stroke: "rgba(255,255,255,0.1)" }} />
                  <Scatter data={filteredConsensusData} fillOpacity={0.85}>
                    {filteredConsensusData.map((entry, i) => (
                      <Cell key={i} fill={getRatingColor(entry.userRating)} r={3 + Math.abs(entry.userRating - entry.publicRating) * 0.5} />
                    ))}
                  </Scatter>
                  <Customized component={makeOutlierLabels(
                    [biggestContrarian, biggestOverrated].filter(Boolean) as ConsensusItem[], 'publicRating', 'userRating'
                  )} />
                </ScatterChart>
              </ResponsiveContainer>
              {consensusInsight && (
                <p className="text-xs text-white/50 italic mt-2 text-center">{consensusInsight}</p>
              )}
            </CardContent>
          </Card>

          <Card className="bg-[#111111] border-0">
            <CardHeader>
              <CardTitle className="text-white text-base">Your Ratings vs. Community</CardTitle>
              <CardDescription className="text-white/50 text-xs">How your rating distribution compares to a representative community sample</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={320}>
                <AreaChart data={histogramData} margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
                  <defs>
                    <linearGradient id="histUserGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.05} />
                    </linearGradient>
                    <linearGradient id="histCommunityGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="rgba(255,255,255,1)" stopOpacity={0.2} />
                      <stop offset="100%" stopColor="rgba(255,255,255,1)" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis
                    dataKey="rating" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    label={{ value: "Rating", position: "bottom", offset: 0, fill: "rgba(255,255,255,0.3)", fontSize: 11 }}
                  />
                  <YAxis
                    tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    label={{ value: "Movies", angle: -90, position: "insideLeft", offset: 10, fill: "rgba(255,255,255,0.3)", fontSize: 11 }}
                  />
                  <Tooltip content={<HistogramTooltip />} cursor={{ stroke: "rgba(255,255,255,0.1)", strokeDasharray: "3 3" }} />
                  <Area type="monotone" dataKey="community" stroke="rgba(255,255,255,0.3)" strokeWidth={2} fill="url(#histCommunityGradient)" dot={false} />
                  <Area type="monotone" dataKey="user" stroke="#8b5cf6" strokeWidth={2} fill="url(#histUserGradient)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
              <HistogramLegend />
            </CardContent>
          </Card>
        </div>


        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="bg-[#111111] border-0">
            <CardHeader>
              <CardTitle className="text-white text-base">Popularity vs. Your Rating</CardTitle>
              <CardDescription className="text-white/50 text-xs">Do you prefer hidden gems or blockbusters?</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={320}>
                <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    type="number" dataKey="voteCount" name="Vote Count"
                    scale="log" domain={popularityDomain}
                    tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)}
                    label={{ value: "Popularity (votes, log scale)", position: "bottom", offset: 0, fill: "rgba(255,255,255,0.3)", fontSize: 11 }}
                  />
                  <YAxis
                    type="number" dataKey="userRating" name="Your Rating"
                    domain={[0, 10]} tickCount={6}
                    tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    label={{ value: "Your Rating", angle: -90, position: "insideLeft", offset: 10, fill: "rgba(255,255,255,0.3)", fontSize: 11 }}
                  />
                  <ReferenceLine y={6} stroke="rgba(255,255,255,0.1)" strokeDasharray="5 5" />
                  <ReferenceLine x={Math.sqrt(popularityDomain[0] * popularityDomain[1])} stroke="rgba(255,255,255,0.1)" strokeDasharray="5 5" />
                  <Tooltip content={<PopularityTooltip />} cursor={{ strokeDasharray: "3 3", stroke: "rgba(255,255,255,0.1)" }} />
                  <Scatter data={visiblePopularityData} fillOpacity={0.85} isAnimationActive={false}>
                    {visiblePopularityData.map((entry, i) => (
                      <Cell key={i} fill={getGenreColor(entry.genre)} r={3 + Math.abs(entry.userRating - 5) * 0.6} />
                    ))}
                  </Scatter>
                  <Customized component={QuadrantLabels} />
                  <Customized component={makeOutlierLabels(
                    (selectedGenres.size === 0 ? [hiddenGem, mainstreamMiss, popularFav].filter(Boolean) : []) as PopularityItem[]
                  )} />
                </ScatterChart>
              </ResponsiveContainer>
              {popularityInsight && (
                <p className="text-xs text-white/50 italic mt-2 text-center">{popularityInsight}</p>
              )}
              <ScatterLegend data={filteredPopularityData} selectedGenres={selectedGenres} onToggle={toggleGenre} />
            </CardContent>
          </Card>

          <Card className="bg-[#111111] border-0">
            <CardHeader>
              <CardTitle className="text-white text-base">Rating Trend Over Time</CardTitle>
              <CardDescription className="text-white/50 text-xs">30-day film rolling average of your ratings — are you getting more critical?</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={360}>
                <AreaChart data={trendData} margin={{ top: 10, right: 10, bottom: 20, left: 0 }}>
                  <defs>
                    <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#f97316" stopOpacity={0.75} />
                      <stop offset="100%" stopColor="#f97316" stopOpacity={0.05} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    interval={trendInterval}
                    tickFormatter={formatDate}
                    label={{ value: "Date", position: "bottom", offset: 0, fill: "rgba(255,255,255,0.3)", fontSize: 11 }}
                  />
                  <YAxis
                    domain={[5, 9]} tickCount={5}
                    tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 11 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    label={{ value: "Rating", angle: -90, position: "insideLeft", offset: 10, fill: "rgba(255,255,255,0.3)", fontSize: 11 }}
                  />
                  <Tooltip content={<TrendTooltip />} />
                  <Area type="monotone" dataKey="rollingAvg" stroke="#f97316" strokeWidth={2} fill="url(#trendGradient)" />
                  <Line type="monotone" dataKey="actual" stroke="rgba(255,255,255,0.2)" strokeWidth={1} dot={{ fill: "rgba(255,255,255,0.3)", r: 2 }} />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        <Card className="bg-[#111111] border-0">
          <CardHeader>
            <CardTitle className="text-white text-base">Nanogenres Explorer</CardTitle>
            <CardDescription className="text-white/50 text-xs">
              Nanogenre tags most correlated with your high and low ratings. Size = movies watched. Color = rating.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={360}>
              <Treemap
                data={correlationTreemapData}
                dataKey="size"
                stroke="none"
                content={<CorrelationTreemapContent />}
                animationDuration={300}
              >
                <Tooltip content={<TreemapTooltip />} />
              </Treemap>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="bg-[#111111] border-0 mb-6">
          <CardHeader>
            <CardTitle className="text-white text-base">Your Perfect Movie Recipe</CardTitle>
            <CardDescription className="text-white/50 text-xs">
              Themes ranked by your average rating
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-emerald-400/80 uppercase tracking-wider font-semibold mb-3">Themes You Love</p>
            <div className="space-y-2 mb-6">
              {topThemes.map((item) => (
                <div key={item.name} className="flex items-center bg-white/[0.02] rounded-lg px-3 py-2">
                  <span className="text-sm text-white/80 flex-1 min-w-0 truncate">{item.name}</span>
                  <div className="flex items-center gap-3 ml-4 shrink-0">
                    <CorrelationBar value={Math.max(0.15, (item.avgRating - topMin) / topRange)} positive />
                    <span className="text-xs text-emerald-400 font-mono w-8 text-right shrink-0">{item.avgRating}</span>
                    <span className="text-xs text-white/30 w-20 text-right shrink-0 whitespace-nowrap">{item.size} movies</span>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-red-400/80 uppercase tracking-wider font-semibold mb-3">Themes You Avoid</p>
            <div className="space-y-2">
              {[...bottomThemes].reverse().map((item) => (
                <div key={item.name} className="flex items-center bg-white/[0.02] rounded-lg px-3 py-2">
                  <span className="text-sm text-white/80 flex-1 min-w-0 truncate">{item.name}</span>
                  <div className="flex items-center gap-3 ml-4 shrink-0">
                    <CorrelationBar value={Math.max(0.15, (bottomMax - item.avgRating) / bottomRange)} positive={false} />
                    <span className="text-xs text-red-400 font-mono w-8 text-right shrink-0">{item.avgRating}</span>
                    <span className="text-xs text-white/30 w-20 text-right shrink-0 whitespace-nowrap">{item.size} movies</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
