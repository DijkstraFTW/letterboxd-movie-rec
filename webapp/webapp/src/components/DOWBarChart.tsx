import {BarChart, Bar, Tooltip} from 'recharts';

// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-expect-error
const DOWBarChart = ({data, y_field}) => {

    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-expect-error
    const CustomTooltip = ({active, payload, label}) => {
        if (active && payload && payload.length) {
            label = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][label]
            return (
                <div className="inline-block bg-gray-800 p-1.5 rounded-sm">
                    <span className="flex flex-row items-center justify-center text-white font-bold">
                        {`${payload[0].value.toLocaleString(0)} (avg)`}</span>
                    <span className="flex flex-row items-center text-gray-500">{`watched on ${label}`}</span>
                </div>
            );
        }
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
            <Bar dataKey={y_field} fill="#15ecce" radius={[8, 8, 2, 2]}/>
        </BarChart>
    );
};

export default DOWBarChart;
