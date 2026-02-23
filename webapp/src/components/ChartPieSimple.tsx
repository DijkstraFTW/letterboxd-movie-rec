import { Pie, PieChart, Cell } from "recharts"
import { TrendingUp } from "lucide-react"

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

type ChartPieSimpleProps = {
  title: string
  description?: string
  data: any[]
  config: Record<string, any>
  dataKey?: string
  nameKey?: string
  legendKey?: boolean
}

function ChartPieSimple({
  title,
  description,
  data,
  config,
  dataKey = "visitors",
  nameKey = "browser",
  legendKey = true,
}: ChartPieSimpleProps) {
  const total = data.reduce((acc, d) => acc + d[dataKey], 0)

  // find top two categories
  const sorted = [...data].sort((a, b) => b[dataKey] - a[dataKey])
  const topEntry = sorted[0]
  const secondEntry = sorted[1]

  // calculate percentage
  const topPercent = Math.round((topEntry[dataKey] / total) * 100)
  let comparisonMessage = ""

  if (secondEntry) {
    const ratio = topEntry[dataKey] / secondEntry[dataKey]
    if (ratio >= 2) {
      comparisonMessage = `${topEntry[nameKey]} has more than double the share of ${secondEntry[nameKey]}`
    } else if (ratio >= 1.5) {
      comparisonMessage = `${topEntry[nameKey]} has ~50% more than ${secondEntry[nameKey]}`
    } else {
      comparisonMessage = `${topEntry[nameKey]} narrowly leads over ${secondEntry[nameKey]}`
    }
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

                  const rawLabel = entry[nameKey]
                  const formattedLabel = config[rawLabel]?.label ||
                    rawLabel
                      .replace(/_/g, ' ')
                      .split(' ')
                      .map((word: string) => word.charAt(0).toUpperCase() + word.slice(1))
                      .join(' ')

                  const percent = Math.round((value / total) * 100)

                  return (
                    <div className="rounded-lg border bg-background p-3 shadow-sm">
                      <div className="flex flex-col gap-1">
                        <span className="text-sm text-muted-foreground">
                          <span className="font-bold">{formattedLabel}</span> accounts for <span className="font-bold">{value}</span> ({percent}%) of your activity.
                        </span>
                      </div>
                    </div>
                  )
                }
                return null
              }}
            />
            <Pie data={data} dataKey={dataKey} nameKey={nameKey}>
              {data.map((_, index) => {
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
      {legendKey && ( 
        <CardFooter className="flex-col gap-2 text-sm text-center">
        <div className="flex items-center justify-center gap-2 leading-none font-medium">
          {topEntry[nameKey]} leads with {topEntry[dataKey]} ({topPercent}%)
          <TrendingUp className="h-4 w-4" />
        </div>
        <div className="text-muted-foreground leading-none">
          {comparisonMessage}
        </div>
      </CardFooter>
      )}
    </Card>
  )
}

export default ChartPieSimple
