# Resultados para el artículo

La sección está en **Laboratorio de modelos → Resultados para el artículo**. El enlace directo es `/laboratorio?vista=articulo`. Utiliza el permiso existente `laboratorio:ver` tanto en la interfaz como en la API.

Incluye la comparación de las cuatro arquitecturas entrenadas en la RTX 3050, sus tiempos y memoria, el F1 por época, pérdidas, métricas por clase, matrices de confusión, curvas ROC y precisión-exhaustividad, fiabilidad antes/después de calibrar, tablas del EDA y el diagrama completo de la metodología. Puede seleccionar modelo, conjunto de evaluación e informe. Las tablas se pueden ordenar antes de copiarlas.

## Exportar figuras

Seleccione el ancho al imprimir y use **PNG · 600 DPI** en cada figura. **Ampliar** permite revisar los textos antes de descargar. El ancho inicial es 17,5 cm; hay opciones de 8,5 y 21 cm. Conviene usar 17,5 cm o más cuando hay varias series o muchas etiquetas.

La imagen se vuelve a renderizar desde la figura vectorial; no se amplía una captura de pantalla. Se calcula `píxeles = redondear(ancho_cm / 2,54 × 600)` y se escribe un bloque PNG `pHYs` de 23 622 píxeles/metro en ambos ejes. Por ejemplo, 17,5 cm produce 4134 píxeles de ancho. La representación entera del estándar corresponde a 599,9988 DPI, que los editores presentan como 600 DPI. Al insertar la imagen en Word, conserve el ancho físico elegido para mantener esa densidad efectiva.

Se verificaron las descargas reales de comparación, matriz, ROC, PR, calibración, pérdida y metodología, además de su decodificación y metadatos con Pillow. La metodología de ejemplo está en `ml/data/comparacion-cuatro/article/methodology-600dpi.png` y mide 4134 × 5788 píxeles.

Referencias de implementación: [PNG pHYs de W3C](https://www.w3.org/TR/png-3/#11pHYs), [canvas.toBlob](https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/toBlob).

## Copiar tablas para Word o Excel

Use **Copiar con formato**. El portapapeles recibe una tabla HTML editable con encabezados, bordes, tipografía, título y nota de procedencia, además de texto con tabulaciones. Se copia el orden visible de las filas y su precisión decimal. En Word elija **Mantener formato de origen** al pegar; en Excel conserve el formato de origen si desea los estilos. La compatibilidad del pegado final depende del editor receptor.

Si el navegador bloquea el portapapeles, el módulo muestra el error; habilite copiar para este sitio y reintente. El mecanismo principal requiere HTTPS o localhost. Existe un fallback del evento `copy` que también conserva HTML; no se anuncia éxito si ambos fallan. [Referencia de Clipboard.write](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard/write).

## Metodología y límites científicos

El diagrama utiliza los recuentos y parámetros del informe: fuentes y licencias → deduplicación y cuarentena → EDA → separación de PlantVillage y PlantDoc → holdout agrupado → entrenamiento CUDA de cuatro arquitecturas → selección y calibración internas → evaluación externa descriptiva → verificación y artefactos. El máximo de épocas, resolución, lote y precisión se leen de los parámetros guardados.

Los cinco folds preparados no se presentan como cinco entrenamientos de validación cruzada: este piloto usó el fold 1 para validar y los restantes para entrenar. La validación anidada y la evaluación prospectiva aparecen como pendientes. PlantDoc no intervino en la elección y ya fue observado en un piloto anterior. No contiene hojas sanas; su macro-F1 corresponde a las dos clases presentes. Los resultados no demuestran no inferioridad estadística ni calidad agronómica en campo.

## Publicación de resultados y despliegue

La app sirve informes publicados en `backend/app/data/training_reports/`; no expone fotos, pesos, credenciales ni rutas privadas. Cada informe conserva la huella del manifest, el contrato, los IDs de MLflow, los hashes de checkpoints, las métricas y sus historiales. Consultarlo no requiere GPU ni MLflow encendido; sí requiere la autenticación normal de PapaSana.

Se publicó `papasana-cuatro-gpu-20261118.json` con los resultados reales. Para regenerarlo, desde la raíz:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/train-gpu.ps1 -Mode publish
```

Para otro directorio con el mismo formato de resultados de la comparación (incluye `results.json`, `model_sources.json` y checkpoints):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/train-gpu.ps1 -Mode publish -Source data/otra-comparacion
```

El publicador comprueba el manifest, el balance del control de calidad, los hashes de pesos y el estado FINISHED de las ejecuciones; rechaza intentos excluidos o datos no coincidentes. Es una operación local sin reentrenamiento. Los entrenamientos existentes conservan sus artefactos. Al incorporar otro formato de experimento, se debe adaptar el publicador, conservando la procedencia de sus datos.

Los informes viajan con el backend al construir su imagen. En una instalación Docker existente, reconstruya las imágenes que cambiaron y actualice la app desde la raíz, con su `.env` habitual:

```powershell
docker compose build migrate frontend
docker compose up -d
```

Endpoints GET protegidos: `/api/v1/laboratorio/publicaciones` y `/api/v1/laboratorio/publicaciones/{id}`. No hay migraciones de base de datos, cambios de permisos ni promoción de modelos. No se añadieron dependencias de producción ni servicios remotos.

## Verificación

Pasaron 51 pruebas de frontend, 12 de la API aislada y 3 del publicador. Typecheck, build de producción y Ruff pasaron. Vite conserva un aviso de tamaño del paquete principal; la nueva pestaña se carga bajo demanda.

- Frontend: pruebas de navegación, estados vacío/error, datos reales, parámetros del diagrama, densidad PNG y copia HTML/texto; typecheck y build.
- Backend: pruebas aisladas de lectura, autenticación, permiso del Laboratorio, rechazo de identificadores de rutas y archivos corruptos, sin PostgreSQL.
- Publicador: preservación de métricas e historiales, rechazo de manifest y pesos modificados.
- Chrome: navegación entre vistas y modelos, selección externa, portapapeles con tabla HTML, siete descargas PNG, ampliación del diagrama y anchos de 1440 y 390 píxeles sin desbordamiento del documento. Las tablas amplias se desplazan dentro de su contenedor.

La prueba de navegador utilizó el snapshot real e interceptó autenticación y servicios adyacentes únicamente en el proceso de prueba; la API se probó por separado con FastAPI. Docker no estaba iniciado y no se ejecutó la suite histórica que requiere PostgreSQL. No se afirma una prueba E2E de toda la infraestructura. Evidencia local en `ml/data/ui-verification/`.
