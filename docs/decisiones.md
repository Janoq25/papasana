# Registro de decisiones — AP-01

Este archivo cumple la regla §7.4 de la especificación: cuando algo es ambiguo se toma una decisión razonable, se registra aquí y se continúa.

**Estados:** ✅ tomada · ⚠ requiere aprobación (cambia el alcance, un criterio de aceptación o la metodología del artículo)

---

## D-01 ✅ Esquema de etiquetas por síntoma y "confirmado" solo por experto (aprobada el 2026-11-04)

- **Contexto:** la especificación pide las clases `sano`, `sospechoso / tizón temprano de infección` y `tizón tardío confirmado`. En PlantVillage y Kaggle, *Early blight* es **otra enfermedad** (*Alternaria solani*), no la fase inicial del tizón tardío. Además, ningún dataset público confirma la etiología.
- **Decisión propuesta:**
  - el modelo predice `sano` / `sintomas_compatibles_tizon_tardio` / `otra_enfermedad_foliar`;
  - la interfaz muestra **Sano / Sospechoso / Tizón tardío: síntomas compatibles**;
  - el estado **"confirmado"** solo lo asigna un especialista en la validación por experto.
- **Consecuencia:** la interfaz mantiene las tres categorías, se cumple la restricción científica §6 y el diagnóstico diferencial pasa a ser un aporte del trabajo.

## D-02 ✅ MUI como librería de componentes

- **Alternativas:** MUI y Ant Design.
- **Elegida:** MUI con MUI X DataGrid (versión comunitaria) y Date Pickers.
- **Razones:**
  - mejor soporte de accesibilidad (roles ARIA, foco, contraste configurable), que ayuda con el requisito WCAG AA;
  - tiene locale `esES` y es fácil de adaptar a es-PE (formato de fechas con dayjs);
  - el tema es flexible para el encabezado institucional;
  - la comunidad es grande y se integra sin problemas con React 18 + TypeScript.
- Ant Design tiene tablas y formularios muy completos, pero su accesibilidad y su personalización visual son más limitadas.

## D-03 ✅ LangFlow en el perfil `lab` de docker-compose (aprobada el 2026-11-04)

- **Contexto:** el equipo de desarrollo tiene 7,6 GB de RAM. LangFlow consume entre 1 y 1,5 GB y no forma parte del flujo de producción (solo sirve para prototipar).
- **Decisión propuesta:**
  - `docker compose up` levanta todos los servicios de la aplicación;
  - LangFlow se levanta aparte con `docker compose --profile lab up`.
- **Impacto:** el criterio de aceptación "un solo `docker compose up` levanta todo" se cumple para la aplicación, pero no para la herramienta de prototipado. En un servidor con más RAM basta con quitar el perfil.

## D-04 ✅ Python 3.12 dentro de los contenedores

- Python 3.14 (el instalado en el equipo) puede no tener todavía ruedas de PyTorch y de algunas librerías científicas.
- Las imágenes Docker usan Python 3.12, que cumple el "3.11+" de la especificación.

## D-05 ✅ Proveedor de LLM y embeddings (aprobada el 2026-11-04: Gemini)

