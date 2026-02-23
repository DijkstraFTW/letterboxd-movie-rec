"use client"

import { TrendingUp } from "lucide-react"
import { Bar, BarChart, XAxis, YAxis, Cell } from "recharts"

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

type ChartBarMixedDecadesProps = {
  title: string
  description?: string
  data: { [key: string]: any }[]
  config: Record<string, any>
  dataKey?: string
  yKey?: string
  legendKey?: boolean
  baseColor?: string
}

function ChartBarMixedDecades({
  title,
  description,
  data,
  config,
  dataKey = "visitors",
  yKey = "browser",
  legendKey = true,
  baseColor = "#8b5cf6",
}: ChartBarMixedDecadesProps) {
  const maxValue = Math.max(...data.map((d) => d[dataKey]))
  const total = data.reduce((acc, d) => acc + d[dataKey], 0)

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
      comparisonMessage = `the ${topEntry[yKey]}s has more than double the share of the ${secondEntry[yKey]}s`
    } else if (ratio >= 1.5) {
      comparisonMessage = `the ${topEntry[yKey]}s has ~50% more than the ${secondEntry[yKey]}s`
    } else {
      comparisonMessage = `the ${topEntry[yKey]}s narrowly lead over the ${secondEntry[yKey]}s`
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
              tickFormatter={(value) => (config[value]?.label ?? value) + 's'}
            />
            <XAxis dataKey={dataKey} type="number" hide />
            <ChartTooltip
              cursor={false}
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const entry = payload[0].payload
                  const value = Number(payload[0].value ?? 0)
                  const label = config[entry[yKey]]?.label || entry[yKey]

                  return (
                    <div className="rounded-lg border bg-background p-3 shadow-sm">
                      <div className="flex flex-col gap-1">
                        <span className="text-sm text-muted-foreground">
                          the <span className="font-bold">{label + 's'}</span> average rating is <span className="font-bold">{value.toFixed(2)}</span>
                        </span>
                      </div>
                    </div>
                  )
                }
                return null
              }}
            />
            <Bar dataKey={dataKey} layout="vertical" radius={5}>
              {data.map((entry, index) => {
                if (entry[dataKey] === 0) {
                  return (
                    <Cell
                      key={`cell-${index}`}
                      fill="#e5e5e5"
                    />
                  )
                }
                const intensity = entry[dataKey] / maxValue
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
            </Bar>
          </BarChart>
        </ChartContainer>
      </CardContent>
      {legendKey && (
      <CardFooter className="flex-col items-start gap-2 text-sm">
        <div className="flex gap-2 leading-none font-medium">
          the {topEntry[yKey]}s lead with {topEntry[dataKey].toFixed(2)} ({topPercent}%)
          <TrendingUp className="h-4 w-4" />
        </div>
        <div className="text-muted-foreground leading-none">{comparisonMessage}</div>
      </CardFooter>
      )}
    </Card>
  )
}

export default ChartBarMixedDecades
