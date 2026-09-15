export const STATIONS = [
  "Meteo Station Gabriel de Castilla",
  "Meteo Station Juan Carlos I",
] as const;
export type Station = (typeof STATIONS)[number];

export const DATA_TYPES = ["temperature", "pressure", "speed"] as const;
export type DataType = (typeof DATA_TYPES)[number];

export const AGGREGATIONS = ["none", "hourly", "daily", "monthly"] as const;
export type Aggregation = (typeof AGGREGATIONS)[number];

export interface MeasurementOut {
  station: string;
  datetime: string; // ISO-8601 with UTC offset, Europe/Madrid
  temperature_c: number | null;
  pressure_hpa: number | null;
  speed_ms: number | null;
}

export interface AntartidaResponse {
  station: Station;
  aggregation: Aggregation;
  from_datetime: string;
  to_datetime: string;
  tz_location_requested: string | null;
  count: number;
  data: MeasurementOut[];
}

export interface QueryParams {
  station: Station;
  fechaIniStr: string;
  fechaFinStr: string;
  location?: string;
  aggregation: Aggregation;
  dataTypes: DataType[];
}
