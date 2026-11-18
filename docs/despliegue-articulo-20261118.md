# Despliegue local y artículo del 18 de noviembre de 2026

PapaSana quedó activa con Docker Compose. En esta laptop se accede mediante
http://127.0.0.1:18080 y el laboratorio está en
http://127.0.0.1:18080/laboratorio?vista=articulo.

## Servicios y correcciones

- Se construyeron las imágenes y se ejecutaron migraciones y seed.
- MLflow incorpora psycopg 3 además de psycopg2, porque la versión instalada normaliza el driver PostgreSQL a psycopg.
- El límite de MLflow pasó de 512 MiB a 1024 MiB tras observar reinicios por OOM. No se aumentaron los demás límites.
- El test de ResearchTab usa una copia local del snapshot dentro de frontend; el contexto Docker ya no necesita importar archivos externos.
- El diagnóstico conserva su flujo de promoción existente. Publicar métricas no promociona automáticamente un checkpoint.

## Acceso desde Windows

El puerto 8080 declarado por Docker no aceptaba conexiones desde Windows ni desde el loopback de WSL, aunque Nginx respondía dentro de la red de contenedores. La máquina usa WSL en modo mirrored. Se verificó el fallo también después de reiniciar Docker Desktop; no se cambió la configuración global de WSL ni el firewall.

Como solución local se dejó activo scripts/windows-docker-bridge.py. Escucha únicamente en 127.0.0.1:18080 y transporta bytes mediante docker compose exec al Nginx del frontend. La aplicación, la API y los datos siguen ejecutándose en los contenedores. El puente no analiza ni registra cuerpos HTTP, contraseñas o tokens. Necesita Python y Docker CLI de Windows.

El proceso es local y termina al cerrar sesión o reiniciar Windows. Para levantarlo de nuevo, desde la raíz del repositorio:

    docker compose up -d
    powershell -ExecutionPolicy Bypass -File scripts/windows-docker-bridge.ps1

Para detener solo el puente:

    powershell -ExecutionPolicy Bypass -File scripts/windows-docker-bridge.ps1 -Stop

Los logs y el PID se guardan en ml/data/deployment, excluido del repositorio. No ejecutar el puente si la publicación normal de Docker ya funciona y se utiliza el puerto 8080. El puente es un recurso de desarrollo; no es un servidor de producción.

El usuario confirmó que la página abre en Windows. Se verificaron además desde Windows el login real, /api/health, el acceso al informe publicado y sus cuatro modelos. La cuenta demo es admin@demo.papasana.pe; su contraseña generada está en DEMO_USERS_PASSWORD del archivo local .env. No publicar ese archivo.

Referencias de diagnóstico:
- https://docs.docker.com/desktop/features/networking/
- https://learn.microsoft.com/en-us/windows/wsl/networking
- https://github.com/microsoft/WSL/issues/13868

Estas referencias describen la arquitectura y problemas similares; el diagnóstico exacto del fallo del host no se considera demostrado solo por su coincidencia con un issue.

## Verificación

- Backend dentro de Docker: 242 pruebas aprobadas, una advertencia y cobertura global del 89 %. Registro: ml/data/deployment/backend-tests.log.
- Frontend: 51 pruebas aprobadas en 12 archivos después de hacer el fixture autocontenido.
- Build Docker del frontend y del resto de servicios completado.
- Login y carga autenticada de los cuatro modelos a través del puente de Windows aprobados.
- Ocho matrices de confusión reproducidas desde los cuatro checkpoints; hashes conservados.
- Cinco figuras PNG comprobadas con metadatos de 600 dpi.
- DOCX renderizado con LibreOffice headless en un contenedor aislado, tras diagnosticar la ausencia de LibreOffice en Windows. Las 15 páginas PNG finales se inspeccionaron visualmente. No se adjuntan intermediarios de QA.
- No hay migraciones nuevas por las correcciones de este despliegue.

## Artículo nuevo

Archivo final, junto al artículo original en AP-01:

    articulo_papasana_hallazgos_reales_20261118.docx

Contiene resumen y abstract, métodos ejecutados, cinco figuras, seis tablas editables, discusión, limitaciones, 14 referencias y un apéndice de trazabilidad. El original articulo_q1.docx se conserva.

La evaluación de PlantDoc es descriptiva porque ya se había observado en el piloto. No se atribuyen validación cruzada completa, búsqueda Optuna ejecutada, detección presintomática, confirmación etiológica o efecto de alertas climáticas.

La NLL del artículo se calcula de forma estable en log-espacio; el evaluador archivado recorta probabilidades a 1e-12. Se mantienen ambos registros y se explica su diferencia. Las temperaturas y los pesos no se modificaron. Los IC externos provienen de 5000 remuestreos de 206 grupos, sin estimar variación entre entrenamientos.

Para preparar una presentación editorial faltan la revisión de los autores, afiliación, correspondencia, contribuciones, declaraciones y adaptación a la revista elegida. No se asegura aceptación Q1/Q2.

