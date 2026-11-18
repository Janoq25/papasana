# Prompt: Sistema de detección temprana del tizón tardío de la papa (AP-01)

## 1. Rol

Actúa como un **arquitecto y desarrollador full-stack senior** especializado en aplicaciones de **agricultura de precisión y salud pública**, con experiencia en visión artificial (PyTorch/TensorFlow), MLOps (MLflow, Optuna), orquestación con **n8n**, agentes y RAG con **LangChain** y prototipado de flujos LLM con **LangFlow**.

## 2. Contexto

Lee completo el archivo @contexto.md antes de escribir código. **Implementa solo el proyecto AP-01** ("Multimodal Explainable Deep Learning for Early Detection of Potato Late Blight Under Real Field Conditions"). Las demás secciones (revistas, otros proyectos SP/AP, priorización) son referencia y **no** deben implementarse. De las secciones 5 y 6 toma la arquitectura, los workflows n8n WF-01 a WF-06, el protocolo experimental, las métricas y las restricciones de uso del LLM.

**Objetivo de la aplicación:** que un técnico de campo o un agrónomo suba fotografías de hojas de papa tomadas en campo y reciba:

- una clasificación en tres clases: `sano`, `sospechoso / tizón temprano de infección` y `tizón tardío confirmado`;
- el nivel de confianza;
- un mapa Grad-CAM que muestre en qué zona de la hoja se basó el modelo;
- una explicación y recomendaciones con fuentes verificables.

Todo queda georreferenciado, auditado y disponible en reportes.

## 3. Stack tecnológico (obligatorio)

| Capa | Tecnología |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic, Celery + Redis para tareas asíncronas |
| Base de datos | PostgreSQL 16 + PostGIS |
| Almacenamiento de objetos | MinIO (imágenes, mapas Grad-CAM, reportes generados) |
| IA / ML | PyTorch (modelos), scikit-learn (métricas), Optuna, SHAP, Grad-CAM, MLflow (registro de modelos) |
| LLM | LangChain (agente + RAG con pgvector), LangFlow (prototipos de flujos) |
| Orquestación | n8n (workflows WF-01 a WF-06, exportados como JSON en el repositorio) |
| Frontend | React 18 + TypeScript + Vite, React Router, TanStack Query, una librería de componentes para el panel administrativo (MUI o Ant Design: elige una y justifícala), Recharts, React-Leaflet |
| Reportes | PDF (WeasyPrint o ReportLab), Word (python-docx), Excel (openpyxl/XlsxWriter) |
| Despliegue | Docker + docker-compose (un solo `docker compose up` levanta todo) |

## 4. Módulos requeridos

### 4.1 Seguridad, usuarios, roles y perfiles
- Autenticación JWT (access + refresh), contraseñas con Argon2/bcrypt, bloqueo tras N intentos fallidos, cambio y recuperación de contraseña.
- **RBAC granular:** permisos por *módulo × acción* (ver, crear, editar, eliminar, exportar, aprobar). Los roles son configurables desde la interfaz.
- Roles semilla: `Administrador`, `Investigador / Científico de datos`, `Especialista agrónomo`, `Técnico de campo / Productor`, `Auditor` (este último con acceso de solo lectura a la bitácora y los reportes).
- Perfil de usuario: datos personales, institución, región asignada, foto y preferencias.
- El frontend oculta menús y botones según los permisos; el backend **siempre** valida los permisos en cada endpoint.

### 4.2 Bitácora de auditoría (crítico)
- Registra **inicio y cierre de sesión**, **entrada y salida de cada módulo** (con hora de entrada, hora de salida y duración de la permanencia) y cada acción relevante (CRUD, exportaciones, diagnósticos, cambios de permisos, promoción de modelos).
- Campos mínimos: usuario, rol, módulo, acción, ruta/endpoint, entidad afectada y su ID, valores antes/después (JSON), IP, user-agent, timestamp con zona horaria (America/Lima) y resultado (éxito/fallo).
- Detección de salida de módulo: cambio de ruta en React, cierre de pestaña (`visibilitychange` / `beforeunload` con `navigator.sendBeacon`), logout y expiración de sesión por inactividad.
- **Inmutable:** tabla append-only (un trigger impide UPDATE y DELETE) y hash encadenado entre registros para detectar manipulaciones.
- Pantalla de consulta con filtros (usuario, módulo, acción, rango de fechas), línea de tiempo por usuario y exportación a PDF, Word y Excel.