- **LLM:** Google Gemini API, por elección del usuario.
  - `.env.example`: `LLM_PROVIDER=google`, `LLM_MODEL=gemini-3.6-flash`, `LLM_API_KEY=`.
  - Integración con `langchain-google-genai`.
  - `gemini-3.6-flash` figura como **estable** en la [lista oficial de modelos](https://aistudio.google.com/docs/models) consultada el 2026-11-04. Se usa un ID fijo en lugar de un alias `-latest`, para que los resultados sean reproducibles. `gemini-3.5-flash-lite` es la alternativa más barata.
  - Antes de la Fase 6 se revisa la [página de retiro de modelos](https://ai.google.dev/gemini-api/docs/deprecations). `gemini-2.5-flash` y `gemini-2.5-pro` ya están marcados como obsoletos.
  - La fábrica `llm_factory` sigue aceptando otros proveedores, así que cambiar de proveedor no toca el resto del código.
- **Embeddings:** se calculan en local con `intfloat/multilingual-e5-small` (384 dimensiones) dentro de `ml-service`. Así se evitan costos y los documentos no salen del servidor al indexarlos.
- **Sin API key:** el asistente funciona en modo "solo recuperación", es decir, muestra los fragmentos citados sin redactar una respuesta.

## D-06 ✅ Qué "secuencia" procesa el modelo H2 (EfficientNet-Attention-BiLSTM) (aprobada el 2026-11-04)

- **Contexto:** `contexto.md` dice "secuencias de observaciones", pero los datasets públicos son imágenes sueltas.
- **Decisión propuesta:**
  - con datos públicos, la BiLSTM procesa la **secuencia de mapas de características espaciales** (filas o parches de la salida de EfficientNet) con atención;
  - con datos propios de la aplicación (varias fotos de la misma parcela a lo largo del tiempo), se evalúa una variante **temporal** como trabajo futuro o como experimento adicional.
- **Impacto:** la metodología del artículo debe describirlo con honestidad.

## D-07 ✅ Alcance de "multimodal" y nuevo título (aprobada el 2026-11-04)

- **Contexto:** los datasets públicos de imágenes no traen datos meteorológicos asociados, así que no se puede entrenar un modelo que fusione imagen y clima con datos públicos.
- **Decisión propuesta:**
  - la multimodalidad del **sistema** es una **fusión tardía** (*late fusion*) entre el diagnóstico por imagen y el riesgo climático, a nivel de alerta;
  - con datos propios georreferenciados y fechados, la fusión dentro del modelo queda como experimento futuro.
- **Impacto:** afecta la redacción del título y la contribución del artículo. Conviene revisarlo con tu asesor.
- **Resolución:** el usuario aprobó cambiar el título. Título de trabajo:
  - **EN:** *Explainable Deep Learning for Symptom-Based Detection of Potato Late Blight Under Field Conditions, Integrated with Climate-Based Risk Alerts*
  - **ES:** *Aprendizaje profundo explicable para la detección por síntomas del tizón tardío de la papa en condiciones de campo, integrado con alertas de riesgo climático*
- **Qué cambia respecto del original:**
  - se quita **"Multimodal"**, porque la fusión es del sistema y no del modelo;
  - **"Early Detection"** pasa a **"Symptom-Based Detection"**, porque no hay datos de infección temprana confirmada;
  - se añade **"Climate-Based Risk Alerts"**, que es donde está la parte de alerta temprana.
- Si en una etapa posterior se consiguen imágenes propias georreferenciadas con datos de clima y se entrena un modelo de fusión, se puede recuperar el término "multimodal".
- `contexto.md` conserva el título original como documento de referencia.

## D-08 ✅ Un solo framework de deep learning: PyTorch

- `contexto.md` menciona TensorFlow/Keras y PyTorch.
- Se usa solo PyTorch con `timm`, `pytorch-grad-cam` y `shap`, para simplificar el entorno, la inferencia y la comparación justa entre los cinco modelos.

## D-09 ✅ Promoción de modelos con cuatro ojos

- El rol Investigador registra y propone una versión.
- El Administrador aprueba la promoción a *Production* o el rollback.
- Ambos pasos quedan en `model_promotions` y en la bitácora.

## D-10 ✅ Un rol por usuario

- Simplifica la bitácora (el campo `role_code` del evento es único) y la matriz de permisos.
- Si un usuario necesita permisos combinados, se crea un rol a medida desde la interfaz.

## D-11 ✅ Datos meteorológicos de Open-Meteo

- Es gratuito, no requiere API key y ofrece temperatura, humedad relativa y precipitación horarias por coordenada.
- Las condiciones de uso y la atribución se verifican y se documentan en la Fase 5.
- SENAMHI se puede añadir como fuente adicional si su acceso lo permite.

## D-12 ✅ Sin borrado físico de datos de diagnóstico

- "Eliminar" un diagnóstico o una imagen significa **anularlo con un motivo**.
- Esto preserva la trazabilidad científica y es coherente con la bitácora inmutable.

## D-13 ✅ SHAP solo fuera de línea

- Grad-CAM se calcula en cada inferencia.
- SHAP y los mapas de atención se calculan en `ml/` (laboratorio), porque su costo computacional no es aceptable en cada petición.

## D-14 ✅ Servicio de inferencia separado (`ml-service`)

- Aísla PyTorch (unos 900 MB) del backend.
- Permite usar GPU de forma opcional y reiniciarlo al promover un modelo.
- También concentra los embeddings, para no cargar PyTorch en dos procesos.

## D-15 ✅ Correo de desarrollo con Mailpit y Telegram opcional

- En desarrollo, todos los correos (recuperación de contraseña, alertas, reportes) se capturan en Mailpit (`http://localhost:8025`).
- Telegram se activa si se configura `TELEGRAM_BOT_TOKEN`.

## D-16 ✅ Definición del modelo DEMO

- Es un backbone preentrenado en ImageNet con una cabeza sin entrenar para las 3 clases.
- Se marca `is_demo = true` y la marca se propaga a la API, la interfaz y los reportes.
- Nunca se muestran métricas para este modelo.

## D-17 ✅ Esquemas de PostgreSQL por dominio

- Los esquemas son `seguridad`, `auditoria`, `catalogo`, `campo`, `ml`, `clima`, `rag` y `reportes`.
- Permiten permisos de base de datos diferenciados (por ejemplo, solo `INSERT`/`SELECT` en `auditoria`).

## D-18 ✅ Nombre de trabajo "PapaSana AP-01"

- Es provisional y se puede cambiar en la configuración (encabezado de la interfaz y de los reportes).

## D-19 ✅ Dataset Kaggle `abbasataiemontazer/potato-leaf`: descartado como fuente

- **Revisión del 2026-11-04** (metadatos y listado completo de archivos obtenidos de la API pública de Kaggle, sin descargar las imágenes):
  - **Licencia:** "Unknown". No hay descripción, cita ni fuente declarada. Usabilidad 0,31/1. Una sola versión, del 2019-12-08.
  - **Contenido:** 1.500 imágenes (unos 26 MB): 500 de `Early_blight`, 500 de `Late_blight` y 500 de `healthy`. Ya vienen divididas en 300 de entrenamiento, 100 de validación y 100 de prueba por clase.
  - **Procedencia:** los nombres de los archivos de las clases enfermas (`<uuid>___RS_Early.B 7136.JPG`, `<uuid>___RS_LB ...`) son los de **PlantVillage**. Es decir, se trata de un subconjunto de PlantVillage tomado en laboratorio.
  - **Clase `healthy`:** sus 500 imágenes salen de **solo 125 fotos originales con 4 copias aumentadas cada una** (patrón de nombre `Potato_healthy-<id>-_0_<n>.jpg`, el que genera la exportación de aumento de datos de Keras). Las clases enfermas no están aumentadas. No se detectó que un mismo original aparezca en dos particiones distintas.
- **Problemas:**
  1. Sin licencia explícita no hay permiso documentado de uso. Eso incumple la restricción §6 de la especificación.
  2. Al ser un subconjunto de PlantVillage, no aporta información nueva. Además, **no sirve como validación externa**: probar con él un modelo entrenado en PlantVillage sería una fuga de información.
  3. Que solo la clase sana esté aumentada es un **sesgo artificial**: el modelo podría aprender a reconocer los artefactos del aumento en lugar de la hoja (*shortcut learning*).
  4. Son condiciones de laboratorio, mientras que el título apunta a condiciones de campo.
  5. Su `Early_blight` es *Alternaria solani*, el mismo problema descrito en D-01.
- **Decisión:** no se usa ni para entrenar ni para validar. En su lugar se trabaja con PlantVillage desde su fuente original, con la licencia verificada. Su lista de archivos sirve como referencia para **excluir duplicados** si otro dataset de Kaggle incluye las mismas imágenes.

## D-20 ✅ Datos que se envían a Gemini según el nivel del servicio

- Según los [términos de la API de Gemini](https://aistudio.google.com/docs/terms) consultados el 2026-11-04:
  - en el **nivel gratuito**, Google puede usar las entradas y salidas para mejorar sus productos, y revisores humanos pueden leerlas. Los términos piden no enviar información sensible, confidencial ni personal;
  - en el **nivel de pago**, Google no usa los prompts ni las respuestas para mejorar sus productos.
- **Decisión:**
  - el nivel gratuito se usa **solo con datos demo**;
  - con datos reales de productores o de parcelas se usa una API key del nivel de pago;
  - el backend **no envía** a Gemini nombres de productores, coordenadas exactas ni fotos. Solo envía los fragmentos documentales recuperados y un resumen anonimizado del diagnóstico (clase, confianza, región a nivel de provincia y riesgo).
- Los embeddings siguen siendo locales (D-05), así que los documentos indexados no salen del servidor.

---

# Decisiones tomadas durante la Fase 1

## D-21 ✅ Imagen de MinIO: compilación de Chainguard

- La imagen `minio/minio` ya no se publica en Docker Hub ("repository does not exist"), y `quay.io/minio/minio` pide autenticación.
- Se usa `cgr.dev/chainguard/minio:latest`, que es MinIO compilado desde el código fuente. La versión verificada el 2026-11-04 fue `RELEASE.2026-10-23T20-06-51Z`, con licencia AGPLv3.
- Esta imagen corre con el UID 65532. Un servicio de un solo uso (`minio-volume-init`) ajusta una vez el propietario del volumen.
- La API S3 es la misma, así que no cambia nada en el backend.

## D-22 ✅ Imagen de PostgreSQL: `postgres:16-bookworm` + PostGIS + pgvector

- Las imágenes `postgis/postgis:16-3.4` y `16-3.5` se basan en Debian bullseye, y su repositorio PGDG ya fue archivado, así que `apt-get` falla al instalar pgvector.
- Se usa la imagen oficial `postgres:16-bookworm` y se instalan `postgresql-16-postgis-3` y `postgresql-16-pgvector` desde PGDG. Versiones verificadas: PostGIS 3.7.0 y pgvector 0.8.7.

## D-23 ✅ SQLAlchemy síncrono con psycopg 3

- FastAPI ejecuta los endpoints síncronos en un pool de hilos. Esto simplifica las transacciones, las pruebas (cada prueba corre en una transacción que se revierte) y el código compartido con Celery.
- La concurrencia esperada en el prototipo no justifica la complejidad de `asyncio` con SQLAlchemy.

## D-24 ✅ La cadena de hash se calcula en PostgreSQL

- El trigger BEFORE INSERT calcula `seq`, `prev_hash` y `hash`. Así ningún camino de código (ni un INSERT manual) puede crear un registro sin encadenarlo.
- `seq` se asigna dentro del bloqueo consultivo, en lugar de usar `id`, porque con transacciones concurrentes el orden de los `id` no coincide con el orden de commit.
- **Limitación:** el truncado de la cola no se detecta solo con la cadena. En la Fase 5, WF-06 guardará un anclaje externo diario (último `seq` y `hash`).

## D-25 ✅ El beacon de salida de módulo se autentica con la cookie de refresh

- `navigator.sendBeacon` no permite enviar la cabecera `Authorization`. Por eso la cookie `ps_refresh` se emite con `path=/api/v1`, y `POST /api/v1/audit/beacon` identifica la sesión con ella.
- `SameSite=Strict` impide que otro sitio dispare el beacon con la cookie del usuario.
- El endpoint solo acepta eventos de salida de la propia sesión y es idempotente.

## D-26 ✅ Desactivar cuentas en lugar de borrarlas

- "Eliminar" un usuario equivale a desactivarlo (requiere `usuarios:eliminar`) y revoca todas sus sesiones.
- Los registros de la bitácora y de diagnóstico conservan su referencia.
- Reglas adicionales:
  - un administrador no puede desactivarse ni cambiar su propio rol;
  - siempre debe quedar al menos un Administrador activo;
  - el rol Administrador no puede perder `usuarios:ver` ni `usuarios:editar`.

## D-27 ✅ Las dependencias de desarrollo van en la imagen del backend

- La imagen `papasana/backend:dev` incluye pytest y ruff, para poder ejecutar `docker compose run --rm backend pytest` sin instalar Python 3.12 en Windows.
- Para producción se separará en una etapa sin dependencias de desarrollo.

## D-28 ✅ Página de inicio por rol

- Tras el login, cada rol va al primer módulo permitido que ya está implementado (por ejemplo, el Auditor va a la Bitácora).
- Desde la Fase 3, el Dashboard será la página de inicio de los roles que lo tengan.

---

# Decisiones tomadas durante la Fase 2

## D-29 ✅ Duplicados: exactos se rechazan, casi duplicados se marcan

- **Duplicado exacto** (mismo SHA-256 en la misma parcela): se rechaza con `409`, indicando el diagnóstico existente.
- **Casi duplicado** (distancia de Hamming del hash perceptual ≤ `diagnostico.distancia_duplicado`, 6 por defecto): se acepta, pero queda marcado en `duplicate_of_id`.
  - Puede ser la misma hoja fotografiada dos veces, así que el caso se conserva.
  - En la Fase 4 se excluirá de los datos de reentrenamiento y de la evaluación, para evitar fugas de información (§6 de la especificación).

## D-30 ✅ Hash perceptual dHash de 64 bits

- Se usa *difference hash* (dHash) en lugar de pHash (DCT), porque solo necesita Pillow, sin numpy ni scipy en el backend.
- Es robusto a cambios de brillo, compresión y escala, que son los casos típicos de reenvío de una misma foto.
- La distancia se calcula en PostgreSQL con `bit_count(phash XOR h)`.

## D-31 ✅ El servicio de inferencia no tiene estado

- El backend envía los bytes de la imagen a `ml-service`, y este devuelve las probabilidades, la clase, la confianza y la superposición Grad-CAM en PNG (base64).
- El backend guarda el Grad-CAM en MinIO. Así `ml-service` no necesita credenciales de MinIO ni de la base de datos, y no publica ningún puerto.
- Lo protege un token interno (`ML_SERVICE_TOKEN`).

## D-32 ✅ Grad-CAM propio, sin dependencias extra

- Grad-CAM se implementa con *hooks* de PyTorch sobre `layer4` de ResNet50, con un mapa de color "jet" propio. No se usan matplotlib ni pytorch-grad-cam, para reducir el tamaño de la imagen y la RAM.
- Las inferencias se serializan con un *lock*, porque los hooks guardan estado.
- En la Fase 4 se generalizará a la última capa convolucional de cada uno de los 5 modelos.

## D-33 ✅ Ubigeo: departamentos sembrados, provincias y distritos por importación CSV

- Solo se siembran los 25 departamentos, cuyos códigos son conocidos.
- Las provincias y distritos se importan desde un CSV (`ubigeo`, `nombre`) desde Catálogos. La fuente y la licencia del archivo las documenta quien lo importa.
- No se incluyeron códigos de provincias o distritos escritos a mano, para no introducir errores.
- El alcance por región usa los dos primeros dígitos del ubigeo (el departamento).

## D-34 ✅ react-leaflet 4.2.1

- react-leaflet 5 exige React 19, y el stack fijado es React 18. Se usa la 4.2.1, la última compatible.
- El dibujo de polígonos es un editor propio (clic para agregar vértices, deshacer, limpiar, detección de lados que se cruzan), sin plugins.
- PostGIS valida de nuevo la geometría (`ST_IsValid`, límites del Perú, área máxima de 2000 ha) y calcula el área oficial.

## D-35 ✅ Mosaicos de OpenStreetMap

- Los mosaicos se cargan desde `tile.openstreetmap.org`, con atribución visible.
- Para un uso con muchos usuarios habrá que usar un proveedor propio o un servidor de mosaicos, como pide la política de uso de OSM.

## D-36 ✅ Carga en lote en segundo plano

- Una sola foto se procesa de forma síncrona y el resultado es inmediato.
- Varias fotos (hasta `diagnostico.max_imagenes_lote`, 20 por defecto) se guardan primero y luego el worker de Celery las procesa (`diagnostico.procesar_imagen`).
  - Si `ml-service` no responde, se reintenta 3 veces y el fallo solo se cuenta en el último intento.
  - Las tareas son idempotentes.
- El frontend consulta el avance cada 2 s.
- El límite de Nginx sube a 120 MB por petición. Cada foto sigue limitada a 15 MB.

## D-37 ✅ Ubicación de la foto: EXIF > dispositivo > ninguna

- Se usa el GPS del EXIF si existe. Si no, la ubicación del navegador, si el usuario la autoriza.
- Se guarda el origen (`gps_source`) y si el punto cae dentro del polígono de la parcela (`inside_parcel`, con `ST_Contains`) como control de calidad.
- La foto original se guarda intacta en MinIO por trazabilidad científica. Solo se accede a ella mediante el backend, con permisos y según el alcance del rol.

## D-38 ✅ Sin borrado de diagnósticos, imágenes ni revisiones

- Al usuario de la aplicación se le revoca `DELETE` y `TRUNCATE` sobre `campo.diagnoses`, `campo.images` y `campo.expert_reviews` (refuerza D-12).
- Anular un diagnóstico requiere `diagnostico:eliminar` y un motivo, y queda en la bitácora.

## D-39 ✅ Decisión del especialista derivada de la etiqueta final

- El especialista elige la etiqueta final. El sistema deduce si **confirma** o **corrige** la categoría predicha, para evitar incoherencias.
- **"Tizón tardío confirmado"** exige evidencia: esporulación observada, laboratorio, cámara húmeda u otra (con notas).
- **"Otra enfermedad"** exige indicar el diferencial del catálogo.
- La susceptibilidad de una variedad al tizón solo se registra con una fuente.

---

# Fase 3: dashboard, reportes y notificaciones

## D-40 ✅ KPIs sin dato: "—" con el motivo, nunca un valor inventado

- **Precisión del modelo en producción**: solo se muestra si hay un modelo en etapa `production` con métricas registradas (Fase 4). Con el modelo DEMO aparece "—" y el motivo.
- **Alertas activas** y **parcelas en riesgo climático**: "—" hasta la Fase 5.
- **Acuerdo con la validación experta** (confirmados ÷ confirmados + corregidos) se muestra como indicador de seguimiento. **No es una métrica de evaluación**: los casos revisados no son una muestra aleatoria, y la interfaz y el reporte R-08 lo aclaran.
- Se agrega **"parcelas con casos compatibles en los últimos N días"** (`dashboard.dias_casos_recientes`, 14 por defecto). Sale directamente de los datos y no depende del clima.

## D-41 ✅ PDF con ReportLab en lugar de WeasyPrint

- La especificación admite ambos. ReportLab no necesita bibliotecas del sistema (Pango, HarfBuzz) en la imagen, usa menos memoria (el equipo tiene 7,6 GB) y permite verificar los PDF en Windows sin Docker.
- Usa las fuentes estándar (Helvetica, codificación Windows-1252): cubren el español. Los caracteres que no cubren se reemplazan por "?", por eso el texto de los reportes no usa símbolos como "≥".

## D-42 ✅ Permisos de los reportes

| Acción | Permiso |
|---|---|
| Ver el catálogo y el historial | `reportes:ver` (o `bitacora:exportar`, para exportar desde la bitácora) |
| Generar y descargar R-01 a R-04 y R-06 a R-09 | `reportes:exportar` |
| R-05 (actividad de usuarios) y R-10 (uso del sistema) | `reportes:exportar` **y** `bitacora:ver`, porque contienen datos de la bitácora |
| B-01 (exportación de la bitácora) | `bitacora:exportar` |
| `reportes:crear` | Reservado para programar reportes con n8n (WF-05, Fase 5) |

- Cada usuario ve y descarga solo los reportes que él solicitó.
- El reporte se arma con el **alcance de datos del solicitante**. Si pierde el permiso o se desactiva antes de que el worker lo procese, el reporte termina en error.
- Como máximo 5 reportes en proceso por usuario.
- La solicitud (`exportar`) y cada descarga (`descargar`) quedan en la bitácora.

## D-43 ✅ Todos los reportes se generan en segundo plano

- Hay un solo flujo: solicitud → Celery → MinIO (bucket `reportes`) → notificación → descarga desde el historial. La interfaz consulta el estado cada 1,5 s.
- **Límites:** PDF y Word truncan cada tabla a `reportes.max_filas` filas (5 000 por defecto) con un aviso; Excel admite hasta 50 000 y conserva los tipos (fechas, porcentajes, números).
- El usuario de la aplicación no tiene `DELETE` sobre el historial de reportes ni sobre las notificaciones.

## D-44 ✅ Actividad de ejemplo para el dashboard (solo desarrollo)

- La semilla genera 48 diagnósticos con **imágenes sintéticas**: dibujos simples, no fotos de hojas. Usan el modelo DEMO, se reparten en los últimos 75 días sobre las 4 parcelas demo e incluyen validaciones del especialista demo.
- Quedan marcados con la procedencia `semilla` ("Datos de ejemplo"). El dashboard muestra cuántos hay y el reporte R-02 los identifica.
- Es determinista (semilla 2026) e idempotente. Se desactiva con `SEED_DEMO_ACTIVITY=false`, y no se ejecuta fuera de `APP_ENV=development`.
- Como son datos semilla, no generan eventos en la bitácora.

## D-45 ✅ Notificaciones internas (A4)

- **Eventos:** reporte listo, reporte con error y caso pendiente de validación. Las alertas se suman en la Fase 5.
- **Casos pendientes:** se notifica a los usuarios activos con `validacion:aprobar` cuyo alcance incluye la parcela, salvo a quien subió la foto. En un lote se envía **una** notificación al cerrarlo, con el total de casos pendientes.
- La campana consulta cada 60 s. Cada usuario solo ve y marca las suyas.

## D-46 ✅ Las consultas periódicas no cuentan como actividad

- La campana y el estado de los reportes envían `X-Background: 1`, y esas peticiones no renuevan `last_seen_at`.
- Si contaran, la sesión nunca expiraría por inactividad (requisito de la Fase 1).

## D-47 ✅ "Incidencia" = proporción de fotografías

- R-06 y el dashboard calculan la proporción de fotografías diagnosticadas en cada categoría.
- **No es una incidencia epidemiológica en campo**, porque depende de qué y cuánto se fotografía. El reporte lo indica en una nota.

## D-48 ✅ R-04 "Alertas emitidas" ya tiene su formato definitivo

- Se genera con la tabla vacía y una nota hasta que exista el módulo de alertas (Fase 5).

## D-49 ✅ Dashboard: filtros, granularidad y mapa de calor

- **Filtros globales:** viven en la URL (se pueden compartir y sobreviven a la recarga). Por defecto, los últimos 90 días en hora de Lima.
- **Granularidad automática de la tendencia:** diaria hasta 62 días, semanal (semanas ISO, desde el lunes) hasta 400 días y mensual por encima. Los periodos sin datos aparecen en 0.
- **Mapa de calor:** `leaflet.heat` **0.2.0**. Se descartó la 1.0.0, publicada una semana antes de esta fase con una API nueva. Pondera los casos compatibles = 1, sospechosos = 0,6 y sanos = 0,2; los sanos están ocultos por defecto.
  - Las fotos sin GPS se ubican en el centroide de la parcela y se cuentan como "ubicación aproximada".
  - El mapa muestra como máximo 5 000 puntos.
- **Gráficos:** Recharts 2.15 (compatible con React 18).
  - Colores con contraste de al menos 3:1 y un texto alternativo con los totales.
  - La página se carga bajo demanda para no agrandar el paquete inicial.
- **Exportar** (requiere `dashboard:exportar` y `reportes:exportar`): genera R-07, R-06 o R-01 con los filtros vigentes.

## D-50 ✅ Página de inicio: Dashboard, luego Bitácora

- Prioridad: Dashboard → Bitácora → orden del menú.
- Así se cumple D-28: los roles con Dashboard entran ahí desde esta fase y el Auditor sigue entrando a la Bitácora, aunque el módulo de Reportes también está habilitado.

---

# Fase 4: MLOps, laboratorio de modelos y datasets

## D-51 ✅ El modelo en uso es el que tiene el alias `production` en MLflow

- MLflow 3 dejó en desuso las etapas del Model Registry: se usan **alias**.
- ml-service resuelve el alias `production` entre los modelos `papasana-*` al arrancar y cada vez que el backend llama a `/reload`.
- **Formato del modelo:** el run guarda `model/model.pt` (state_dict) y `model/model_config.json`.
  - No se usa `mlflow.pytorch.log_model`: ml-service no instala MLflow ni carga pickles (`weights_only=True`).
- **Mismo código en entrenamiento y producción:** ml-service construye la red con el mismo paquete de arquitecturas que la entrenó (`ml/src/potato_blight/models`).
  - Ese paquete se copia al construir la imagen, con la raíz del repositorio como contexto.
  - Un `.dockerignore` en la raíz funciona como lista blanca y deja fuera `node_modules`, los datos de `ml/` y `.env`.
- **Respaldo al DEMO:** si no hay modelo en producción, MLflow no responde o el modelo no es válido (clases distintas de las de D-01), se sirve el DEMO y `/model` informa el motivo.
  - Una recarga fallida conserva el modelo que ya estaba cargado.
- **Pruebas de humo:** un modelo `smoke_test` se sirve, pero marcado como DEMO / no validado.

## D-52 ✅ Cliente REST de MLflow, sin instalar MLflow en el backend ni en ml-service

- Se usan pocos endpoints, todos verificados contra MLflow 3.18: registro y versiones, alias, runs, historial de métricas, artefactos y búsqueda de runs.
- **Borrar un alias** exige enviar el cuerpo JSON en el `DELETE`: los parámetros en la URL se ignoran.
- **Cabecera Host:** el servidor la valida, y los nombres `mlflow` y `mlflow:5000` se declaran en `--allowed-hosts`. Sin eso, MLflow rechaza con 403 las llamadas entre contenedores.

## D-53 ✅ MLflow con base y bucket propios

- **Base de datos:** `mlflow`, con un rol `mlflow` propio (`MLFLOW_DB_PASSWORD`).
  - La crea el servicio `migrate` (`app.seed.mlflow_init`).
  - MLflow crea y migra sus propias tablas, aisladas de las de la aplicación.
- **Artefactos:** en MinIO (bucket `mlflow`), servidos por el propio servidor (`--artifacts-destination`). Los clientes no reciben credenciales de MinIO.
- **Puerto:** solo en `127.0.0.1:5000`, para registrar entrenamientos hechos en el equipo y abrir la interfaz de MLflow.
- **Recursos:** 1 worker y 512 MB.

## D-54 ✅ Cuatro ojos en la promoción y el rollback (detalla D-09)

- **Permisos:**
  - solicitar requiere `laboratorio:crear` (Investigador);
  - aprobar o rechazar requiere `laboratorio:aprobar` (Administrador).
- **El solicitante nunca aprueba su propia solicitud,** aunque su rol tenga ambos permisos. Se verifica en el servicio, no solo en la interfaz, y el intento queda en la bitácora como `acceso_denegado`.
- **Una solicitud pendiente a la vez.**
- **Rollback:** solo a una versión que ya estuvo en producción o al DEMO (retirar el modelo entrenado).
- **Al aprobar:**
  1. se deja un único modelo con el alias `production`;
  2. ml-service recarga el modelo;
  3. se comprueba que cargó la versión esperada.

  Si algo falla, se restaura el alias anterior y la solicitud queda **fallida**.
- **Historial:** `ml.model_promotions` no admite `DELETE`.

## D-55 ✅ Registrar no es promover

- `potato_blight.register` crea la versión en el Model Registry sin alias.
- La aplicación la importa con **Sincronizar** (etapa "Registrado") y solo llega a producción por el circuito de D-54.
- Solo se registran modelos con las clases por síntoma (D-01).

## D-56 ✅ Ninguna licencia externa está verificada todavía

**Revisión preliminar del 2026-11-12** (búsqueda web, no verificada):

| Dataset | Lo encontrado |
|---|---|
| PlantVillage | El repositorio no muestra una licencia en los resultados de búsqueda. Meta-Album indica CC0 1.0 para la publicación original; su copia en OpenML figura como CC BY-NC 4.0. **Las fuentes se contradicen.** |
| PlantDoc | Solo copias de terceros (Roboflow) lo declaran CC BY 4.0. |

- Ambos quedan **por verificar**, sin licencia registrada, con estas notas y sus enlaces.
- La verificación la registra una persona en el módulo A1, con la licencia, el enlace a la fuente oficial y qué revisó.
- `ml/` se niega a indexar un dataset con la licencia sin verificar. El registro se exporta como `ml/datasets.yaml`.

## D-57 ✅ Prueba de humo con imágenes sintéticas

- **Qué hace:** dibujos generados por programa, sin pesos preentrenados (no descarga nada), con tamaño 96 y 1 época.
- **Qué demuestra:** que el pipeline completo funciona (datos → MLflow → registro → promoción → ml-service).
- **Cómo se marca:** todo lleva `smoke_test=true`.
  - Sus métricas nunca se reportan.
  - El KPI "precisión del modelo en producción" las ignora.
  - Una comparación calculada con runs de humo se marca como tal.

## D-58 ✅ Protocolo de entrenamiento

**Modos:**

- `cv`: validación cruzada agrupada, con un run padre y uno por partición.
- `final`: entrena con todas las particiones salvo la de validación y es el que se registra.

**Detalles:**

- **Selección y calibración:** early stopping por macro-F1 de la validación interna; la temperatura se calibra en esa misma validación.
- **Desbalance:** pesos por clase inversos a su frecuencia.
- **Aumento de datos:** solo en entrenamiento.
- **Preprocesamiento de evaluación:** lado corto a `img_size / 0,875` y recorte central. Es idéntico en `ml/` y en ml-service.
  - Esto también cambia el DEMO, que antes redimensionaba sin recortar; no tiene efecto práctico, porque el DEMO no tiene valor diagnóstico.
- **Comparación:**
  - Friedman y Wilcoxon-Holm sobre bloques (partición × escenario interno o externo);
  - McNemar, DeLong y bootstrap sobre las predicciones fuera de partición, que cubren las mismas imágenes para todos los modelos.

## D-59 ✅ H1 y H2: backbone EfficientNet-B0 por defecto

- **H1 (CNN-ViT):** tokens del mapa de características, posición aprendida y token [CLS] en un encoder Transformer de 2 capas.
- **H2:** la BiLSTM recorre los parches del mapa en orden raster y una atención aditiva resume la secuencia (D-06).
- **Por qué B0:** es más liviano para la GPU de 6 GB. El backbone es un hiperparámetro y se puede cambiar.
- **Grad-CAM:** usa la salida del backbone. En H2, cuDNN se desactiva durante el cálculo porque no permite el backward de una LSTM en modo evaluación.

## D-60 ✅ Optuna: mismo presupuesto y sin mirar la prueba

- **Configuración:** TPE con semilla fija y `MedianPruner` (5 intentos de arranque, 3 épocas de calentamiento).
- **Presupuesto común:** `n_trials`, `max_epochs` y `timeout_hours` son los mismos para los cinco modelos y se definen en `configs/base.yaml`.
- **Sin fuga:** la búsqueda solo usa el entrenamiento y la validación interna de la partición 0.
- **Espacio de búsqueda:**
  - para todos: lr, weight decay, label smoothing, batch size y dropout;
  - para H1: profundidad y dimensión;
  - para H2: tamaño oculto y número de capas de la BiLSTM.

## D-61 ✅ Entrenamiento en Colab: MLflow en Drive y copia de runs

- Colab no alcanza el MLflow local, que solo escucha en 127.0.0.1.
- En Colab se registra en `sqlite:///…/mlflow.db` dentro de Drive.
- `potato_blight.sync_runs` copia después los runs al MLflow de la aplicación (idempotente, conserva la jerarquía).

## D-62 ✅ El KPI de precisión usa métricas registradas

- El dashboard muestra la accuracy del modelo en producción, en este orden de preferencia: media de la validación cruzada, validación externa, validación interna. Indica la fuente.
- Nunca se muestra para el DEMO ni para un modelo de prueba de humo.
