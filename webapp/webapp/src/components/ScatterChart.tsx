import {Scatter, Tooltip, XAxis, YAxis} from "recharts";

// eslint-disable-next-line @typescript-eslint/ban-ts-comment
const ScatterChart = () => {

    const data = [
        { x: 100, y: 200, z: 200 },
        { x: 120, y: 100, z: 260 },
        { x: 170, y: 300, z: 400 },
        { x: 140, y: 250, z: 280 },
        { x: 150, y: 400, z: 500 },
        { x: 110, y: 280, z: 200 },
    ];

    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-expect-error
    return ( <ScatterChart
            width={800}
            height={400}
            margin={{
                top: 20, right: 20, bottom: 20, left: 20,
            }}
        >
            <XAxis type="number" dataKey="year_released" name="Year Released" />
            <YAxis type="number" dataKey="average_rating" name="Average Rating" />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
            <Scatter name="Movies" data={data} fill="#8884d8" />
        </ScatterChart>
    );

}

export default ScatterChart;