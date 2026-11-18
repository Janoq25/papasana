import type { LabModel, ModelStage, Promotion } from "../../api/types";

export const STAGE_LABEL: Record<ModelStage, string> = {
  demo: "DEMO",
  staging: "Registrado",
  production: "En producción",
  archived: "Archivado",
};

export const STAGE_COLOR: Record<ModelStage, "default" | "info" | "success" | "warning"> = {
  demo: "warning",
  staging: "info",
  production: "success",
  archived: "default",
};

export const PROMOTION_STATUS_LABEL: Record<Promotion["status"], string> = {
  pendiente: "Pendiente de aprobación",
  aplicada: "Aplicada",
  rechazada: "Rechazada",
  cancelada: "Cancelada",
  fallida: "Fallida (se restauró el modelo anterior)",
};

export const PROMOTION_STATUS_COLOR: Record<Promotion["status"], "default" | "warning" | "success" | "error"> = {
  pendiente: "warning",
  aplicada: "success",
  rechazada: "default",
  cancelada: "default",
  fallida: "error",
};

export const ARCH_LABEL: Record<string, string> = {
  efficientnetv2_b0: "EfficientNetV2-B0",
  mobilenetv4_conv_medium: "MobileNetV4 Conv Medium",
  efficientvit_b1: "EfficientViT-B1",
  resnet50: "ResNet50",
  efficientnet_b3: "EfficientNet-B3",
  convnext_tiny: "ConvNeXt-Tiny",
  cnn_vit: "H1 · CNN-ViT",
  effnet_att_bilstm: "H2 · EffNet-Att-BiLSTM",
};

export const SPLIT_LABEL = (split: string) =>
  split === "val" ? "Validación interna" : split === "test" ? "Prueba (partición)"
    : split.startsWith("external_") ? `Externa · ${split.slice("external_".length)}` : split;

export function fmtMetric(v: number | null | undefined, digits = 3): string {
  return v === null || v === undefined || Number.isNaN(v) ? "—" : v.toFixed(digits);
}

export function fmtP(p: number | null | undefined): string {
  if (p === null || p === undefined) return "—";
  return p < 0.001 ? "< 0,001" : p.toFixed(3).replace(".", ",");
}

/** Resumen de métricas de una versión (solo las que existen en MLflow; nunca se completan). */
export function summarize(m: LabModel) {
  const s = m.metrics_summary ?? {};
  const ext = Object.keys(s).filter((k) => k.startsWith("external_") && k.endsWith("_macro_f1"));
  return {
    valF1: s.val_macro_f1 ?? null,
    cvF1: s.cv_mean_test_macro_f1 ?? null,
    cvF1Std: s.cv_std_test_macro_f1 ?? null,
    extF1: ext.length ? s[ext[0]] : null,
    extName: ext.length ? ext[0].slice("external_".length, -"_macro_f1".length) : null,
    ece: s.test_ece ?? s[ext[0]?.replace("_macro_f1", "_ece") ?? ""] ?? null,
    hasMetrics: Object.keys(s).length > 0,
  };
}

/** Puede pedirse rollback a una versión que estuvo en producción o al DEMO (si hay otro modelo en uso). */
export function canRollbackTo(m: LabModel, promotions: Promotion[], productionInUse: boolean): boolean {
  if (m.stage === "production") return false;
  if (m.source === "demo") return productionInUse;
  return promotions.some((p) => p.status === "aplicada" && p.previous?.id === m.id);
}

export function canPromote(m: LabModel): boolean {
  return m.source === "mlflow" && m.stage !== "production";
}
