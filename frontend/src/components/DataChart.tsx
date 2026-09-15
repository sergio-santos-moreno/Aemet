import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MeasurementOut } from "../types";

interface Props {
  data: MeasurementOut[];
}

const hasField = (data: MeasurementOut[], field: keyof MeasurementOut) =>
  data.some((row) => row[field] !== null);

export default function DataChart({ data }: Props) {
  const showTemp = hasField(data, "temperature_c");
  const showPres = hasField(data, "pressure_hpa");
  const showSpeed = hasField(data, "speed_ms");

  return (
    <div className="panel">
      <div className="panel-title">Chart</div>
      <div className="chart-wrap" style={{ height: 320 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#223447" strokeDasharray="2 4" />
            <XAxis
              dataKey="datetime"
              tick={{ fill: "#8ea3b3", fontSize: 11, fontFamily: "IBM Plex Mono, monospace" }}
              tickFormatter={(v: string) => v.slice(5, 16).replace("T", " ")}
              minTickGap={40}
              stroke="#33495e"
            />
            <YAxis
              tick={{ fill: "#8ea3b3", fontSize: 11, fontFamily: "IBM Plex Mono, monospace" }}
              stroke="#33495e"
            />
            <Tooltip
              contentStyle={{
                background: "#101f2b",
                border: "1px solid #33495e",
                fontFamily: "IBM Plex Mono, monospace",
                fontSize: 12,
              }}
              labelStyle={{ color: "#8ea3b3" }}
            />
            {showTemp && (
              <Line type="monotone" dataKey="temperature_c" name="Temp (°C)" stroke="#5fd4e8" dot={false} strokeWidth={2} />
            )}
            {showPres && (
              <Line type="monotone" dataKey="pressure_hpa" name="Pressure (hPa)" stroke="#e8a23d" dot={false} strokeWidth={2} />
            )}
            {showSpeed && (
              <Line type="monotone" dataKey="speed_ms" name="Speed (m/s)" stroke="#8fd66f" dot={false} strokeWidth={2} />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