### 4.3 Dashboard
- KPIs: diagnósticos realizados, porcentaje por clase, alertas activas, parcelas en riesgo, precisión del modelo en producción y casos pendientes de validación por un experto.
- Gráficos de tendencia temporal, distribución por región y variedad, y un mapa de calor de casos (PostGIS + Leaflet).
- Filtros globales por fecha, región, parcela y variedad. El contenido se adapta al rol del usuario.

### 4.4 Gestión de parcelas y catálogos
- Parcelas con polígono georreferenciado, productor, variedad, fecha de siembra y estadio fenológico.
- Catálogos: variedades de papa, estadios fenológicos, regiones/ubigeo del Perú y enfermedades diferenciales.

### 4.5 Captura de imágenes y diagnóstico
- Carga individual o por lote desde web o móvil (diseño responsive), con extracción de EXIF/GPS, deduplicación por hash perceptual y registro de procedencia.
- La inferencia se ejecuta vía FastAPI con el modelo marcado como "producción" en MLflow. Devuelve la clase, las probabilidades calibradas, la superposición Grad-CAM y la versión del modelo.
- Si la confianza está por debajo de un umbral configurable, el caso se marca como **"requiere revisión"**.
- **Validación por experto (human-in-the-loop):** el especialista confirma o corrige la etiqueta. Esas etiquetas validadas alimentan futuros reentrenamientos.

### 4.6 Laboratorio de modelos (MLOps)
- Registro y comparación de los 5 modelos del contexto: ResNet50, EfficientNetB3, ConvNeXt, CNN-ViT (H1) y EfficientNet-Attention-BiLSTM (H2).
- Scripts y notebooks de entrenamiento **separados de la aplicación**, en `ml/`. Requisitos:
  - división agrupada por planta, parcela o procedencia (sin fuga de información);
  - validación externa entre datasets (por ejemplo, entrenar con PlantVillage y probar con PlantDoc);
  - Optuna con TPE y un pruner, con presupuesto computacional comparable entre los cinco modelos.
- Vista de métricas: precisión, sensibilidad, especificidad, F1, MCC, AUC-ROC, AUC-PR, matriz de confusión, curvas ROC/PR y calibración.
- Pruebas estadísticas: Friedman, Wilcoxon con corrección de Holm, McNemar, intervalos de confianza por bootstrap y DeLong.
- Promoción y retroceso (rollback) de versiones de modelo, siempre registrados en la bitácora.

### 4.7 Riesgo climático y alertas
- Integración de datos meteorológicos mediante n8n (WF-01): temperatura y humedad relativa.
- Índice de riesgo de *Phytophthora infestans* con reglas configurables (por ejemplo, criterios tipo Hutton/Smith).
- Las alertas combinan diagnósticos positivos con el riesgo climático, por parcela o región, y se envían por correo o Telegram vía n8n (WF-04).

### 4.8 Asistente IA (LangChain + RAG)
- RAG sobre documentos técnicos de FAO, SENASA e INIA cargados por el administrador, con indexación en pgvector.
- Funciones: explicar un diagnóstico, interpretar el mapa de riesgo y sugerir medidas de manejo **citando la fuente y la página**.
- Guardrails: el LLM es una interfaz de consulta y explicación, **nunca sustituye al modelo validado** ni al profesional. Todas las respuestas muestran un aviso de supervisión profesional, y las respuestas sin evidencia recuperada lo declaran explícitamente.
- Proveedor de LLM configurable por variable de entorno.

### 4.9 Reportes (PDF, Word y Excel)
- **Operacionales:** diagnósticos por fecha, parcela y técnico; imágenes procesadas; casos pendientes de revisión; alertas emitidas; actividad de usuarios.
- **De gestión:** incidencia por región y variedad, tendencias, desempeño y deriva de los modelos, tiempos de respuesta, uso del sistema.
- Cada reporte incluye filtros parametrizables, encabezado institucional, fecha de emisión, usuario emisor y la versión del modelo.
- Los reportes pesados se generan en segundo plano (Celery) y se descargan desde un historial. También pueden programarse con n8n (WF-05).

