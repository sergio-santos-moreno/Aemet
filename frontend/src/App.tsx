import { useState } from "react";
import QueryForm from "./components/QueryForm";
import DataTable from "./components/DataTable";
import DataChart from "./components/DataChart";
import { fetchAntartidaDatos, ApiError } from "./api";
import type { AntartidaResponse, QueryParams } from "./types";

export default function App() {
  const [result, setResult] = useState<AntartidaResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(params: QueryParams) {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAntartidaDatos(params);
      setResult(data);
    } catch (err) {
      setResult(null);
      setError(err instanceof ApiError ? err.message : "Unexpected error querying the API.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <span className="mark">AEMET</span>
        <h1>Antarctic Station Data</h1>
        <span className="sub">Wind Farm feasibility · Business Development</span>
      </header>

      <div className="app-body">
        <QueryForm onSubmit={handleSubmit} loading={loading} />

        <main className="content">
          {error && <div className="error-box">{error}</div>}

          {!error && !result && !loading && (
            <div className="empty-state">
              Choose a station and date range, then run a query to see readings here.
            </div>
          )}

          {result && (
            <>
              <div className="status-line">
                {result.station} · {result.from_datetime} → {result.to_datetime}
                {result.tz_location_requested ? ` (input tz: ${result.tz_location_requested})` : " (input tz: UTC)"}
                {" · "}aggregation: {result.aggregation}
              </div>
              <DataChart data={result.data} />
              <DataTable data={result.data} />
            </>
          )}
        </main>
      </div>
    </div>
  );
}
