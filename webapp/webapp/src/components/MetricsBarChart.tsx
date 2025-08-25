import {BarChart, Bar, Tooltip} from 'recharts';

// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-expect-error
const MetricsBarChart = ({data, x_field, y_field}) => {

    const colors = ['#3cbbf4', '#15ecce', '#ea182e']

    // @ts-ignore
    const CustomTooltip = ({active, payload, label}) => {
        if (active && payload && payload.length) {
            if (x_field == 'day_of_week') {
                label = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][label]
                return (
                    <div className="inline-block text-white">
                        <p className="flex flex-row items-center">{`${label}`}
                            {` (${payload[0].value.toLocaleString(1)})`}</p>
                    </div>
                );
            } else {
                label = data[label][x_field]
                return (
                    <div className="inline-block text-white">
                        <p className="flex flex-row items-center">{`${label}`}
                            {` (${payload[0].value.toLocaleString(1)})`}</p>
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
