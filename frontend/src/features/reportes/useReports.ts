import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { ReportDefinition, ReportFormat, ReportJob, ReportOptions, ReportStatus } from "../../api/types";

export const FORMAT_LABELS: Record<ReportFormat, string> = { pdf: "PDF", docx: "Word", xlsx: "Excel" };

export const STATUS_LABELS: Record<ReportStatus, string> = {
  pendiente: "En cola",
  procesando: "Generando",
  listo: "Listo",
  error: "Error",
};

export const STATUS_COLORS: Record<ReportStatus, "default" | "info" | "success" | "error"> = {
  pendiente: "default",
  procesando: "info",
  listo: "success",
  error: "error",
};

const NUMERIC_KEYS = new Set(["parcel_id", "variety_id", "model_version_id", "min_age_days"]);

export function isFinished(status: ReportStatus | undefined) {
  return status === "listo" || status === "error";
}

/** Quita los filtros vacíos y convierte a número los que el backend espera como enteros. */
export function cleanFilters(values: Record<string, string>, allowed?: string[]): Record<string, string | number> {
  const out: Record<string, string | number> = {};
  Object.entries(values).forEach(([k, v]) => {
    if (v === undefined || v === null || String(v).trim() === "") return;
    if (allowed && !allowed.includes(k)) return;
    out[k] = NUMERIC_KEYS.has(k) ? Number(v) : String(v).trim();
  });
  return out;
}

export function useReportCatalog(enabled = true) {
  return useQuery({
    queryKey: ["reportes", "catalogo"],
    queryFn: () => api<ReportDefinition[]>("/reportes/catalogo"),
    staleTime: 300_000,
    enabled,
  });
}

export function useReportOptions(enabled = true) {
  return useQuery({
    queryKey: ["reportes", "opciones"],
    queryFn: () => api<ReportOptions>("/reportes/opciones"),
    staleTime: 120_000,
    enabled,
  });
}

export function useRequestReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { code: string; format: ReportFormat; filters: Record<string, string | number> }) =>
      api<ReportJob>("/reportes", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reportes", "historial"] }),
  });
}

/** Estado de un reporte; consulta cada 1,5 s hasta que termina (sin contar como actividad del usuario). */
export function useReportJob(id: string | null) {
  const q = useQuery({
    queryKey: ["reportes", "job", id],
    queryFn: () => api<ReportJob>(`/reportes/${id}`, { background: true }),
    enabled: !!id,
    refetchInterval: (query) => (isFinished(query.state.data?.status) ? false : 1500),
  });
  useNotifyWhenFinished(q.data ? [q.data] : []);
  return q;
}

/** Cuando un reporte termina, refresca el historial y la campana de notificaciones. */
export function useNotifyWhenFinished(jobs: ReportJob[]) {
  const qc = useQueryClient();
  const pending = useRef(new Set<string>());
  useEffect(() => {
    let finished = false;
    jobs.forEach((j) => {
      if (!isFinished(j.status)) pending.current.add(j.id);
      else if (pending.current.delete(j.id)) finished = true;
    });
    if (finished) {
      void qc.invalidateQueries({ queryKey: ["notificaciones"] });
      void qc.invalidateQueries({ queryKey: ["reportes", "historial"] });
    }
  }, [jobs, qc]);
}

export function formatBytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
