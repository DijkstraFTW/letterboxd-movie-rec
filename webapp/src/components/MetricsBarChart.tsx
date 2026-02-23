import {BarChart, Bar, Tooltip} from 'recharts';

interface MetricsBarChartProps {
    data: Record<string, unknown>[];
    x_field: string;
    y_field: string;
}

interface TooltipPayload {
    value: number;
}

interface CustomTooltipProps {
    active?: boolean;
    payload?: TooltipPayload[];
    label?: number;
}

const MetricsBarChart = ({data, x_field, y_field}: MetricsBarChartProps) => {

    const colors = ['#3cbbf4', '#15ecce', '#ea182e']

    const CustomTooltip = ({active, payload, label}: CustomTooltipProps) => {
        if (active && payload && payload.length && label !== undefined) {
            let displayLabel: unknown;
            if (x_field === 'day_of_week') {
                displayLabel = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][label];
                return (
                    <div className="inline-block text-white">
                        <p className="flex flex-row items-center">{`${displayLabel}`}
                            {` (${payload[0].value.toLocaleString()})`}</p>
                    </div>
                );
            } else {
                displayLabel = data[label][x_field];
                return (
                    <div className="inline-block text-white">
                        <p className="flex flex-row items-center">{`${displayLabel}`}
                            {` (${payload[0].value.toLocaleString()})`}</p>
                    </div>
                );
            }

        }

        return null;
    };


    return (
        <BarChart width={500} height={200}
                  barCategoryGap={2}
                  data={data}
                  margin={{
                      top: 5, right: 30, left: 20, bottom: 5,
                  }}
        >
            <Tooltip cursor={{fill: 'transparent'}} content={<CustomTooltip active={false} payload={[]} label={""}/>}/>
            <Bar dataKey={y_field} fill={colors[1]} radius={[8, 8, 2, 2]}/>
        </BarChart>
    );
};

export default MetricsBarChart;
