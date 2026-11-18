import dayjs from "dayjs";
import { TZ } from "../../utils/format";

export interface DashboardFilters {
  date_from: string;
  date_to: string;
  region_code: string;
  parcel_id: string;
  variety_id: string;
}

export const FILTER_KEYS: (keyof DashboardFilters)[] = ["date_from", "date_to", "region_code", "parcel_id", "variety_id"];
export const DEFAULT_DAYS = 90;

/** Últimos 90 días (hoy incluido) en la hora de Lima. */
export function defaultFilters(now = dayjs()): DashboardFilters {
  const today = now.tz(TZ);
  return {
    date_from: today.subtract(DEFAULT_DAYS - 1, "day").format("YYYY-MM-DD"),
    date_to: today.format("YYYY-MM-DD"),
    region_code: "",
    parcel_id: "",
    variety_id: "",
  };
}

/** Los filtros globales viven en la URL (se pueden compartir y sobreviven a la recarga). */
export function filtersFromParams(params: URLSearchParams, defaults = defaultFilters()): DashboardFilters {
  const out = { ...defaults };
  FILTER_KEYS.forEach((k) => {
    const v = params.get(k);
    if (v !== null) out[k] = v;
  });
  return out;
}

export function filtersToParams(f: DashboardFilters, defaults = defaultFilters()): Record<string, string> {
  const out: Record<string, string> = {};
  FILTER_KEYS.forEach((k) => {
    if (f[k] !== defaults[k]) out[k] = f[k];
  });
  return out;
}

export function rangeError(f: DashboardFilters): string | null {
  if (f.date_from && f.date_to && f.date_from > f.date_to) return "La fecha final debe ser igual o posterior a la inicial.";
  return null;
}

/** Etiqueta del eje X según la granularidad de la tendencia. */
export function periodLabel(iso: string, granularity: "dia" | "semana" | "mes"): string {
  const d = dayjs(iso);
  if (granularity === "mes") return d.format("MMM YYYY");
  if (granularity === "semana") return `Sem. ${d.format("DD/MM")}`;
  return d.format("DD/MM");
}
