# PapaSana AP-01

Sistema de apoyo a la decisión para la **detección por síntomas del tizón tardío de la papa** en condiciones de campo, integrado con alertas de riesgo climático.

> Prototipo de investigación. Los resultados **no constituyen un diagnóstico definitivo** y deben ser revisados por un profesional agrónomo.

**Estado:** Fase 4 escrita (MLflow, entrenamiento de los 5 modelos en `ml/`, laboratorio de modelos con promoción y rollback de cuatro ojos, y registro de datasets y licencias) sobre las Fases 1 a 3 (autenticación, RBAC y bitácora; parcelas y diagnóstico; dashboard, reportes y notificaciones). Ver el plan en [docs/fase0_plan.md](docs/fase0_plan.md) y las decisiones en [docs/decisiones.md](docs/decisiones.md).

---

## Arquitectura (Fases 1 a 4)

```
Navegador ──► frontend (Nginx: SPA React + proxy /api, cabeceras de seguridad)
                 │
                 ▼
              backend (FastAPI: routers → services → repositories)
                 │        │          │
                 ▼        ▼          ▼
           PostgreSQL   Redis      MinIO (fotos de perfil, imágenes de hojas, Grad-CAM, reportes)
        (PostGIS+pgvector) │          ▲
                           ▼          │
                     worker (Celery: correos, lotes de imágenes y reportes) ──► Mailpit (correo de desarrollo)
                 │
                 ▼  (red interna, token)
              ml-service (FastAPI + PyTorch CPU: modelo con alias "production" o DEMO, calibración y Grad-CAM)
                 │  (resuelve el alias y descarga model/)
                 ▼
              mlflow (tracking + Model Registry · metadatos en la base `mlflow` · artefactos en MinIO)
                 ▲
              ml/ (entrenamiento fuera de la aplicación: local con GPU o Google Colab)
```

| Servicio | URL local | Uso |
|---|---|---|
| Aplicación | http://127.0.0.1:8080 | Interfaz web |
| API / OpenAPI | http://127.0.0.1:8080/api/docs | Documentación interactiva |
| Mailpit | http://127.0.0.1:8025 | Correos capturados (recuperación de contraseña) |
| Consola MinIO | http://127.0.0.1:9001 | Almacenamiento de objetos |
| MLflow | http://127.0.0.1:5000 | Experimentos y Model Registry (`MLFLOW_TRACKING_URI` para entrenar) |
| PostgreSQL | 127.0.0.1:5433 | Base de datos (`papasana`, `papasana_test`) |

> En Windows use `127.0.0.1` en lugar de `localhost`: algunos clientes intentan primero IPv6 (`::1`) y tardan
> hasta 2 s por conexión, porque los puertos solo se publican en IPv4 local.

## Requisitos

- Docker Desktop (con WSL2) y unos 4 GB de RAM asignados a Docker (`ml-service` usa hasta 1,2 GB).
- Opcional para desarrollo del frontend: Node 22+.

## Instalación

```powershell
# 1. Crear .env con secretos aleatorios (muestra la contraseña de los usuarios demo)
powershell -ExecutionPolicy Bypass -File scripts\init.ps1

# 2. Construir y levantar todo
docker compose up -d --build
```

El servicio `migrate` aplica las migraciones de Alembic y carga los datos semilla antes de iniciar el backend. En desarrollo también genera 48 diagnósticos **de ejemplo** con imágenes sintéticas para que el dashboard y los reportes tengan datos (D-44; se desactiva con `SEED_DEMO_ACTIVITY=false`).

### Usuarios demo (solo `APP_ENV=development`)

La contraseña es el valor de `DEMO_USERS_PASSWORD` en `.env`.

| Rol | Correo | Ve |
|---|---|---|
| Administrador | admin@demo.papasana.pe | Todo, gestión de usuarios, roles y configuración |
| Investigador / Científico de datos | investigador@demo.papasana.pe | Laboratorio, datasets, reportes |
| Especialista agrónomo | agronomo@demo.papasana.pe | Validación por experto, alertas, parcelas (su región) |
| Técnico de campo / Productor | tecnico@demo.papasana.pe | Captura y diagnóstico, parcelas propias |
| Auditor | auditor@demo.papasana.pe | Solo lectura de bitácora y reportes |

## Qué incluye la Fase 4

