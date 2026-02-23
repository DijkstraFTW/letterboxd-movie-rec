import { useState } from "react"
import { Pie, PieChart, Cell } from "recharts"
import { TrendingUp } from "lucide-react"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter,
} from "../../shadcn/components/ui/card.tsx"

import {
  ChartContainer,
  ChartTooltip,
} from "../../shadcn/components/ui/chart.tsx"

import {
  Button,
} from "../../shadcn/components/ui/button.tsx"

type ChartPieSimpleProps = {
  title: string
  description?: string
  data: any[]
  config: Record<string, any>
  dataKey?: string
  nameKey?: string
  altData?: any[]
  legendKey?: boolean
}

function ChartPieSimpleToggable({
  title,
  description,
  data,
  config,
  dataKey = "visitors",
  nameKey = "browser",
  altData,
  legendKey = true,
}: ChartPieSimpleProps) {
  const [useAltData, setUseAltData] = useState(false)
  const activeData = useAltData && altData ? altData : data

  const total = activeData.reduce((acc, d) => acc + d[dataKey], 0)

  const sorted = [...activeData].sort((a, b) => b[dataKey] - a[dataKey])
  const topEntry = sorted[0]
  const secondEntry = sorted[1]

  const topPercent = Math.round((topEntry[dataKey] / total) * 100)
  let comparisonMessage = ""
  if (secondEntry) {
    const ratio = topEntry[dataKey] / secondEntry[dataKey]
    if (ratio >= 2) comparisonMessage = `${topEntry[nameKey]} has more than double the share of ${secondEntry[nameKey]}`
    else if (ratio >= 1.5) comparisonMessage = `${topEntry[nameKey]} has ~50% more than ${secondEntry[nameKey]}`
    else comparisonMessage = `${topEntry[nameKey]} narrowly leads over ${secondEntry[nameKey]}`
  }

  return (
        <Card className="bg-transparent text-card-white flex flex-col gap-6 rounded-xl border-0 py-6">
      <CardHeader className="items-center pb-0">
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="flex-1 pb-0">
        <ChartContainer config={config} className="mx-auto aspect-square max-h-[250px]">
          <PieChart>
            <ChartTooltip
              cursor={false}
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const entry = payload[0].payload
                  const value = Number(payload[0].value ?? 0)
                  const label = config[entry[nameKey]]?.label || entry[nameKey]
                  const percent = Math.round((value / total) * 100)

                  return (
                    <div className="rounded-lg border bg-background p-3 shadow-sm">
                      <div className="flex flex-col gap-1">
                        <span className="text-sm text-muted-foreground">
                          <span className="font-bold">{label}</span> accounts for <span className="font-bold">{value}</span> ({percent}%) of your activity.
                        </span>
                      </div>
                    </div>
                  )
                }
                return null
              }}
            />
            <Pie data={activeData} dataKey={dataKey} nameKey={nameKey}>
              {activeData.map((_, index) => {
                // Use vibrant, distinct colors for each slice
                const colors = [
                  '#ef4444', // red
                  '#3b82f6', // blue
                  '#10b981', // green
                  '#f59e0b', // amber
                  '#8b5cf6', // violet
                  '#ec4899', // pink
                  '#14b8a6', // teal
                  '#f97316', // orange
                  '#06b6d4', // cyan
                  '#84cc16', // lime
                ]
                return <Cell key={index} fill={colors[index % colors.length]} />
              })}
            </Pie>
          </PieChart>
        </ChartContainer>
      </CardContent>
      <CardFooter className="flex-col gap-2 text-sm text-center">
        {legendKey && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-center gap-2 leading-none font-medium">
              {topEntry[nameKey]} leads with {topEntry[dataKey]} ({topPercent}%)
              <TrendingUp className="h-4 w-4" />
            </div>
            <div className="text-muted-foreground leading-none">{comparisonMessage}</div>
          </div>
        )}
        
        {altData && (
          <Button
            size="sm"
            variant="outline"
            className="mt-2 inline-flex items-center justify-center whitespace-nowrap transition-colors focus-visible:outline-none cursor-pointer disabled:pointer-events-none disabled:opacity-50 border px-3 py-1.5 bg-white/5 hover:bg-white text-white/80 border-white/5 text-sm h-8 font-medium"
            onClick={() => setUseAltData(!useAltData)}
          >
            {useAltData ? "Show Rating" : "Show Watch Count"}
          </Button>
        )}
      </CardFooter>
    </Card>
  )
}

export default ChartPieSimpleToggable
