"use client"

import { Bar, BarChart, XAxis, YAxis, Cell } from "recharts"

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

function BarChartDefault({
  title,
  description,
  data,
  config,
  dataKey = "desktop",
  xKey = "month",
}: BarChartDefaultProps) {
  const maxValue = Math.max(...data.map((d) => d[dataKey]))
  const minValue = Math.min(...data.map((d) => d[dataKey]))
  const range = maxValue - minValue || 1

  const baseColor = "#10b981"

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
          <BarChart accessibilityLayer data={data}>
            <YAxis hide domain={[Math.max(0, minValue - range * 0.5), maxValue + range * 0.1]} />
            <XAxis
              dataKey={xKey}
              tickLine={false}
              tickMargin={10}
              axisLine={false}
              tickFormatter={(value) => value.slice(0, 3)}
            />
            <ChartTooltip
              cursor={false}
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const entry = payload[0].payload
                  const value = Number(payload[0].value ?? 0)
                  const label = entry[xKey]

                  return (
                    <div className="rounded-lg border bg-background p-3 shadow-sm">
                      <div className="flex flex-col gap-1">
                        <span className="text-sm text-muted-foreground">
                          You watch around <span className="font-bold">{value.toFixed(2)}</span> movies on <span className="font-bold">{label}s</span>.
                        </span>
                      </div>
                    </div>
                  )
                }
                return null
              }}
            />
            <Bar dataKey={dataKey} radius={8}>
              {data.map((entry, index) => {
                const intensity = (entry[dataKey] - minValue) / range
                const dimRgb = { r: Math.round(baseRgb.r * 0.25), g: Math.round(baseRgb.g * 0.25), b: Math.round(baseRgb.b * 0.25) }
                const r = Math.round(dimRgb.r + (baseRgb.r - dimRgb.r) * intensity)
                const g = Math.round(dimRgb.g + (baseRgb.g - dimRgb.g) * intensity)
                const b = Math.round(dimRgb.b + (baseRgb.b - dimRgb.b) * intensity)
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

export default BarChartDefault
