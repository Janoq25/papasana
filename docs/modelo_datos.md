# Modelo de datos

Estado: **Fase 4**. Este documento crece con cada fase; el diseño completo previsto está en [fase0_plan.md §2](fase0_plan.md).

## Diagrama entidad-relación (implementado)

```mermaid
erDiagram
    ROLES ||--o{ USERS : "role_id"
    ROLES ||--o{ ROLE_PERMISSIONS : ""
    PERMISSIONS ||--o{ ROLE_PERMISSIONS : ""
    MODULES ||--o{ PERMISSIONS : "módulo × acción"
    USERS ||--o{ USER_SESSIONS : ""
    USERS ||--o{ PASSWORD_RESET_TOKENS : ""
    ROLES ||--o{ SERVICE_ACCOUNTS : ""
    UBIGEO ||--o{ USERS : "region_code"
    UBIGEO ||--o{ UBIGEO : "parent_code"

    ROLES {
        int id PK
        varchar code UK
        varchar name
        varchar data_scope "todo | region | propio"
        bool is_system
    }
    MODULES {
        int id PK
        varchar code UK
        int phase
        bool requires_permission
    }
    PERMISSIONS {
        int id PK
        int module_id FK
        varchar action "ver crear editar eliminar exportar aprobar"
    }
    USERS {
        uuid id PK
        varchar email UK
        varchar password_hash "Argon2id"
        varchar region_code FK
        int role_id FK
        int failed_attempts
        timestamptz locked_until
        jsonb preferences
    }
    USER_SESSIONS {
        uuid id PK
        uuid user_id FK
        varchar refresh_token_hash UK
        varchar previous_token_hash "detección de reuso"
        timestamptz last_seen_at "inactividad"
        timestamptz revoked_at
    }
    AUDIT_LOG {
        bigint id PK
        bigint seq UK "orden de la cadena"
        timestamptz occurred_at
        uuid user_id
        varchar event_type
        varchar module_code
        jsonb before
        jsonb after
        bigint related_event_id "salida → entrada"
        bigint duration_ms
        varchar prev_hash
        varchar hash "SHA-256(prev_hash ‖ payload)"
    }
    SYSTEM_SETTINGS {
        varchar key PK
        jsonb value
    }
    UBIGEO {
        varchar code PK
        varchar level
        varchar parent_code FK
    }
```

`auditoria.audit_log` no tiene claves foráneas a propósito: conserva `user_email` y `role_code` del momento del evento, de modo que el registro no depende de cambios posteriores en usuarios o roles.

## Esquemas

| Esquema | Tablas (Fase 1) |
|---|---|
| `seguridad` | `users`, `roles`, `modules`, `permissions`, `role_permissions`, `user_sessions`, `password_reset_tokens`, `service_accounts` |
| `auditoria` | `audit_log` + funciones `fn_audit_payload`, `fn_audit_chain`, `fn_audit_immutable` |
| `catalogo` | `ubigeo` (departamentos; provincias y distritos en la Fase 2) |
| `configuracion` | `system_settings` |

## Bitácora inmutable

1. **Trigger `trg_audit_chain` (BEFORE INSERT):** toma un `pg_advisory_xact_lock`, asigna `seq = último + 1`, `prev_hash = hash del último` y `hash = SHA-256(prev_hash ‖ JSON canónico del registro)`.
2. **Triggers `trg_audit_no_update_delete` y `trg_audit_no_truncate`:** lanzan una excepción ante UPDATE, DELETE o TRUNCATE, incluso para el propietario.
3. **Permisos:** el usuario de la aplicación (`papasana_app`) solo tiene `INSERT` y `SELECT` sobre la tabla.
4. **Verificación:** `GET /api/v1/audit/verify` recalcula la cadena completa e informa el primer registro alterado (`contenido_alterado`) o faltante (`cadena_rota`).

**Limitación conocida:** borrar los últimos registros de la cadena (truncar la cola) no rompe la cadena restante. Se mitiga en la Fase 5: WF-06 guardará cada día el último `seq` y `hash` fuera de la base de datos (anclaje externo), de modo que una cola eliminada se detecte al comparar.


## Fase 2: catálogos, campo y modelos

