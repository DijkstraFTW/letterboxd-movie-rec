import {AreaChart, Area, Tooltip, ResponsiveContainer} from 'recharts'
import {formatNumber} from "./MovieCard.tsx";
import {StarFilledIcon} from "@radix-ui/react-icons";

// @ts-ignore
export default function RatingsLineChart({ data }) {

    const filteredHistogram = Object.keys(data)
        .filter(key => key !== 'fans' && key !== 'total' && key !== 'lb_rating')
        .reduce((obj, key) => {
            // @ts-ignore
            obj[key] = data[key];
            return obj;
        }, {});
    const plotHistogram = Object.entries(filteredHistogram).map(([key, value]) => ({
        x: key,
        y: value
    }));

    // @ts-ignore
    const CustomTooltip = ({ active, payload, label }) => {
        if (active && payload && payload.length) {
            return (
                <div className="inline-block text-gray-500">
                    <p className="flex flex-row items-center">{`${label + 1}`}
                        <StarFilledIcon className="ml-0.5 mr-1.5" />
                        {` (${formatNumber(payload[0].value)})`}</p>
                </div>
            );
        }

        return null;
    };


    return (
        <ResponsiveContainer width="100%" className="w-80 p-4">
            <AreaChart data={plotHistogram}>
                <defs>
                    <linearGradient id="colorY" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#8884d8" stopOpacity={0.8}/>
                        <stop offset="95%" stopColor="#8884d8" stopOpacity={0}/>
                    </linearGradient>
                </defs>
                <Tooltip content={<CustomTooltip active={false} payload={[]} label={""}  />} cursor={{ fill: "transparent" }} />
                <Area type="monotone" dataKey="y" stroke="#8884d8" fill="url(#colorY)"/>
            </AreaChart>
        </ResponsiveContainer>
    );
}
