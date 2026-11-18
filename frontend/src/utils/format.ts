import dayjs from "dayjs";
import "dayjs/locale/es";
import utc from "dayjs/plugin/utc";
import timezone from "dayjs/plugin/timezone";

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.locale("es");

export const TZ = "America/Lima";

/** Fecha y hora en la zona horaria de Lima (la bitácora se guarda en UTC). */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return dayjs(iso).tz(TZ).format("DD/MM/YYYY HH:mm:ss");
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ${s % 60} s`;
  const h = Math.floor(m / 60);
  return `${h} h ${m % 60} min`;
}

/** Convierte una fecha local de Lima (YYYY-MM-DD) a ISO UTC para filtrar. */
export function limaDayStartIso(date: string): string {
  return dayjs.tz(date, TZ).startOf("day").toISOString();
}

export function limaNextDayStartIso(date: string): string {
  return dayjs.tz(date, TZ).add(1, "day").startOf("day").toISOString();
}

export const EVENT_LABELS: Record<string, string> = {
  login: "Inicio de sesión",
  login_fallido: "Inicio de sesión fallido",
  bloqueo_cuenta: "Bloqueo de cuenta",
  logout: "Cierre de sesión",
  sesion_expirada: "Sesión expirada",
  modulo_entrada: "Entrada a módulo",
  modulo_salida: "Salida de módulo",
  accion: "Acción",
  acceso_denegado: "Acceso denegado",
};

export const SCOPE_LABELS: Record<string, string> = {
  todo: "Todos los datos",
  region: "Su región",
  propio: "Solo lo propio",
};
