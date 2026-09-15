import type { AntartidaResponse, QueryParams } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {}

export async function fetchAntartidaDatos(params: QueryParams): Promise<AntartidaResponse> {
  const path =
    `/api/antartida/datos/fechaini/${encodeURIComponent(params.fechaIniStr)}` +
    `/fechafin/${encodeURIComponent(params.fechaFinStr)}` +
    `/estacion/${encodeURIComponent(params.station)}`;

  const search = new URLSearchParams();
  if (params.location) search.set("location", params.location);
  search.set("time_aggregation", params.aggregation);
  for (const dt of params.dataTypes) search.append("data_types", dt);

  const response = await fetch(`${API_BASE_URL}${path}?${search.toString()}`);

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail ?? response.statusText;
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  return (await response.json()) as AntartidaResponse;
}
