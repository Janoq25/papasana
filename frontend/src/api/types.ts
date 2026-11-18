export interface RoleBrief {
  id: number;
  code: string;
  name: string;
  data_scope: "todo" | "region" | "propio";
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  institution: string | null;
  phone: string | null;
  region_code: string | null;
  role: RoleBrief;
  is_active: boolean;
  is_locked: boolean;
  has_photo: boolean;
  locked_until: string | null;
  last_login_at: string | null;
  created_at: string;
}

export interface Me extends User {
  preferences: Record<string, unknown>;
  permissions: string[];
  session_settings: {
    minutos_inactividad: number;
    longitud_minima_contrasena: number;
    institucion: string;
    aviso: string;
  };
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: Me;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface Role {
  id: number;
  code: string;
  name: string;
  description: string | null;
  data_scope: "todo" | "region" | "propio";
  is_system: boolean;
  user_count: number;
  permissions: string[];
}

export interface PermissionCatalog {
  acciones: string[];
  modulos: { code: string; name: string; phase: number; acciones: string[] }[];
}

export interface AuditEntry {
  id: number;
  seq: number | null;
  occurred_at: string;
  user_id: string | null;
  user_email: string | null;
  role_code: string | null;
  session_id: string | null;
  event_type: string;
  module_code: string | null;
  action: string | null;
  http_method: string | null;
  endpoint: string | null;
  entity_type: string | null;
  entity_id: string | null;
  before: unknown;
  after: unknown;
  ip: string | null;
  user_agent: string | null;
  result: "exito" | "fallo";
  error_detail: string | null;
  related_event_id: number | null;
  duration_ms: number | null;
  hash: string | null;
}

export interface ModuleTime {
  module_code: string;
  total_ms: number;
  visitas: number;
}

export interface VerifyResult {
  ok: boolean;
  total_registros: number;
  primer_registro_alterado: { seq: number; id: number; motivo: string } | null;
  ultimo: { seq: number; hash: string } | null;
  verificado_en: string;
}

export interface Setting {
  key: string;
  value: string | number;
  description: string;
  type: "int" | "float" | "str";
  min: number | null;
  max: number | null;
  updated_at: string | null;
}

export interface Ubigeo {
  code: string;
  name: string;
  level: string;
  parent_code: string | null;
}

// --- Fase 2 -------------------------------------------------------------------------------------

export interface CatalogItem {
  id: number;
  name: string;
  is_active: boolean;
  group?: string | null;
  late_blight_susceptibility?: string | null;
  source?: string | null;
  code?: string | null;
  sort_order?: number | null;
  description?: string | null;
  causal_agent?: string | null;
  key_symptoms?: string | null;
  distinguishing_features?: string | null;
  is_target?: boolean | null;
}

export interface Producer {
  id: number;
  name: string;
  contact: string | null;
  region_code: string | null;
}

export interface PolygonGeometry {
  type: "Polygon";
  coordinates: number[][][]; // [[[lon, lat], ...]]
}

export interface Parcel {
  id: number;
  code: string;
  name: string;
  region_code: string;
  producer: Producer | null;
  variety: CatalogItem | null;
  stage: CatalogItem | null;
  sowing_date: string | null;
  altitude_m: number | null;
  area_ha: number;
  notes: string | null;
  is_active: boolean;
  geometry: PolygonGeometry | null;
  centroid: [number, number] | null;
  assignees: string[];
  created_at: string;
}

export interface ParcelFeatureCollection {
  type: "FeatureCollection";
  features: {
    type: "Feature";
    id: number;
    geometry: PolygonGeometry;
    properties: { id: number; code: string; name: string; area_ha: number; region_code: string };
  }[];
}

export interface ParcelOption {
  id: number;
  code: string;
  name: string;
  region_code: string;
}

export interface ModelVersion {
  id: number;
  model_key: string;
  display_name: string;
  architecture: string;
  stage: string;
  is_demo: boolean;
  label_scheme: string;
  classes: string[];
}

export interface DiagnosisImage {
  id: string;
  original_filename: string | null;
  width: number;
  height: number;
  size_bytes: number;
  captured_at: string | null;
  gps_source: "exif" | "dispositivo" | "manual" | "ninguno";
  location: { lat: number; lon: number } | null;
  inside_parcel: boolean | null;
  exif: Record<string, unknown>;
  provenance: string;
  duplicate_of_id: string | null;
  duplicate_distance: number | null;
}

export interface Review {
  id: number;
  reviewer_id: string;
  decision: "confirma" | "corrige" | "no_determinable";
  final_label: string;
  final_label_name: string;
  evidence: string | null;
  differential: string | null;
  notes: string | null;
  created_at: string;
}

export type Category = "sano" | "sospechoso" | "tizon_tardio_compatible";

export interface Diagnosis {
  id: string;
  created_at: string;
  status: "automatico" | "pendiente_revision" | "validado" | "corregido" | "anulado";
  category: Category;
  category_label: string;
  predicted_class: string;
  probabilities: Record<string, number>;
  confidence: number;
  threshold_used: number;
  requires_review: boolean;
  has_gradcam: boolean;
  inference_ms: number | null;
  void_reason: string | null;
  model: ModelVersion;
  parcel: { id: number; code: string; name: string; region_code: string };
  image: DiagnosisImage;
  reviews: Review[];
  created_by: string;
  disclaimer: string;
}

export interface BatchResultItem {
  archivo: string;
  aceptada: boolean;
  imagen_id?: string;
  motivo?: string;
  posible_duplicado?: boolean;
}

export interface Batch {
  id: string;
  status: "procesando" | "completado";
  total: number;
  processed: number;
  failed: number;
  created_at: string;
  results: BatchResultItem[];
  diagnoses: Diagnosis[];
}

export interface LabelCatalog {
  categorias: Record<string, string>;
  etiquetas_finales: Record<string, string>;
  evidencias: Record<string, string>;
}

// --- Fase 3: dashboard ---------------------------------------------------------------------------

export interface CategoryCounts {
  sano: number;
  sospechoso: number;
  tizon_tardio_compatible: number;
}

export interface UnavailableKpi {
  valor: number | null;
  motivo: string | null;
}

export interface DashboardData {
  alcance: "todo" | "region" | "propio";
  region_usuario: string | null;
  modelo: { display_name: string; is_demo: boolean; stage: string } | null;
  kpis: {
    diagnosticos: number;
    diagnosticos_ejemplo: number;
    por_categoria: { categoria: Category; etiqueta: string; total: number; porcentaje: number | null }[];
    pendientes_validacion: number;
    parcelas: number;
    parcelas_con_casos_compatibles: { valor: number; dias: number; hasta: string };
    acuerdo_experto: { valor: number | null; n: number; confirma: number; corrige: number };
    precision_modelo: UnavailableKpi;
    alertas_activas: UnavailableKpi;
    parcelas_en_riesgo: UnavailableKpi;
  };
  tendencia: {
    granularidad: "dia" | "semana" | "mes";
    desde: string;
    hasta: string;
    series: ({ periodo: string } & CategoryCounts)[];
  };
  por_region: ({ codigo: string; nombre: string; total: number } & CategoryCounts)[];
  por_variedad: ({ nombre: string; total: number } & CategoryCounts)[];
  mapa: { lat: number; lon: number; categoria: Category; peso: number; aproximado: boolean }[];
  mapa_truncado: boolean;
}

// --- Fase 3: reportes ----------------------------------------------------------------------------

export type ReportFormat = "pdf" | "docx" | "xlsx";

export type ReportFilterType =
  | "date"
  | "number"
  | "text"
  | "select"
  | "region"
  | "parcel"
  | "variety"
  | "technician"
  | "model"
  | "role"
  | "module";

export interface ReportFilterField {
  key: string;
  label: string;
  type: ReportFilterType;
  options?: Record<string, string>;
}

export interface ReportDefinition {
  code: string;
  title: string;
  kind: "operacional" | "gestion" | "auditoria";
  kind_label: string;
  description: string;
  formats: ReportFormat[];
  filters: ReportFilterField[];
  available_from_phase: number | null;
}

export interface ReportOptions {
  regions: { code: string; name: string }[];
  parcels: { id: number; code: string; name: string }[];
  varieties: { id: number; name: string }[];
  technicians: { id: string; name: string; email: string }[];
  model_versions: { id: number; name: string; stage: string; is_demo: boolean }[];
  roles: { code: string; name: string }[];
  modules: { code: string; name: string }[];
}

export type ReportStatus = "pendiente" | "procesando" | "listo" | "error";

export interface ReportJob {
  id: string;
  report_code: string;
  report_title: string | null;
  format: ReportFormat;
  filters: Record<string, string | number>;
  status: ReportStatus;
  file_name: string | null;
  size_bytes: number | null;
  row_count: number | null;
  error: string | null;
  download_count: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

// --- Fase 3: notificaciones ----------------------------------------------------------------------

export interface AppNotification {
  id: number;
  kind: string;
  title: string;
  body: string | null;
  link: string | null;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
  read_at: string | null;
}

export interface NotificationSummary {
  unread: number;
  recent: AppNotification[];
}

export interface NotificationPage extends Page<AppNotification> {
  unread: number;
}

// --- Fase 4: laboratorio de modelos --------------------------------------------------------------

export type ModelStage = "demo" | "staging" | "production" | "archived";

export interface LabModel {
  id: number;
  model_key: string;
  architecture: string;
  display_name: string;
  source: "demo" | "mlflow";
  stage: ModelStage;
  is_demo: boolean;
  smoke_test: boolean;
  label_scheme: string;
  classes: string[];
  temperature: number;
  mlflow_model_name: string | null;
  mlflow_version: string | null;
  mlflow_run_id: string | null;
  train_dataset_ids: string[];
  metrics_summary: Record<string, number> | null;
  registered_at: string | null;
  synced_at: string | null;
}

export interface ClassMetrics {
  support: number;
  precision: number | null;
  sensitivity: number | null;
  specificity: number | null;
  f1: number | null;
  auc_roc: number | null;
  auc_pr: number | null;
}

export interface ReliabilityBin {
  lower: number;
  upper: number;
  count: number;
  accuracy: number | null;
  confidence: number | null;
}

export interface SplitEvaluation {
  split: string;
  n: number;
  accuracy: number | null;
  macro_f1: number | null;
  mcc: number | null;
  macro_sensitivity: number | null;
  macro_specificity: number | null;
  macro_auc_roc: number | null;
  macro_auc_pr: number | null;
  per_class: Record<string, ClassMetrics>;
  confusion_matrix: number[][];
  classes: string[];
  roc_curves?: Record<string, { fpr: number[]; tpr: number[] }>;
  pr_curves?: Record<string, { recall: number[]; precision: number[] }>;
  calibration?: {
    temperature: number;
    nll_before: number;
    nll_after: number;
    before: { ece: number; bins: ReliabilityBin[] };
    after: { ece: number; bins: ReliabilityBin[] };
  };
}

export interface LabModelDetail {
  modelo: LabModel;
  run: { params: Record<string, string>; metrics: Record<string, number>; tags: Record<string, string> } | null;
  evaluacion: Record<string, SplitEvaluation> | null;
  historial: Record<string, { step: number; value: number }[]>;
  validacion_cruzada: { run_id: string; metrics: Record<string, number> } | null;
  mlflow_url: string | null;
  mensaje?: string;
}

export interface StatRow {
  modelo_a: string;
  modelo_b: string;
  p_valor: number;
  [key: string]: unknown;
}

export interface Comparison {
  estado: "ok" | "sin_experimentos";
  mensaje?: string;
  metrica?: string;
  modelos?: string[];
  bloques?: string[];
  smoke_test?: boolean;
  solo_prueba_de_humo?: boolean;
  por_modelo?: Record<string, { media: number; desviacion: number; n_bloques: number }>;
  friedman?: { aplicable: boolean; motivo?: string; estadistico?: number; p_valor?: number; bloques?: number;
    rango_medio?: Record<string, number> };
  wilcoxon_holm?: (StatRow & { p_holm: number; diferencia_media: number })[];
  mcnemar?: (StatRow & { n01: number; n10: number; metodo: string })[];
  delong?: (StatRow & { auc_a?: number; auc_b?: number; aplicable: boolean; clase: string })[];
  bootstrap?: Record<string, Record<string, { valor: number; ic_inferior: number | null; ic_superior: number | null }>>;
  oof_imagenes?: number;
  run_id?: string;
}

export interface LabStatus {
  mlflow_configurado: boolean;
  mlflow_disponible: boolean;
  mlflow_url: string;
  ml_service: ({ key: string; display_name: string; is_demo: boolean; load_status?: { estado: string;
    detalle: string | null } } & Record<string, unknown>) | { error: string } | null;
  produccion_registrada: string | null;
}

export interface Promotion {
  id: number;
  action: "promover" | "rollback";
  status: "pendiente" | "aplicada" | "rechazada" | "cancelada" | "fallida";
  from_stage: string | null;
  to_stage: string;
  model_version: LabModel;
  previous: LabModel | null;
  requested_by: string;
  requested_by_name: string | null;
  request_reason: string;
  decided_by: string | null;
  decided_by_name: string | null;
  decision_reason: string | null;
  error: string | null;
  created_at: string;
  decided_at: string | null;
}

// --- Fase 4: datasets y licencias (A1) -----------------------------------------------------------

export type LicenseStatus = "por_verificar" | "verificada" | "rechazada";

export interface DatasetEntry {
  id: number;
  code: string;
  name: string;
  version: string | null;
  source_url: string | null;
  license: string | null;
  license_url: string | null;
  license_status: LicenseStatus;
  license_notes: string | null;
  license_verified_by: string | null;
  license_verified_by_name: string | null;
  license_verified_at: string | null;
  citation: string | null;
  conditions: "laboratorio" | "campo" | "mixto" | "sintetico";
  label_scheme: string;
  etiological_confirmation: "no" | "parcial" | "si";
  has_group_ids: boolean;
  role: "entrenamiento" | "validacion_externa" | "validacion_prospectiva" | "prueba_de_humo";
  class_map: Record<string, string>;
  n_images: number | null;
  notes: string | null;
  is_active: boolean;
  usable: boolean;
  updated_at: string;
}
