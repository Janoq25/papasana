import type { SplitEvaluation } from "../../../api/types";
export interface ReportSummary { id: string; title: string; trained_on: string; model_count: number }
export interface ResearchModel {
  architecture: string; label: string; run_id: string; best_epoch: number;
  metrics: Record<string, number>; parameters: number; checkpoint_mb: number;
  checkpoint_sha256: string; img_size: number;
  train: Record<string, string | number | boolean | null>;
  history: Record<string, { step: number; value: number }[]>;
  evaluation: Record<string, SplitEvaluation>;
}
export interface ResearchReport {
  schema_version: 1; id: string; title: string; trained_on: string; generated_at: string;
  gpu: string; torch: string; manifest_sha256: string; fingerprint: string; classes: string[];
  data: {
    original: number; duplicates_removed: number; quarantined: number; accepted: number;
    train: number; validation: number; external: number; leaf_groups: number; validation_fold: number;
    datasets: { id: string; n: number; role: string; counts: Record<string, number> }[];
    folds: { fold: number; n: number; counts: Record<string, number> }[];
    resolution: { metric: string; width: number; height: number }[];
  };
  models: ResearchModel[];
  selection: { recommended_architecture: string; best_internal_architecture: string;
    fastest_architecture: string; external_used_for_selection: false; statistical_noninferiority_proven: false };
  limitations: string[];
  model_sources: { architecture: string; repo: string; revision: string; license: string; license_source: string }[];
  data_sources: { title: string; license: string; url: string }[];
}
export const number = (v: number | null | undefined, digits = 4) => v == null || !Number.isFinite(v)
  ? "—" : new Intl.NumberFormat("es-PE", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(v);
export const shortClass: Record<string, string> = { sano: "Sano", sintomas_compatibles_tizon_tardio: "Tizón tardío (síntomas)", otra_enfermedad_foliar: "Otra enfermedad foliar" };
export const shortModel: Record<string, string> = { resnet50: "ResNet50", efficientnetv2_b0: "EffNetV2-B0", mobilenetv4_conv_medium: "MobileNetV4-M", efficientvit_b1: "EfficientViT-B1" };
