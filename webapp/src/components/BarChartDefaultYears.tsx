"use client"

import { Bar, BarChart, XAxis, Cell } from "recharts"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../shadcn/components/ui/card.tsx"
import {
  ChartContainer,
  ChartTooltip,
} from "../../shadcn/components/ui/chart.tsx"

type BarChartDefaultProps = {
  title: string
  description?: string
  data: { [key: string]: any }[]
  config: Record<string, any>
  dataKey?: string
  xKey?: string
}

function BarChartDefaultYears({
  title,
  description,
  data,
  config,
  dataKey = "desktop",
  xKey = "year",
}: BarChartDefaultProps) {
  const years = data.map((d) => d[xKey])
  const minYear = Math.min(...years)
  const maxYear = Math.max(...years)

  const fullData = []
  for (let y = minYear; y <= maxYear; y++) {
    const entry = data.find((d) => d[xKey] === y)
    fullData.push(entry ?? { [xKey]: y, [dataKey]: 0 })
  }

  const maxValue = Math.max(...fullData.map((d) => d[dataKey]))

  const baseColor = "#f97316"

  const hexToRgb = (hex: string) => {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : { r: 0, g: 0, b: 0 }
  }

  const baseRgb = hexToRgb(baseColor)

  return (
  <Card className="bg-transparent text-card-white flex flex-col gap-6 rounded-xl border-0 py-6">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <ChartContainer config={config}>
          <BarChart accessibilityLayer data={fullData}>
            <XAxis
              dataKey={xKey}
              tickLine={false}
              tickMargin={10}
              axisLine={false}
            />
            <ChartTooltip
              cursor={false}
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const yearValue = payload[0].payload[xKey]
                  const ratingValue = payload[0].value

                  return (
                    <div className="rounded-lg border bg-background p-2 shadow-sm">
                      <div className="flex flex-col gap-1">
                        <span className="text-sm text-muted-foreground">
                          {ratingValue === 0 ? (
                            <>You watched <span className="font-bold">0</span> movies from <span className="font-bold">{yearValue}</span></>
                          ) : (
                            <>Average rating for <span className="font-bold">{yearValue}</span> is <span className="font-bold">{Number(ratingValue).toFixed(2)}</span></>
                          )}
                        </span>
                      </div>
                    </div>
                  )
                }
                return null
              }}
            />
            <Bar dataKey={dataKey} radius={2}>
              {fullData.map((entry, index) => {
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
    </Card>
  )
}

export default BarChartDefaultYears
