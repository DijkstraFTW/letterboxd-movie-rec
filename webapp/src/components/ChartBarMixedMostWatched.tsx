"use client"

import { TrendingUp } from "lucide-react"
import { Bar, BarChart, XAxis, YAxis, Cell, LabelList } from "recharts"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter
} from "../../shadcn/components/ui/card.tsx"
import {
  ChartContainer,
  ChartTooltip,
} from "../../shadcn/components/ui/chart.tsx"

type ChartBarMixedMostWatchedProps = {
  title: string
  description?: string
  data: { [key: string]: any }[]
  config: Record<string, any>
  dataKey?: string
  yKey?: string
  legendKey?: boolean
  imageKey: string
}

function ChartBarMixedMostWatched({
  title,
  description,
  data,
  config,
  dataKey = "visitors",
  yKey = "browser",
  legendKey = true,
  imageKey,
}: ChartBarMixedMostWatchedProps) {
  const baseColor = "#3b82f6" // Blue color
  const maxValue = Math.max(...data.map((d) => d[dataKey]))
  const total = data.reduce((acc, d) => acc + d[dataKey], 0)

  // Parse hex color to RGB
  const hexToRgb = (hex: string) => {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : { r: 0, g: 0, b: 0 }
  }

  const baseRgb = hexToRgb(baseColor)

  const sorted = [...data].sort((a, b) => b[dataKey] - a[dataKey])
  const topEntry = sorted[0]
  const secondEntry = sorted[1]

  const topPercent = Math.round((topEntry[dataKey] / total) * 100)
  let comparisonMessage = ""

  if (secondEntry) {
    const ratio = topEntry[dataKey] / secondEntry[dataKey]
    if (ratio >= 2) {
      comparisonMessage = `${topEntry[yKey]} has more than double the share of ${secondEntry[yKey]}`
    } else if (ratio >= 1.5) {
      comparisonMessage = `${topEntry[yKey]} has ~50% more than ${secondEntry[yKey]}`
    } else {
      comparisonMessage = `${topEntry[yKey]} narrowly leads over ${secondEntry[yKey]}`
    }
  }

  return (
    <Card className="bg-red text-card-white flex flex-col gap-6 rounded-xl border-0 py-6">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <ChartContainer config={config}>
          <BarChart
            accessibilityLayer
            data={data}
            layout="vertical"
            margin={{ left: 0 }}
          >
            <YAxis
              dataKey={yKey}
              type="category"
              tickLine={false}
              tickMargin={10}
              axisLine={false}
              tickFormatter={(value) => config[value]?.label || value}
              width={0}
            />
            <XAxis dataKey={dataKey} type="number" hide />
            <ChartTooltip
              cursor={false}
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const entry = payload[0].payload
                  const value = payload[0].value
                  const label = config[entry[yKey]]?.label || entry[yKey]
                  const imageUrl = entry[imageKey] || null

                  return (
                    <div className="rounded-lg border bg-background p-3 shadow-sm max-w-xs">
                      <div className="flex items-start gap-3">
                        {imageUrl && (
                          <div className="flex-shrink-0">
                            <img
                              src={imageUrl}
                              alt={label}
                              className="w-20 h-28 object-cover rounded shadow-md bg-muted"
                              loading="lazy"
                              onError={(e) => {
                                const target = e.currentTarget;
                                target.parentElement!.style.display = 'none';
                              }}
                            />
                          </div>
                        )}
                        <div className="flex flex-col gap-1 min-w-0">
                          <span className="text-sm text-muted-foreground">
                            You watched <span className="font-bold">{label}</span> a total of <span className="font-bold">{value}</span> times.
                          </span>
                        </div>
                      </div>
                    </div>
                  )
                }
                return null
              }}
            />
            <Bar dataKey={dataKey} layout="vertical" radius={5}>
              {data.map((entry, index) => {
                // For zero values, use a very light gray
                if (entry[dataKey] === 0) {
                  return (
                    <Cell
                      key={`cell-${index}`}
                      fill="#e5e5e5"
                    />
                  )
                }
                const intensity = entry[dataKey] / maxValue
                // Create gradient from lighter to darker based on intensity
                const r = Math.round(baseRgb.r + (255 - baseRgb.r) * (1 - intensity))
                const g = Math.round(baseRgb.g + (255 - baseRgb.g) * (1 - intensity))
                const b = Math.round(baseRgb.b + (255 - baseRgb.b) * (1 - intensity))
                return (
                  <Cell
                    key={`cell-${index}`}
                    fill={`rgb(${r}, ${g}, ${b})`}
                  />
                )
              })}
              <LabelList
                dataKey={yKey}
                position="insideLeft"
                content={(props: any) => {
                  const { x, y, width, height, value } = props
                  const label: string = config[value]?.label || value || ''
                  const charWidth = 7
                  const available = Math.floor((width - 10) / charWidth)
                  const truncated = label.length > available
                    ? label.slice(0, Math.max(0, available - 1)) + '…'
                    : label
                  if (available <= 0) return null
                  return (
                    <text
                      x={x + 10}
                      y={y + height / 2}
                      dominantBaseline="middle"
                      fill="white"
                      fontSize={12}
                      fontWeight={500}
                    >
                      {truncated}
                    </text>
                  )
                }}
              />
            </Bar>
          </BarChart>
        </ChartContainer>
      </CardContent>
      {legendKey && (
      <CardFooter className="flex-col items-start gap-2 text-sm">
        <div className="flex gap-2 leading-none font-medium">
          {topEntry[yKey]} leads with {topEntry[dataKey]} ({topPercent}%)
          <TrendingUp className="h-4 w-4" />
        </div>
        <div className="text-muted-foreground leading-none">{comparisonMessage}</div>
      </CardFooter>
      )}
    </Card>
  )
}

export default ChartBarMixedMostWatched
