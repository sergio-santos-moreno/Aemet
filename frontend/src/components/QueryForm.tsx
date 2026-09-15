import { useState } from "react";
import { AGGREGATIONS, DATA_TYPES, STATIONS } from "../types";
import type { Aggregation, DataType, QueryParams, Station } from "../types";

interface Props {
  onSubmit: (params: QueryParams) => void;
  loading: boolean;
}

function defaultDatetimeLocal(offsetHours: number): string {
  const d = new Date(Date.now() - offsetHours * 3600 * 1000);
  return d.toISOString().slice(0, 19);
}
/**
 * Browsers omit the seconds portion of a <input type="datetime-local">
 * value when it's exactly ":00" (a documented quirk), e.g. "2026-09-13T00:00"
 * instead of "2026-09-13T00:00:00". The backend requires the full
 * YYYY-MM-DDTHH:MM:SS format, so we pad it back in here.
 */
function withSeconds(value: string): string {
  return value.length === 16 ? `${value}:00` : value;
}

export default function QueryForm({ onSubmit, loading }: Props) {
  const [station, setStation] = useState<Station>(STATIONS[0]);
  const [fechaIni, setFechaIni] = useState(defaultDatetimeLocal(48));
  const [fechaFin, setFechaFin] = useState(defaultDatetimeLocal(0));
  const [location, setLocation] = useState("");
  const [aggregation, setAggregation] = useState<Aggregation>("hourly");
  const [dataTypes, setDataTypes] = useState<DataType[]>([]);

  function toggleDataType(dt: DataType) {
    setDataTypes((prev) => (prev.includes(dt) ? prev.filter((x) => x !== dt) : [...prev, dt]));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      station,
      fechaIniStr: withSeconds(fechaIni),
      fechaFinStr: withSeconds(fechaFin),
      location: location.trim() || undefined,
      aggregation,
      dataTypes,
    });
  }

  return (
    <form className="query-panel" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="station">Station</label>
        <select id="station" value={station} onChange={(e) => setStation(e.target.value as Station)}>
          {STATIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label htmlFor="fecha-ini">Start datetime</label>
        <input
          id="fecha-ini"
          type="datetime-local"
          step={1}
          value={fechaIni}
          onChange={(e) => setFechaIni(e.target.value)}
          required
        />
      </div>

      <div className="field">
        <label htmlFor="fecha-fin">End datetime</label>
        <input
          id="fecha-fin"
          type="datetime-local"
          step={1}
          value={fechaFin}
          onChange={(e) => setFechaFin(e.target.value)}
          required
        />
      </div>

      <div className="field">
        <label htmlFor="location">Input timezone (optional)</label>
        <input
          id="location"
          type="text"
          placeholder="Europe/Berlin or +02:00"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
        />
        <span className="hint">
          How the two datetimes above should be interpreted. Leave empty to treat them as UTC.
          Output is always shown in Europe/Madrid time (CET/CEST).
        </span>
      </div>

      <div className="field">
        <label htmlFor="aggregation">Time aggregation</label>
        <select
          id="aggregation"
          value={aggregation}
          onChange={(e) => setAggregation(e.target.value as Aggregation)}
        >
          {AGGREGATIONS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>

      <div className="field">
        <label>Measurements</label>
        <div className="checkbox-row">
          {DATA_TYPES.map((dt) => (
            <label key={dt}>
              <input
                type="checkbox"
                checked={dataTypes.includes(dt)}
                onChange={() => toggleDataType(dt)}
              />
              {dt}
            </label>
          ))}
        </div>
        <span className="hint">None selected = all three returned.</span>
      </div>

      <button className="submit-btn" type="submit" disabled={loading}>
        {loading ? "Querying…" : "Query AEMET data"}
      </button>
    </form>
  );
}
