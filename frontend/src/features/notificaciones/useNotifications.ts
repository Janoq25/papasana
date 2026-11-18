import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { NotificationSummary } from "../../api/types";

export const KIND_LABELS: Record<string, string> = {
  reporte_listo: "Reporte listo",
  reporte_error: "Error en reporte",
  revision_pendiente: "Validación pendiente",
  alerta: "Alerta",
};

/** Resumen para la campana: se consulta cada minuto sin contar como actividad del usuario. */
export function useNotificationSummary() {
  return useQuery({
    queryKey: ["notificaciones", "resumen"],
    queryFn: () => api<NotificationSummary>("/notificaciones/resumen", { background: true }),
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api(`/notificaciones/${id}/leida`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notificaciones"] }),
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ marcadas: number }>("/notificaciones/leer-todas", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notificaciones"] }),
  });
}