- **MLflow** (tracking y Model Registry): metadatos en una base propia y artefactos en MinIO. El modelo en uso es el que tiene el alias `production`; si no hay ninguno, ml-service sirve el DEMO.
- **`ml/` (paquete `potato_blight`):**
  - datos: registro de datasets con licencias, deduplicación por SHA-256 y dHash (también entre datasets) y particiones agrupadas sin fuga;
  - modelos: ResNet50, EfficientNet-B3, ConvNeXt-Tiny, H1 (CNN-ViT) y H2 (EfficientNet-Atención-BiLSTM);
  - entrenamiento: Optuna con el mismo presupuesto para todos y calibración por temperatura;
  - evaluación: métricas por clase y curvas; Friedman, Wilcoxon-Holm, McNemar, bootstrap y DeLong;
  - explicabilidad: Grad-CAM, estabilidad, relevancia, SHAP y atención;
  - prueba de humo de punta a punta, copia de runs desde Colab y 4 notebooks.

  Ver la [guía de entrenamiento](docs/guia_entrenamiento.md).
- **Laboratorio de modelos:**
  - versiones sincronizadas desde MLflow;
  - detalle con métricas por partición y por clase, matriz de confusión, curvas ROC y precisión-exhaustividad, fiabilidad (ECE) y curvas de entrenamiento;
  - comparación estadística entre modelos;
  - **promoción y rollback con cuatro ojos:** lo solicita el Investigador y lo aprueba otra persona. Al aprobarse, ml-service recarga el modelo; si falla, se restaura el anterior. Todo queda en la bitácora.
- **Datasets y licencias (A1):** registro con el estado de la licencia. La verificación la registra una persona con el enlace a la fuente oficial, y se exporta `ml/datasets.yaml`. **Ninguna licencia externa está verificada todavía** (D-56).
- No se muestra ninguna métrica que no venga de un run registrado. El DEMO y las pruebas de humo se marcan siempre como no validados.

## Qué incluye la Fase 3

- **Dashboard** (página de inicio de los roles que lo tienen):
  - KPIs: diagnósticos, porcentaje por categoría, pendientes de validación, parcelas con casos compatibles recientes y acuerdo con la validación experta. La precisión del modelo, las alertas y las parcelas en riesgo muestran "—" con el motivo hasta las fases 4 y 5: no se inventan métricas.
  - Tendencia diaria, semanal o mensual, distribución por categoría, región y variedad, y mapa de calor de casos (PostGIS + Leaflet).
  - Filtros globales por fechas, región, parcela y variedad, guardados en la URL. El contenido respeta el alcance del rol.
- **Reportes** en PDF, Word y Excel, con encabezado institucional, fecha de emisión en hora de Lima, usuario emisor, filtros aplicados, versión del modelo, franja DEMO y aviso profesional:
  - **Operacionales:** R-01 diagnósticos por fecha, parcela y técnico · R-02 imágenes procesadas · R-03 casos pendientes de revisión · R-04 alertas emitidas (con datos desde la Fase 5) · R-05 actividad de usuarios.
  - **De gestión:** R-06 incidencia por región y variedad · R-07 tendencias · R-08 desempeño y deriva de los modelos · R-09 tiempos de respuesta · R-10 uso del sistema.
  - **Auditoría:** B-01 exportación de la bitácora, con la verificación de la cadena de hash. Se lanza desde el módulo Bitácora.
  - Se generan en segundo plano (Celery), se guardan en MinIO y se descargan desde el historial. La solicitud y cada descarga quedan en la bitácora.
- **Notificaciones internas (A4):** campana con las no leídas. Avisa de reportes listos o con error y de casos nuevos pendientes de validación (al especialista de la región; en los lotes, un solo aviso).

## Qué incluye la Fase 2