```mermaid
erDiagram
    UBIGEO ||--o{ PARCELS : "region_code"
    UBIGEO ||--o{ PRODUCERS : "region_code"
    PRODUCERS ||--o{ PARCELS : ""
    POTATO_VARIETIES ||--o{ PARCELS : ""
    PHENOLOGICAL_STAGES ||--o{ PARCELS : ""
    PARCELS ||--o{ PARCEL_ASSIGNMENTS : ""
    USERS ||--o{ PARCEL_ASSIGNMENTS : "técnico"
    PARCELS ||--o{ IMAGES : ""
    UPLOAD_BATCHES ||--o{ IMAGES : "lote"
    IMAGES ||--o{ IMAGES : "duplicate_of_id"
    IMAGES ||--o{ DIAGNOSES : ""
    MODEL_VERSIONS ||--o{ DIAGNOSES : "versión usada"
    DIAGNOSES ||--o{ EXPERT_REVIEWS : "human-in-the-loop"
    DIFFERENTIAL_DISEASES ||--o{ EXPERT_REVIEWS : "diferencial"

    PARCELS {
        int id PK
        varchar code UK
        geometry geom "POLYGON 4326 (GiST)"
        geometry centroid "POINT 4326"
        float area_ha "ST_Area(geography)"
        varchar region_code FK
    }
    IMAGES {
        uuid id PK
        varchar sha256 "único por parcela"
        bigint phash "dHash 64 bits"
        geometry location "POINT 4326 (GiST)"
        varchar gps_source "exif | dispositivo | manual | ninguno"
        bool inside_parcel "ST_Contains"
        uuid duplicate_of_id FK
    }
    DIAGNOSES {
        uuid id PK
        varchar predicted_class "síntoma (modelo)"
        varchar category "sano | sospechoso | tizon_tardio_compatible"
        jsonb probabilities
        float confidence
        float threshold_used
        bool requires_review
        varchar status "automatico | pendiente_revision | validado | corregido | anulado"
        varchar gradcam_key "MinIO"
    }
    EXPERT_REVIEWS {
        int id PK
        varchar decision "confirma | corrige | no_determinable"
        varchar final_label
        varchar evidence "obligatoria si confirmado"
    }
    MODEL_VERSIONS {
        int id PK
        varchar model_key UK
        bool is_demo
        varchar stage
        float temperature "calibración"
    }
```

| Esquema | Tablas (Fase 2) |
|---|---|
| `catalogo` | `potato_varieties`, `phenological_stages`, `differential_diseases` |
| `campo` | `producers`, `parcels`, `parcel_assignments`, `upload_batches`, `images`, `diagnoses`, `expert_reviews` |
| `ml` | `model_versions` |

El usuario de la aplicación no tiene `DELETE` ni `TRUNCATE` sobre `campo.images`, `campo.diagnoses` ni `campo.expert_reviews` (D-38).


## Fase 3: reportes y notificaciones

```mermaid
erDiagram
    USERS ||--o{ REPORT_JOBS : "solicita"
    USERS ||--o{ NOTIFICATIONS : "recibe"

    REPORT_JOBS {
        uuid id PK
        varchar report_code "R-01 … R-10, B-01"
        varchar format "pdf | docx | xlsx"
        jsonb filters "solo los filtros usados"
        varchar status "pendiente | procesando | listo | error"
        varchar object_key "MinIO, bucket reportes"
        int row_count
        int download_count
        varchar source "web | n8n (Fase 5)"
    }
    NOTIFICATIONS {
        bigint id PK
        uuid user_id FK
        varchar kind "reporte_listo | reporte_error | revision_pendiente | alerta"
        varchar title
        varchar link "ruta de la interfaz"
        varchar entity_type
        varchar entity_id
        timestamptz read_at
    }
```

| Esquema | Tablas (Fase 3) |
|---|---|
| `reportes` | `report_jobs` |
| `notificaciones` | `notifications` |

- El usuario de la aplicación no tiene `DELETE` sobre estas tablas: el historial de reportes y las notificaciones se conservan (D-43).
- Los datos de cada reporte se calculan al generarlo, a partir de las tablas de `campo`, `ml` y `auditoria`. No hay tablas de agregados.


## Fase 4: laboratorio de modelos y datasets

```mermaid
erDiagram
    MODEL_VERSIONS ||--o{ MODEL_PROMOTIONS : "versión objetivo"
    MODEL_VERSIONS ||--o{ MODEL_PROMOTIONS : "versión anterior"
    USERS ||--o{ MODEL_PROMOTIONS : "solicita / decide"
    USERS ||--o{ DATASETS : "verifica la licencia"

    MODEL_VERSIONS {
        int id PK
        varchar model_key UK "demo-… o papasana-<arq>:v<n>"
        varchar source "demo | mlflow"
        varchar stage "demo | staging | production | archived"
        varchar mlflow_model_name
        varchar mlflow_version
        varchar mlflow_run_id
        bool smoke_test
        jsonb train_dataset_ids
        jsonb metrics_summary "copiado de MLflow"
    }
    MODEL_PROMOTIONS {
        int id PK
        varchar action "promover | rollback"
        varchar status "pendiente | aplicada | rechazada | cancelada | fallida"
        uuid requested_by FK
        uuid decided_by FK "distinto del solicitante"
        text request_reason
        text error
    }
    DATASETS {
        int id PK
        varchar code UK "= id en ml/datasets.yaml"
        varchar license_status "por_verificar | verificada | rechazada"
        uuid license_verified_by FK
        timestamptz license_verified_at
        jsonb class_map "etiqueta de la fuente → clase por síntoma"
        varchar role "entrenamiento | validacion_externa | …"
    }
```

- El **Model Registry de MLflow** es la fuente de verdad: `model_versions` es una copia sincronizada, y la etapa `production` refleja el alias `production`.
- Los metadatos de MLflow viven en una base aparte (`mlflow`), con rol propio.
- El usuario de la aplicación no tiene `DELETE` sobre `ml.model_promotions` (historial de cuatro ojos).
