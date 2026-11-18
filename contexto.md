Tema AP-01. Detección temprana del tizón tardío de la papa mediante inteligencia artificial multimodal y aprendizaje profundo
Impacto ★★★★★
Novedad ★★★★★
Prioridad muy alta
Título científico:
Multimodal Explainable Deep Learning for Early Detection of Potato Late Blight Under Real Field Conditions.
Introducción y vacío de conocimiento
El tizón tardío, causado por Phytophthora infestans, constituye una de las enfermedades más importantes del cultivo de papa.
Numerosos sistemas de clasificación utilizan fotografías controladas de hojas. Sin embargo, existe una brecha entre el rendimiento en imágenes de laboratorio y la detección en condiciones reales de campo, donde intervienen iluminación, humedad, variedades, estadios fenológicos y otras enfermedades.
Metodología
1.	Investigación experimental computacional con imágenes públicas de campo.
2.	Definición de tres clases: sano, tizón temprano de infección o sospechoso y tizón tardío confirmado, siempre que las etiquetas permitan distinguirlas mediante diagnóstico verificable. Si no existe confirmación etiológica, se utilizarán etiquetas de síntomas, no de patógeno.
3.	Preprocesamiento: redimensionamiento, eliminación de duplicados, balanceo y aumento de datos.
4.	Segmentación de lesiones y extracción de características.
5.	Entrenamiento con división por planta, parcela o procedencia para impedir fuga de información.
6.	Validación externa entre datasets.
7.	Grad-CAM, SHAP y mapas de atención.
8.	Evaluación de precisión, sensibilidad, especificidad, F1, MCC, AUC-ROC y AUC-PR.
Algoritmos
Tipo	Algoritmo	Función
1	ResNet50	Clasificación de imágenes.
2	EfficientNetB3	Extracción eficiente de características.
3	ConvNeXt	Representación visual avanzada.
H1	CNN-ViT	Integración de características locales y globales.
H2	EfficientNet-Attention-BiLSTM	Características visuales y secuencias de observaciones.
Datasets públicos
•	PlantVillage.
•	PlantVillage Dataset en GitHub.
•	Kaggle: Potato Disease Datasets.
•	PlantDoc.
Contribución: sistema de detección temprana de enfermedades de papa bajo condiciones reales de cultivo, con especial atención a la generalización entre regiones y variedades.