- **Parcelas:** polígonos dibujados sobre OpenStreetMap, validados y medidos con PostGIS; productor, variedad, fecha de siembra, estadio fenológico y altitud; asignación de técnicos. Alcance por rol: el técnico ve sus parcelas asignadas, el agrónomo las de su región y el resto, todas.
- **Catálogos:** variedades, estadios fenológicos, enfermedades diferenciales (con el tizón tardío marcado como objetivo) e importación de provincias y distritos (CSV de ubigeo).
- **Captura y diagnóstico:** una foto (resultado inmediato) o un lote (en segundo plano con Celery). Se valida el archivo, se extrae el EXIF/GPS (o la ubicación del dispositivo), se comprueba si el punto cae dentro de la parcela y se detectan duplicados exactos (se rechazan) y casi duplicados (dHash).
- **Modelo DEMO:** ResNet50 con pesos ImageNet y una cabeza de 3 clases **sin entrenar**. Todas las pantallas muestran la franja **DEMO / no validado**. Devuelve probabilidades calibradas por temperatura y el mapa Grad-CAM.
- **Etiquetas por síntoma (D-01):** Sano / Sospechoso / Tizón tardío: síntomas compatibles. Si la confianza es menor que el umbral configurable, el caso **requiere revisión**.
- **Validación por experto:** bandeja ordenada por prioridad. "Tizón tardío confirmado" exige evidencia; "otra enfermedad" exige indicar el diferencial. Todo queda en la bitácora.
- **Datos de ejemplo:** 3 parcelas ficticias en el valle del Mantaro (Junín), 2 de ellas asignadas al técnico demo, y 1 en Chinchero (Cusco), fuera de la región del agrónomo demo.

## Qué incluye la Fase 1

- **Autenticación:** JWT de acceso (15 min, en memoria) y refresh rotativo (7 días, cookie `httpOnly` + `SameSite=Strict`) con detección de reutilización; Argon2id; bloqueo tras 5 intentos; recuperación por correo; cambio de contraseña (cierra las otras sesiones); cierre por inactividad en cliente y servidor.
- **RBAC granular:** 14 módulos × 6 acciones, roles configurables desde la interfaz (matriz editable), alcance de datos por rol. El backend valida cada endpoint y registra los accesos denegados.
- **Bitácora inmutable:** login, logout, intentos fallidos, bloqueos, expiración de sesión, entrada y salida de módulos con duración (cambio de ruta, pestaña oculta y cierre vía `sendBeacon`, logout, inactividad) y cada acción con valores antes/después, IP y user-agent. Hash SHA-256 encadenado calculado por trigger; UPDATE, DELETE y TRUNCATE bloqueados por trigger y por permisos. Verificación de integridad desde la interfaz.
- **Usuarios y perfil:** CRUD, desbloqueo, envío de enlace de restablecimiento, foto de perfil (se re-codifica y se eliminan metadatos EXIF/GPS), región asignada.
- **Configuración del sistema (A2):** umbral de revisión, parámetros de seguridad, textos institucionales y aviso de supervisión.
- Los módulos de fases posteriores ya aparecen en el menú según permisos y muestran "Disponible en la Fase N".

## Pruebas

```powershell
# Backend (pytest contra PostgreSQL real, base papasana_test) con cobertura
docker compose run --rm backend pytest --cov

# Entrenamiento (ml/): ver docs/guia_entrenamiento.md
cd ml; python -m pytest

# Servicio de inferencia (PyTorch)
docker compose run --rm --no-deps ml-service pytest

# Frontend (Vitest + Testing Library)
cd frontend; npm install; npm test
```

## Desarrollo del frontend con recarga en caliente

```powershell
cd frontend
npm install
npm run dev      # http://localhost:5173, con proxy /api → backend en :8000
```

## Estructura

```
backend/     FastAPI, SQLAlchemy 2 + GeoAlchemy2, Alembic, Celery, pruebas
ml-service/  Inferencia PyTorch (modelo DEMO) y Grad-CAM
frontend/    React 18 + TypeScript + Vite + MUI
infra/       Imagen de PostgreSQL 16 + PostGIS + pgvector e inicialización
scripts/     init.ps1 (genera .env)
backend/app/reports/  Definición de los reportes (una sola por reporte) y renderers PDF, Word y Excel
ml/          Entrenamiento y evaluación (potato_blight), datasets.yaml, configs, notebooks
docs/        Plan (Fase 0), decisiones, modelo de datos
```

## Seguridad

- Secretos solo en `.env` (nunca en el repositorio; `.env.example` no tiene valores).
- Puertos publicados solo en `127.0.0.1`.
- Usuario de base de datos de la aplicación con privilegios mínimos (sin UPDATE/DELETE en la bitácora); migraciones con un usuario propietario distinto.
- Rate limiting en login, refresh y recuperación; mensajes de error que no revelan si un correo existe.
- CSP, `X-Frame-Options`, `nosniff` y `Referrer-Policy` en Nginx.
- Fotos de perfil validadas con Pillow, limitadas a 2 MB y re-codificadas.
