import { AreaChart, Area, Tooltip, ResponsiveContainer } from "recharts"
import { formatNumber } from "./MovieCard.tsx"
import { StarFilledIcon } from "@radix-ui/react-icons"

interface RatingsLineChartProps {
  data: { [key: string]: any } | null
}

export default function RatingsLineChart({ data }: RatingsLineChartProps) {
  if (!data) return null

  const filteredHistogram = Object.keys(data)
    .filter((key) => key !== "fans" && key !== "total" && key !== "lb_rating")
    .reduce((obj: { [key: string]: any }, key) => {
      obj[key] = data[key]
      return obj
    }, {})

  const plotHistogram = Object.entries(filteredHistogram).map(([key, value]) => ({
    x: Number(key),
    y: value
  }))

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="inline-block text-white/80 text-xs flex items-center gap-1">
          {label} <StarFilledIcon className="w-3 h-3" /> ({formatNumber(payload[0].value)})
        </div>
      )
    }
    return null
  }

  return (
    <ResponsiveContainer width="100%" height={50}>
      <AreaChart data={plotHistogram} margin={{ top: 6, bottom: 6, left: 0, right: 0 }}>
        <defs>
          <linearGradient id="colorY" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.9} />
            <stop offset="50%" stopColor="#3b82f6" stopOpacity={0.4} />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "transparent" }} />
        <Area
          type="monotone"
          dataKey="y"
          stroke="#3b82f6"
          strokeWidth={2}
          fill="url(#colorY)"
          animationDuration={800}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
