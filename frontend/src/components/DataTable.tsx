import type { MeasurementOut } from "../types";

interface Props {
  data: MeasurementOut[];
}

export default function DataTable({ data }: Props) {
  return (
    <div className="panel">
      <div className="panel-title">Readings ({data.length})</div>
      <div style={{ maxHeight: 420, overflowY: "auto" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Datetime (Europe/Madrid)</th>
              <th>Temperature (°C)</th>
              <th>Pressure (hPa)</th>
              <th>Speed (m/s)</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.datetime}>
                <td>{row.datetime}</td>
                <td>{row.temperature_c ?? "—"}</td>
                <td>{row.pressure_hpa ?? "—"}</td>
                <td>{row.speed_ms ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