### 4.10 Workflows n8n
Implementa WF-01 a WF-06 tal como se describen en el contexto. Expórtalos como JSON en `n8n/workflows/` y documenta cada disparador, entrada y salida. Se integran con el backend mediante endpoints protegidos por API key o token de servicio.

### 4.11 Módulos adicionales
Puedes proponer módulos adicionales que aporten valor real (por ejemplo: notificaciones internas, configuración del sistema, monitoreo de deriva de datos, gestión de datasets y licencias, modo offline para campo). **Justifica cada uno en el plan antes de implementarlo.**

## 5. Requisitos no funcionales
- Arquitectura en capas en el backend (routers → services → repositories), con tipado estricto y manejo centralizado de errores.
- Seguridad según OWASP Top 10: validación de entradas, límites de tamaño y tipo de archivo, CORS restringido, rate limiting y secretos en `.env` (incluye `.env.example`, nunca valores reales).
- Pruebas: pytest para el backend (cobertura mínima del 70 % en services y permisos) y Vitest + Testing Library para los componentes críticos del frontend.
- Datos semilla: usuarios demo de cada rol, catálogos y parcelas de ejemplo.
- Interfaz en español (es-PE), responsive y accesible (WCAG AA básico).
- Documentación: `README.md` con arquitectura, instalación y uso; diagrama entidad-relación; OpenAPI automática; guía para entrenar y registrar modelos.

## 6. Restricciones científicas (no negociables)
- **No inventes métricas ni resultados.** Mientras no existan pesos entrenados, usa un modelo base claramente etiquetado como `DEMO / no validado` en la interfaz y en los reportes.
- No mezcles imágenes aumentadas ni fotos de la misma planta o parcela entre entrenamiento y prueba.
- Si los datasets no tienen confirmación etiológica, usa etiquetas de **síntoma**, no de patógeno, y refléjalo en la interfaz.
- Respeta las licencias de los datasets (PlantVillage, PlantDoc, Kaggle). No descargues nada sin documentar la licencia.
- La aplicación es una **herramienta de apoyo a la decisión**, no un diagnóstico definitivo.

## 7. Forma de trabajo
1. **Fase 0 (planificación). No escribas código todavía.** Entrega:
   - arquitectura (diagrama),
   - modelo de datos (tablas principales y relaciones),
   - estructura de carpetas del monorepo (`backend/`, `frontend/`, `ml/`, `n8n/`, `langflow/`, `docs/`, `docker-compose.yml`),
   - matriz de roles × permisos,
   - lista de módulos con su justificación,
   - plan de implementación por fases.

   **Espera mi aprobación antes de continuar.**
2. Implementa por fases incrementales y verificables:
   1. infraestructura Docker + base de datos + autenticación/RBAC + bitácora;
   2. parcelas, imágenes y diagnóstico;
   3. dashboard y reportes;
   4. MLOps y laboratorio de modelos;
   5. n8n, alertas y riesgo climático;
   6. asistente RAG.
3. Al cerrar cada fase:
   - ejecuta las pruebas y verifica que los servicios levantan;
   - muéstrame un resumen de lo hecho, cómo probarlo y los pendientes;
   - **detente para mi revisión**.
4. Si una especificación es ambigua, toma una decisión razonable, regístrala en `docs/decisiones.md` y continúa. Pregúntame solo cuando la decisión cambie de forma importante el alcance.

## 8. Criterios de aceptación
- [ ] `docker compose up` levanta todos los servicios sin errores.
- [ ] Un usuario de cada rol puede iniciar sesión y solo ve lo que su rol permite.
- [ ] La bitácora registra login, logout, entrada y salida de módulos (con su duración) y las acciones, y no puede modificarse.
- [ ] Al subir una imagen se obtienen la clase, la confianza y el Grad-CAM, y el resultado queda registrado con la versión del modelo.
- [ ] El dashboard muestra KPIs, gráficos y el mapa con datos semilla.
- [ ] Cada reporte operacional y de gestión se exporta correctamente en PDF, Word y Excel.
- [ ] Los workflows WF-01 a WF-06 son importables en n8n y funcionan contra el backend.
- [ ] El asistente RAG responde citando fuentes y con el aviso de supervisión profesional.
- [ ] Las pruebas pasan y el README permite a un tercero reproducir la instalación.
