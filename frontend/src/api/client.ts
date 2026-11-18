import type { TokenResponse } from "./types";

const BASE = "/api/v1";

/** El token de acceso vive solo en memoria; el refresh va en una cookie httpOnly. */
let accessToken: string | null = null;
let refreshing: Promise<TokenResponse | null> | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function onUnauthorized(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
  }

  /** Mensajes de validación legibles (lista de strings) cuando el backend los envía. */
  get details(): string[] {
    if (Array.isArray(this.detail)) {
      return this.detail.map((d) => (typeof d === "string" ? d : `${d.campo}: ${d.mensaje}`));
    }
    return [];
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

interface RequestOptions {
  method?: string;
  body?: unknown;
  form?: FormData;
  query?: Query;
  raw?: boolean;
  /** Consulta periódica (sondeo): no cuenta como actividad del usuario para el cierre por inactividad. */
  background?: boolean;
}

function buildUrl(path: string, query?: Query) {
  const url = new URL(BASE + path, window.location.origin);
  Object.entries(query ?? {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  });
  return url.pathname + url.search;
}

async function toError(res: Response): Promise<ApiError> {
  if (res.status === 502 || res.status === 503 || res.status === 504) {
    return new ApiError(res.status, "servidor_no_disponible",
      "El servidor no está disponible en este momento. Intente nuevamente en unos segundos.");
  }
  try {
    const data = await res.json();
    return new ApiError(res.status, data.code ?? "error", data.message ?? "Error inesperado.", data.detail);
  } catch {
    return new ApiError(res.status, "error", `Error ${res.status}`);
  }
}

async function send(path: string, opts: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (opts.background) headers["X-Background"] = "1";
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  return fetch(buildUrl(path, opts.query), {
    method: opts.method ?? "GET",
    headers,
    body,
    credentials: "same-origin",
  });
}

/** Renueva el token de acceso con la cookie de refresh (deduplica llamadas concurrentes). */
export function refreshSession(): Promise<TokenResponse | null> {
  if (!refreshing) {
    refreshing = fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "same-origin" })
      .then(async (res) => {
        if (!res.ok) return null;
        const data = (await res.json()) as TokenResponse;
        accessToken = data.access_token;
        return data;
      })
      .catch(() => null)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

/** Envía la petición y, si el token de acceso expiró, lo renueva una vez y reintenta. */
async function request(path: string, opts: RequestOptions): Promise<Response> {
  let res = await send(path, opts);
  if (res.status === 401 && accessToken && !path.startsWith("/auth/")) {
    const renewed = await refreshSession();
    if (renewed) res = await send(path, opts);
    else unauthorizedHandler?.();
  }
  if (!res.ok) throw await toError(res);
  return res;
}

export async function api<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  const res = await request(path, opts);
  if (res.status === 204) return undefined as T;
  if (opts.raw) return (await res.blob()) as T;
  return (await res.json()) as T;
}

/** Envío por navigator.sendBeacon (salida de módulo al ocultar o cerrar la pestaña). */
export function beacon(path: string, payload: unknown): boolean {
  if (typeof navigator === "undefined" || !navigator.sendBeacon) return false;
  const blob = new Blob([JSON.stringify(payload)], { type: "text/plain" });
  return navigator.sendBeacon(BASE + path, blob);
}

/** Nombre de archivo desde Content-Disposition (prefiere filename* en UTF-8). */
export function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (star) {
    try {
      return decodeURIComponent(star[1]);
    } catch {
      /* se usa el nombre simple */
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain ? plain[1] : fallback;
}

/** Descarga un archivo autenticado y lo guarda con el nombre que envía el servidor. */
export async function downloadFile(path: string, fallbackName: string): Promise<string> {
  const res = await request(path, {});
  const blob = await res.blob();
  const name = filenameFromDisposition(res.headers.get("Content-Disposition"), fallbackName);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return name;
}
