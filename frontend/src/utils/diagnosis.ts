import type { Category, Diagnosis } from "../api/types";

/** Colores MUI por categoría (D-01). */
export const CATEGORY_COLOR: Record<Category, "success" | "warning" | "error"> = {
  sano: "success",
  sospechoso: "warning",
  tizon_tardio_compatible: "error",
};

export const CATEGORY_LABEL: Record<Category, string> = {
  sano: "Sano",
  sospechoso: "Sospechoso",
  tizon_tardio_compatible: "Tizón tardío: síntomas compatibles",
};

export const STATUS_LABEL: Record<Diagnosis["status"], string> = {
  automatico: "Automático",
  pendiente_revision: "Pendiente de revisión",
  validado: "Validado por especialista",
  corregido: "Corregido por especialista",
  anulado: "Anulado",
};

/** Nombres legibles de las clases que predice el modelo (síntomas, no patógeno). */
export const CLASS_LABEL: Record<string, string> = {
  sano: "Sano",
  sintomas_compatibles_tizon_tardio: "Síntomas compatibles con tizón tardío",
  otra_enfermedad_foliar: "Otra enfermedad foliar",
};

export const GPS_LABEL: Record<string, string> = {
  exif: "GPS de la foto (EXIF)",
  dispositivo: "Ubicación del dispositivo",
  manual: "Ingresada manualmente",
  ninguno: "Sin ubicación",
};

export function percent(v: number): string {
  return `${(v * 100).toFixed(1)} %`;
}

/** Probabilidades ordenadas de mayor a menor. */
export function sortedProbabilities(probs: Record<string, number>): [string, number][] {
  return Object.entries(probs).sort((a, b) => b[1] - a[1]);
}
