import {BarChart, Bar, Tooltip} from 'recharts';
import {StarFilledIcon} from "@radix-ui/react-icons";

// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-expect-error
const ARPYBarChart = ({data, x_field, y_field}) => {

    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-expect-error
    const CustomTooltip = ({active, payload, label}) => {
        if (active && payload && payload.length) {
            label = data[label][x_field]
            return (
                <div className="inline-block bg-gray-800 p-1.5 rounded-sm">
                    <div className="flex flex-row items-center justify-center space-x-1.5"><span
                        className="flex flex-row items-center justify-center text-white font-bold">
                        {`${payload[0].value.toLocaleString(0)}`}</span> <StarFilledIcon/> <span>(avg)</span></div>
                    <span className="flex flex-row items-center text-gray-500">{`released in ${label}`}</span>
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
            <Tooltip cursor={{fill: 'transparent'}} content={<CustomTooltip active="false" payload={[]} label={""}/>}/>
            <Bar dataKey={y_field} fill="#15ecce" radius={[8, 8, 2, 2]}/>
        </BarChart>
    );
};

export default ARPYBarChart;