4. Revistas científicas Scopus y Web of Science Q3 de acceso abierto
Para seleccionar revistas de destino hay que diferenciar tres conceptos:
•	Scopus Q3: cuartil calculado mediante CiteScore o SCImago/SJR, que pueden producir clasificaciones diferentes.
•	WoS Q3: cuartil de Journal Citation Reports (JCR), calculado por Clarivate en una categoría determinada.
•	WoS ESCI: pertenecer a Emerging Sources Citation Index no significa necesariamente disponer de factor de impacto ni de cuartil JCR.
Por tanto, no debe afirmarse que una revista es Q3 en ambas bases sin comprobar su ficha correspondiente.
4.1. Revistas para Salud Pública
Estas son candidatas para evaluar, priorizando acceso abierto y afinidad temática.
Revista	Indexación / clasificación de referencia	Acceso abierto	Temas apropiados
Osong Public Health and Research Perspectives	Scopus; SJR Q3 en determinadas categorías	Sí, Diamond OA	Epidemiología, dengue, vigilancia
Annali dell'Istituto Superiore di Sanità	Scopus Q3 en referencia SJR	Sí	Salud pública y epidemiología
UCL Open Environment	Scopus Q3 en referencia SJR	Sí	Contaminación y salud
Arhiv za Higijenu Rada i Toksikologiju	Scopus Q3 en referencia SJR	Sí	Salud ambiental
Clinical and Experimental Vaccine Research	Scopus Q3 en referencia SJR	Sí	Enfermedades infecciosas y vacunación
Journal of Primary Health Care	Scopus Q3 en referencia SJR	Acceso abierto según modalidad	Atención primaria y gestión sanitaria
Fuentes para comprobar la clasificación y acceso: 
openaccessfinder.de+3
Mi recomendación de primera evaluación: Osong Public Health and Research Perspectives. Su alcance incluye epidemiología, enfermedades infecciosas, vigilancia, enfermedades crónicas y salud digital. Además, su editorial confirma que es de acceso abierto y no cobra APC. 
Osong Public Health and Research Perspectives+1
Página de la revista: Osong Public Health and Research Perspectives.
4.2. Revistas para Agricultura de Precisión
Revista	Clasificación de referencia	Acceso abierto	Temas apropiados
New Medit	Scopus/SJR Q3; referencia JCR Q3 reportada	Diamond OA	Agricultura sostenible y sistemas agrícolas
International Journal of Agriculture and Natural Resources	Scopus/SJR Q3; referencia JCR Q3 reportada	Diamond OA	Producción agrícola y recursos naturales
AgroLife Scientific Journal	Scopus/SJR Q3	Acceso abierto	Agricultura y ciencias vegetales
Revista Caatinga	Scopus/SJR Q3; referencia JCR Q3 reportada	Diamond OA	Agronomía y cultivos
Engenharia Agrícola	Scopus/SJR Q3; referencia JCR Q3 reportada	Diamond OA	Riego, maquinaria y agricultura de precisión
Journal of Agriculture and Environment for International Development	Scopus/SJR Q3	Acceso abierto	Agricultura y sostenibilidad
Fuente de contraste de clasificación y modalidad editorial: 
AVİD+1
.
Enlaces editoriales:
•	New Medit.
•	International Journal of Agriculture and Natural Resources.
•	AgroLife Scientific Journal.
•	Revista Caatinga.
•	Engenharia Agrícola.
Advertencia editorial: las clasificaciones de las tablas son referencias para elaborar una lista inicial, no una certificación de cuartil vigente para noviembre de 2026 en todas las categorías. Antes de enviar el artículo se debe comprobar el ISSN, cobertura activa, categoría, cuartil del año correspondiente, modalidad de acceso y APC en Scopus Sources, SCImago, Clarivate JCR y la página oficial de la revista. No debe confundirse una revista de acceso abierto con una revista gratuita para publicar.
5. Arquitectura tecnológica recomendada: IA + n8n + LangChain + LangFlow
Mi recomendación es que las investigaciones no se limiten a comparar algoritmos. Es conveniente desarrollar una aplicación funcional que implemente el modelo seleccionado y demuestre su utilidad en un escenario realista.
Propongo una arquitectura común que puede adaptarse a los 20 proyectos.
Arquitectura general de investigación y aplicación inteligente
CAPA DE ADQUISICIÓN DE DATOS
Datasets públicos · Sensores IoT · Satélites · Imágenes · Registros clínicos · APIs
n8n – ORQUESTACIÓN DE WORKFLOWS
Ingestión · Limpieza · Validación · Programación · Alertas · Auditoría
LangChain
Agentes, RAG, herramientas, recuperación de información y generación de explicaciones.
LangFlow
Diseño visual, experimentación, prototipos y evaluación de flujos con LLM.
MOTOR DE INTELIGENCIA ARTIFICIAL
3 modelos individuales + 2 modelos híbridos + Optuna + SHAP + validación estadística
BACKEND Y ALMACENAMIENTO
FastAPI · PostgreSQL · PostGIS · MinIO · MLflow
FRONTEND Y RESULTADOS
React · Dashboard · Mapas · Alertas · Reportes PDF/Word/Excel · Trazabilidad
5.1. Función de cada tecnología
Tecnología	Función dentro del proyecto
Python	Desarrollo de algoritmos y procesamiento de datos.
TensorFlow/Keras	Entrenamiento de modelos de Deep Learning.
PyTorch	Transformers, redes neuronales y modelos multimodales.
Scikit-learn	Modelos clásicos, métricas y validación.
XGBoost / LightGBM	Modelos predictivos tabulares.
Optuna	Optimización de hiperparámetros.
SHAP / LIME	Explicabilidad de predicciones.
n8n	Automatización de procesos y ejecución programada.
LangChain	Agentes, herramientas y RAG.
LangFlow	Diseño y experimentación visual de flujos de IA.
FastAPI	Servicios de inferencia y APIs.
PostgreSQL / PostGIS	Datos estructurados y geoespaciales.
React	Interfaz de usuario y dashboard.
MLflow	Seguimiento de experimentos y modelos.
Docker	Despliegue reproducible.
5.2. Workflows n8n recomendados
Propongo implementar al menos seis workflows reutilizables:
Workflow	Proceso automatizado
WF-01	Descarga periódica de datasets y datos meteorológicos o epidemiológicos.
WF-02	Limpieza, control de calidad y detección de datos faltantes.
WF-03	Ejecución programada de predicciones mediante FastAPI.
WF-04	Generación y distribución de alertas de riesgo.
WF-05	Elaboración automática de reportes científicos y gerenciales.
WF-06	Registro de auditoría, monitoreo y evaluación del rendimiento de modelos.
Aplicación de LangChain y LangFlow
No recomiendo incorporar LLM simplemente para aumentar el número de tecnologías del proyecto.
Su aplicación debe tener una justificación funcional y evaluable.
En Salud Pública:
•	Agente de consulta de protocolos de vigilancia epidemiológica.
•	RAG sobre guías de la OMS, CDC y documentos científicos.
•	Generación de explicaciones de alertas epidemiológicas.
•	Asistente para consultar resultados de modelos.
•	Recuperación de evidencia científica para apoyar la interpretación de resultados.
En Agricultura de Precisión:
•	Agente de interpretación de mapas de riesgo.
•	RAG sobre documentos técnicos de FAO, SENASA e INIA.
•	Asistente de recomendaciones agronómicas basado en evidencia.
•	Generación de informes sobre estrés hídrico y enfermedades.
•	Explicación de predicciones de rendimiento.
El LLM debe actuar como interfaz de consulta y explicación, no como sustituto del modelo predictivo validado. Las recomendaciones sanitarias y agronómicas deberán incorporar restricciones, fuentes verificables y supervisión profesional.
6. Protocolo experimental común para los 20 proyectos
Para conseguir resultados científicamente defendibles, recomiendo utilizar un protocolo experimental homogéneo que permita comparar los cinco modelos de cada investigación.
6.1. Fases de investigación
Fase	Actividades	Producto científico
F1. Revisión científica	PRISMA 2020, Scopus, WoS, IEEE Xplore y PubMed	Estado del arte y vacío de conocimiento
F2. Comprensión del problema	Definición de población, unidad de análisis y variables	Protocolo de investigación
F3. Datasets	Selección, descarga, licencias y diccionario de datos	Dataset documentado
F4. EDA	Estadística descriptiva, correlaciones, anomalías y visualizaciones	Informe exploratorio
F5. Preprocesamiento	Limpieza, imputación, normalización y selección de variables	Dataset experimental
F6. Modelamiento	Tres algoritmos individuales y dos híbridos	Cinco modelos entrenados
F7. Optimización	Optuna y búsqueda de hiperparámetros	Modelos optimizados
F8. Validación	Validación cruzada, temporal, espacial o externa	Resultados comparativos
F9. Evaluación estadística	Friedman, Wilcoxon y pruebas complementarias	Evidencia de diferencias
F10. Interpretabilidad	SHAP, LIME, Grad-CAM y análisis de incertidumbre	Explicabilidad
F11. Prototipo	FastAPI, React, PostgreSQL y n8n	Aplicación funcional
F12. Publicación	Redacción, figuras, tablas, código y anexos	Artículo científico
6.2. Estrategia de validación
Es uno de los aspectos más importantes para evitar el rechazo de un artículo.
No recomiendo utilizar únicamente una división aleatoria de 80 % entrenamiento y 20 % prueba.
La estrategia debe responder a la estructura de los datos.
Tipo de investigación	Validación recomendada
Imágenes médicas	Agrupación por paciente y validación externa por hospital
Epidemiología	Validación temporal y geográfica
Agricultura con imágenes	Agrupación por parcela, planta y procedencia
Series temporales	Walk-forward validation
Imágenes satelitales	Spatial Block Cross-Validation
Sensores IoT	Validación temporal y por dispositivo
Datos clínicos longitudinales	Separación por paciente y periodo
Para datasets pequeños se puede utilizar validación cruzada agrupada de cinco particiones, siempre que el número de grupos lo permita.
Regla fundamental: las imágenes aumentadas de una misma fotografía, los registros de un mismo paciente o las observaciones de una misma parcela no pueden distribuirse entre entrenamiento y prueba de manera que produzcan fuga de información.
6.3. Optimización de hiperparámetros con Optuna
Se recomienda utilizar Optuna con:
•	50–150 trials iniciales por modelo, ajustables según presupuesto computacional.
•	TPE Sampler.
•	Median Pruner o Hyperband Pruner.
•	Búsqueda de learning rate.
•	Batch size.
•	Número de capas y neuronas.
•	Dropout.
•	Weight decay.
•	Número de estimadores.
•	Profundidad de árboles.
•	Ventanas temporales.
•	Número de cabezas de atención.
La optimización debe ejecutarse exclusivamente sobre los datos de entrenamiento y validación interna. El conjunto de prueba final no debe intervenir en la selección de hiperparámetros.
Para una comparación rigurosa, debe establecerse un presupuesto computacional comparable para los cinco modelos.
6.4. Métricas de evaluación
No todos los problemas deben evaluarse con las mismas métricas.
Problema	Métricas principales
Clasificación médica	Sensibilidad, especificidad, F1, MCC, AUC-ROC, AUC-PR
Epidemiología	MAE, RMSE, MASE, WIS y cobertura de intervalos
Predicción agrícola	MAE, RMSE, R² y MAPE cuando sea válido
Detección de objetos	mAP50, mAP50-95, precisión y recall
Segmentación	Dice, IoU y Hausdorff
Riego inteligente	Ahorro hídrico, rendimiento y eficiencia del agua
Optimización hospitalaria	Ocupación, tiempos de espera y utilización de recursos
Se deben presentar matrices de confusión, curvas ROC, curvas Precision-Recall, curvas de aprendizaje, mapas de calor y gráficos de calibración cuando correspondan.
6.5. Pruebas estadísticas
Recomiendo incorporar:
1.	Friedman: comparación de múltiples modelos sobre bloques de evaluación independientes.
2.	Wilcoxon signed-rank: comparación pareada de dos modelos.
3.	Holm: corrección por comparaciones múltiples.
4.	McNemar: comparación de errores de clasificación sobre los mismos casos.
5.	Bootstrap: intervalos de confianza de métricas.
6.	DeLong: comparación de curvas ROC cuando se cumplen sus supuestos.
7.	Diebold-Mariano: comparación de precisión de pronósticos temporales, cuando corresponda.
No se debe aplicar Friedman a cinco valores agregados de rendimiento obtenidos de una única partición. Se necesitan bloques de evaluación comparables y una unidad de análisis estadístico correctamente definida.
7. Priorización: los 6 temas que recomiendo desarrollar primero
Considerando potencial de publicación, novedad, disponibilidad de datos públicos, posibilidad de desarrollar un prototipo y relevancia para Perú, mi selección es la siguiente.
Selección prioritaria de investigaciones
Forecasting Weekly Dengue Cases by Integrating Google Earth Engine-Based Risk Predictor Generation and Google Colab-Based Deep Learning Modeling in Fortaleza and the Federal District, Brazil
1. SP-01. Predicción de brotes de dengue
Prioridad máxima
Salud Pública · IA espacio-temporal
Combina epidemiología, cambio climático, geolocalización y modelos híbridos.
Hungersnot 2.0? | Industrieverband Agrar e. V.
2. AP-01. Detección temprana del tizón tardío de papa
Prioridad máxima
Agricultura · Visión artificial
Excelente oportunidad para estudiar la diferencia entre imágenes controladas y condiciones reales de campo.
Riego de precisión y sensores para mejorar la eficiencia hídrica en agricultura
3. AP-03. Optimización inteligente del riego
Prioridad máxima
Agricultura · IA + IoT + MPC
Permite medir ahorro hídrico y productividad, dos indicadores de impacto tangible.
Frontiers | Clinical validation of an artificial intelligence algorithm for classifying tuberculosis and pulmonary findings in chest radiographs
4. SP-02. Diagnóstico asistido de tuberculosis
Prioridad alta
Salud Pública · Deep Learning
Dispone de datasets reconocidos y permite validación externa entre fuentes.
Satellite Imagery Transforms Agriculture with Early Crop Monitoring and Precision Farming | Ali Modares posted on the topic | LinkedIn
5. AP-02. Predicción de rendimiento agrícola
Prioridad alta
Agricultura · IA geoespacial
Excelente oportunidad para integrar Sentinel-2, meteorología y características del suelo.
Emerging Growing Regions 2026–27: Where the Frontier Is Shifting in Global Crop Production | SatYield
6. AP-10. Gemelo digital agrícola
Prioridad alta
Agricultura · IA + IoT + gemelos digitales
Permite construir una contribución tecnológica integral con predicción, simulación y optimización.
8. Consideraciones críticas para conseguir publicaciones científicas
Hay seis aspectos que considero especialmente importantes.
1. No confundir disponibilidad pública con calidad científica del dataset.
Por ejemplo, PlantVillage es valioso para benchmarking, pero no representa por sí solo la variabilidad de las condiciones de campo. En imágenes médicas también existen etiquetas automáticas o derivadas de informes que pueden contener errores. Se debe documentar su calidad y procedencia. 
frontiersin.org+2
2. No confundir simulaciones con resultados experimentales.
Si se simula un cultivo, un hospital o una población, los resultados deben presentarse como simulación. No pueden utilizarse para afirmar que se consiguió ahorro de agua real, reducción de mortalidad o mejora de productividad real.
3. No utilizar datasets pequeños para afirmar generalización poblacional.
Por ejemplo, un dataset de 2.000 imágenes no necesariamente representa miles de plantas independientes si contiene fotografías repetidas de las mismas plantas.
4. Evaluar la explicabilidad.
No basta con presentar imágenes Grad-CAM o gráficos SHAP. Se debe estudiar si las explicaciones son estables, relevantes y consistentes con conocimiento clínico o agronómico.
5. Considerar ética y privacidad.
Los estudios sanitarios requieren revisión de requisitos éticos, permisos y acuerdos de uso de datos, aunque estos sean desidentificados. Las aplicaciones de diagnóstico deben considerarse herramientas de investigación o apoyo, no sustitutos del profesional sanitario.
6. Demostrar utilidad más allá de la exactitud predictiva.
Un artículo puede conseguir excelentes métricas y, sin embargo, aportar poco si no demuestra qué problema resuelve mejor que las alternativas existentes.
9. Recomendación final para organizar una cartera de investigación
Sugiero organizar las investigaciones en cuatro grupos, con objetivos y productos científicos diferenciados.
Grupo	Temas	Orientación	Producto
A	SP-01, SP-02, AP-01	Diagnóstico y detección temprana	Modelos de IA explicables
B	SP-03, SP-04, SP-05, SP-06	Predicción y prevención	Modelos de riesgo
C	SP-07, SP-08, SP-09, SP-10	Vigilancia y gestión	Sistemas predictivos
D	AP-02 a AP-10	Agricultura inteligente	Modelos multimodales, IoT y gemelos digitales
Cada investigación debería producir como mínimo:
•	Un artículo científico original.
•	Un repositorio GitHub reproducible.
•	Un notebook ejecutable en Google Colab.
•	Un informe técnico de resultados.
•	Un prototipo funcional.
•	Un conjunto de figuras y tablas científicas.
•	Una documentación de datasets, variables y experimentos.
