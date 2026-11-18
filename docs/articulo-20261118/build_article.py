"""Manuscrito científico de PapaSana a partir de artefactos congelados."""
import json
from pathlib import Path
from datetime import datetime, timezone
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
OUT=ROOT.parent/"articulo_papasana_hallazgos_reales_20261118.docx"
r=json.loads((ROOT/"backend/app/data/training_reports/papasana-cuatro-gpu-20261118.json").read_text(encoding="utf-8"))
a=json.loads((BASE/"analisis_derivado.json").read_text(encoding="utf-8"))
models=r["models"]
audit={x["architecture"]:x for x in a["models"]}
names=["ResNet50","EfficientNetV2 B0","MobileNetV4 Conv Medium","EfficientViT B1"]
doc=Document()
s=doc.sections[0]
s.page_width=Cm(21.59);s.page_height=Cm(27.94)
s.top_margin=s.bottom_margin=Cm(2.1)
s.left_margin=s.right_margin=Cm(2.5)
s.header_distance=s.footer_distance=Cm(1.1)
normal=doc.styles["Normal"]
normal.font.name="Times New Roman";normal.font.size=Pt(11);normal.font.color.rgb=RGBColor(0,0,0)
normal.paragraph_format.line_spacing=1.1
normal.paragraph_format.space_after=Pt(6)
for sty,size in [("Title",16),("Heading 1",13),("Heading 2",11.5)]:
    st=doc.styles[sty]
    st.font.name="Times New Roman";st.font.size=Pt(size);st.font.bold=True
    st.font.color.rgb=RGBColor(0,0,0)
    st.paragraph_format.space_before=Pt(12 if sty!="Title" else 0)
    st.paragraph_format.space_after=Pt(6)
    st.paragraph_format.keep_with_next=True
    for b in list(st.element.xpath(".//w:pBdr")):b.getparent().remove(b)
footer=s.footer.paragraphs[0]
footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
footer.add_run("PapaSana  |  ").font.size=Pt(9)
field=OxmlElement("w:fldSimple");field.set(qn("w:instr"),"PAGE");footer._p.append(field)
doc.core_properties.author="Quiroz Rodríguez y Zavaleta Carranza"
doc.core_properties.title="Evaluación entre dominios y calibración de cuatro modelos para clasificar síntomas foliares de papa en PapaSana"
doc.core_properties.subject="Manuscrito de investigación basado en cuatro entrenamientos GPU y evaluación externa descriptiva"
doc.core_properties.created=datetime(2026,11,18,tzinfo=timezone.utc)
text=[]
def P(t,style=None):
    p=doc.add_paragraph(t,style)
    p.paragraph_format.widow_control=True
    text.append(t+"\n")
    return p
def H(t,level=1):
    heading=doc.add_heading(t,level)
    if t.startswith("Apéndice"):heading.paragraph_format.page_break_before=True
    text.append("#"*(level+1)+" "+t+"\n")
def F(v,n=3):
    return f"{v:.{n}f}".replace(".",",")
def cap(t):
    p=P(t)
    p.paragraph_format.space_before=Pt(4);p.paragraph_format.space_after=Pt(7)
    for run in p.runs:run.font.size=Pt(9.5)
    return p
def image(filename,caption,width=16):
    p=doc.add_paragraph()
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before=Pt(6)
    p.paragraph_format.space_after=Pt(0)
    p.paragraph_format.keep_with_next=True
    p.add_run().add_picture(str(BASE/"figures"/filename),width=Cm(width))
    cap(caption)
    text.append("![Figura]("+str(BASE/"figures"/filename)+")\n")
def table(caption,heads,rows,widths):
    cp=cap(caption);cp.paragraph_format.keep_with_next=True
    t=doc.add_table(rows=1,cols=len(heads))
    t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    tblpr=t._tbl.tblPr
    border=OxmlElement("w:tblBorders")
    for side in ["top","left","bottom","right","insideH","insideV"]:
        e=OxmlElement("w:"+side);e.set(qn("w:val"),"single");e.set(qn("w:sz"),"4");e.set(qn("w:color"),"D9D9D9");border.append(e)
    tblpr.append(border)
    for col,w in zip(t.columns,widths):col.width=Cm(w)
    for i,h in enumerate(heads):t.rows[0].cells[i].text=h
    header=OxmlElement("w:tblHeader");t.rows[0]._tr.get_or_add_trPr().append(header)
    for row in rows:
        cells=t.add_row().cells
        for i,v in enumerate(row):cells[i].text=str(v)
    for ir,row in enumerate(t.rows):
        cant=OxmlElement("w:cantSplit");row._tr.get_or_add_trPr().append(cant)
        for i,c in enumerate(row.cells):
            c.width=Cm(widths[i]);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            pr=c._tc.get_or_add_tcPr()
            margins=OxmlElement("w:tcMar")
            for edge,size in [("top",80),("bottom",80),("left",90),("right",90)]:
                e=OxmlElement("w:"+edge);e.set(qn("w:w"),str(size));e.set(qn("w:type"),"dxa");margins.append(e)
            pr.append(margins)
            if ir==0:
                sh=OxmlElement("w:shd");sh.set(qn("w:fill"),"E4EBEF");pr.append(sh)
            for p in c.paragraphs:
                p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=1.05
                p.paragraph_format.keep_with_next=ir<len(t.rows)-1
                p.alignment=WD_ALIGN_PARAGRAPH.LEFT if i==0 else WD_ALIGN_PARAGRAPH.CENTER
                for run in p.runs:
                    run.font.name="Times New Roman";run.font.size=Pt(9)
                    run.font.bold=ir==0
    gap=doc.add_paragraph()
    gap.paragraph_format.line_spacing=Pt(4)
    gap.paragraph_format.space_after=Pt(3)
    gap.paragraph_format.space_before=Pt(0)
    text.append(" | ".join(heads)+"\n")
    for row in rows:text.append(" | ".join(map(str,row))+"\n")
    return t

p=doc.add_paragraph(doc.core_properties.title,"Title")
p.alignment=WD_ALIGN_PARAGRAPH.CENTER
text.append("# "+doc.core_properties.title+"\n")
p=P("Quiroz Rodríguez y Zavaleta Carranza")
p.alignment=WD_ALIGN_PARAGRAPH.CENTER
p=P("Proyecto PapaSana  ·  Manuscrito actualizado con resultados del 18 de noviembre de 2026")
p.alignment=WD_ALIGN_PARAGRAPH.CENTER
for run in p.runs:run.font.size=Pt(10)

H("Resumen")
P("El alto rendimiento de un clasificador de enfermedades vegetales en imágenes controladas no asegura su utilidad en capturas heterogéneas. Evaluamos cuatro arquitecturas preentrenadas para clasificar hojas de papa como sanas, con síntomas compatibles con tizón tardío o con otra enfermedad foliar. El control de calidad conservó 2152 imágenes de PlantVillage y 208 de PlantDoc, con agrupación por hoja o semejanza perceptual para reducir filtraciones entre particiones. Entrenamos ResNet50, EfficientNetV2 B0, MobileNetV4 Conv Medium y EfficientViT B1 en una GPU RTX 3050 Laptop de 4 GiB, usando 1724 imágenes de entrenamiento y 428 de validación. El F1 macro interno fue de 0,9867 a 1,0000 y cada entrenamiento válido requirió entre 149,6 y 270,3 segundos. En PlantDoc, conjunto previamente observado y utilizado aquí como evaluación externa descriptiva, el F1 macro sobre sus dos clases presentes descendió a 0,5043–0,5849. Al restringir la referencia interna a esas dos clases, las brechas fueron de 39,51 a 49,44 puntos porcentuales. La temperatura estimada internamente no mejoró de forma uniforme la calibración externa. Una auditoría con pérdida logarítmica estable identificó que el recorte de probabilidades ocultaba errores extremos, especialmente en MobileNetV4. PapaSana incorpora tablas, curvas, matrices y una metodología exportables para documentar estos hallazgos. Los resultados respaldan una comparación reproducible y de bajo tiempo de entrenamiento, pero no acreditan detección temprana en campo, confirmación etiológica ni superioridad externa de un modelo.")
P("Palabras clave: papa; aprendizaje por transferencia; cambio de dominio; calibración; PlantVillage; PlantDoc; reproducibilidad.")

H("Abstract")
P("Strong performance on controlled plant leaf images does not establish reliability on heterogeneous photographs. We evaluated four pretrained architectures for classifying potato leaves as healthy, displaying symptoms compatible with late blight, or displaying another foliar disease. Quality control retained 2152 PlantVillage images and 208 PlantDoc images, with leaf identifiers and perceptual similarity groups used to reduce leakage across partitions. ResNet50, EfficientNetV2 B0, MobileNetV4 Conv Medium, and EfficientViT B1 were trained on a 4 GiB RTX 3050 Laptop GPU using 1724 training and 428 validation images. Internal macro F1 ranged from 0.9867 to 1.0000, with successful training times of 149.6–270.3 seconds. On PlantDoc, previously inspected and therefore treated as a descriptive external evaluation set, macro F1 over the two observed classes ranged from 0.5043 to 0.5849. A secondary comparison restricted the internal reference to the same disease classes and showed gaps of 39.51–49.44 percentage points. Internally fitted temperature scaling did not consistently improve external calibration. A stable log-space negative log-likelihood audit revealed that probability clipping masked extreme errors, particularly for MobileNetV4. PapaSana presents reproducible tables, plots, confusion matrices, and a methodology diagram with publication-oriented export. These findings support a short training workflow and transparent reporting, while highlighting limitations in cross-dataset transfer and uncertainty estimation. They do not establish prospective field performance, etiological confirmation, early detection, or external superiority of any architecture.")
P("Keywords: potato; transfer learning; domain shift; calibration; image classification; reproducibility.")

H("1 Introducción")
P("El tizón tardío, asociado con Phytophthora infestans, motiva sistemas de apoyo que orienten la revisión agronómica de síntomas. Una fotografía puede apoyar una clasificación visual, pero no demuestra por sí sola la identidad del agente causal, el momento de inicio de la infección ni la eficacia de una decisión de manejo. PapaSana se desarrolla con esa distinción: la salida del modelo representa compatibilidad visual con categorías de entrenamiento y requiere interpretación agronómica antes de atribuirle utilidad diagnóstica.")
P("PlantVillage permitió estudiar clasificación de enfermedades a partir de fotografías bajo condiciones relativamente controladas [1]. PlantDoc incorporó imágenes heterogéneas recopiladas de internet para aproximarse a escenarios visualmente más complejos [2]. La diferencia de origen plantea una pregunta práctica: ¿qué rendimiento conserva un modelo cuando se evalúa fuera del conjunto del que proceden sus imágenes de ajuste? Una comparación que omita esta pregunta puede favorecer decisiones apoyadas en una estimación interna excesivamente optimista.")
P("Este trabajo compara cuatro modelos con un presupuesto común de entrenamiento corto en una laptop. Documenta el control de datos, las decisiones de partición, la clasificación interna, la evaluación externa descriptiva y la calibración de probabilidades. Su contribución es una evaluación trazable de modelos congelados y una integración para consultar y exportar resultados en PapaSana. No se pretende estimar prevalencia agrícola ni validar todavía la detección temprana o el efecto de alertas climáticas.")
P("Las preguntas de investigación son tres: qué rendimiento interno y consumo de recursos alcanzan las arquitecturas; cómo cambian sus errores al evaluarlas en PlantDoc; y si la calibración estimada con validación interna conserva su comportamiento en ese conjunto. La elección de un candidato operativo se separa de la inspección externa para reducir la adaptación oportunista a sus resultados.")

H("2 Fundamentos y trabajos relacionados")
P("Se incluyeron ResNet50, cuya arquitectura residual facilita optimizar redes profundas [3]; EfficientNetV2 B0, de una familia diseñada considerando eficiencia de entrenamiento [4]; MobileNetV4 Conv Medium, perteneciente a una familia orientada a computación móvil [5]; y EfficientViT B1, basado en la familia de atención multiescala de Cai y colaboradores [6]. Esta última denominación corresponde a la implementación del modelo timm/efficientvit_b1.r224_in1k y evita confundirla con otras familias que comparten el nombre EfficientViT. Las afirmaciones de los trabajos originales no sustituyen mediciones de latencia o precisión en esta aplicación.")
P("La temperatura es una transformación escalar de los logits que permite ajustar probabilidades sin cambiar el orden de las clases [7]. Una mejora en el conjunto usado para estimarla no garantiza una mejora en otra distribución. Asimismo, el error de calibración esperado y la pérdida logarítmica resumen propiedades distintas: el primero depende de la agrupación de confianzas y la segunda penaliza intensamente predicciones incorrectas muy seguras.")
P("Grad-CAM permite visualizar regiones asociadas con una salida de redes convolucionales [8]. En PapaSana se verificó su ejecución técnica, pero no se evaluó la coincidencia entre mapas y lesiones anotadas. La literatura sobre atajos visuales ofrece una hipótesis para interpretar diferencias entre conjuntos [9]; este experimento no identifica causalmente qué rasgos emplea cada red. Por su parte, la prevención de filtración de datos exige describir la relación entre imágenes, particiones y decisiones de selección, además de informar una métrica final [10].")


H("3 Materiales y métodos")
H("3 1 Diseño y alcance de la evaluación",2)
P("Se ejecutó una comparación de cuatro configuraciones predefinidas, con un único pliegue de validación de PlantVillage y una evaluación descriptiva posterior en PlantDoc. Aunque el manifiesto contiene cinco pliegues, no se entrenaron las cinco rotaciones ni se ejecutó validación cruzada anidada. Los parámetros de ajuste de Optuna presentes en la configuración del proyecto no corresponden a una búsqueda realizada en esta comparación. Por ello, los resultados no se presentan como estimaciones de validación cruzada ni como arquitecturas individualmente optimizadas.")
P("PlantDoc ya había sido inspeccionado en una fase piloto. En consecuencia, su carácter externo describe el origen de las imágenes, pero no equivale a un conjunto de prueba completamente intacto para toda la historia del proyecto. Los cuatro entrenamientos de esta comparación usan únicamente PlantVillage y conservan una regla de selección interna; aun así, la evaluación externa debe interpretarse como descriptiva y requiere futura confirmación en una cohorte independiente.")

H("3 2 Fuentes y control de calidad",2)
P("La descarga de PlantVillage se fijó en la revisión 7f7ecc7e1eaca78107e3affe7cb5abd9427e139a [11]. Se utilizaron 2152 imágenes RGB de papa: 152 sanas, 1000 etiquetadas como tizón tardío y 1000 como tizón temprano. El subconjunto de PlantDoc se fijó en la revisión 5467f6012d78d1c446145d5f582da6096f852ae8 [12] y aportó inicialmente 222 imágenes. Se conservaron las etiquetas públicas sin añadir confirmación fitopatológica. La clase de tizón temprano se agrupó como otra enfermedad foliar; esta agrupación no representa toda la diversidad de enfermedades de la papa.")
P("El procedimiento calculó hashes SHA-256 para duplicados exactos y dHash de 64 bits con umbral de distancia de Hamming de cuatro para semejanza perceptual. Se combinaron las relaciones de semejanza con el identificador de hoja de PlantVillage. Las 538 hojas físicas originaron 537 grupos finales por una unión adicional de semejanza. En PlantDoc se retiraron cinco duplicados exactos y se aislaron nueve imágenes con conflicto de etiqueta, quedando 208 imágenes en 206 grupos. No se reasignaron manualmente las etiquetas de los conflictos para aumentar el tamaño de evaluación.")
P("El conjunto limpio contiene 2360 imágenes y 743 grupos finales. El agrupamiento reduce una vía de filtración, pero un hash perceptual no reconoce todas las duplicaciones semánticas ni demuestra independencia por parcela, ubicación o fecha. Los grupos disponibles tampoco sustituyen identificadores de plantas y campañas ausentes en los datos públicos.")

table("Tabla 1. Composición de los datos usados en la comparación.",
      ["Conjunto","Imágenes","Sano","Tizón tardío","Otra enfermedad"],
      [["PlantVillage entrenamiento","1724","124","800","800"],
       ["PlantVillage validación","428","28","200","200"],
       ["PlantDoc evaluación externa","208","0","98","110"],
       ["Total limpio","2360","152","1098","1110"]],
      [6.0,2.0,2.0,3.0,3.0])
P("Las condiciones de reutilización declaradas por las fuentes se registraron en el proyecto: CC BY-SA 3.0 para PlantVillage y CC BY 4.0 para PlantDoc. Estas declaraciones deben acompañar cualquier redistribución y no constituyen una auditoría independiente de derechos sobre cada fotografía recopilada de internet. El artículo proporciona procedencia y versiones; no adjunta ni publica nuevamente el corpus de imágenes.")

H("3 3 Partición y preparación de imágenes",2)
P("Se generaron cinco pliegues estratificados por clase y restringidos por grupo, con semilla 2026. Sus tamaños fueron 428, 428, 432, 432 y 432 imágenes. En la numeración del registro, el pliegue 1 fue la validación utilizada para esta comparación: 428 imágenes frente a 1724 de entrenamiento. No hubo grupos compartidos entre ambas particiones según el manifiesto. PlantDoc se mantuvo fuera del entrenamiento y de la estimación de temperatura de los cuatro modelos.")
P("Durante el entrenamiento se aplicaron recorte aleatorio redimensionado a 224 × 224 píxeles con escala de 0,75 a 1, volteos horizontal y vertical, rotación de hasta 15 grados y variaciones de brillo, contraste y saturación de 0,15 y de tono de 0,03. En validación y evaluación externa se redimensionó a 256 píxeles y se tomó un recorte central de 224 × 224. Las imágenes se normalizaron con los parámetros de ImageNet. No se aplicó desenfoque ni se realizó agrupamiento mediante embeddings. El recorte central podría excluir lesiones periféricas y constituye una decisión de preprocesamiento que deberá revisarse con evidencia adicional.")

H("3 4 Entrenamiento en la GPU local",2)
P("Los modelos se inicializaron con pesos de ImageNet cuya procedencia queda fijada en model_sources.json [13]. Se usaron timm 1.0.31, torchvision 0.22.1 y PyTorch 2.7.1 con CUDA 12.8 en una NVIDIA GeForce RTX 3050 Laptop GPU de 4 GiB. El código exige CUDA para esta comparación. Se emplearon cuatro hilos de CPU y ningún proceso adicional de carga de datos. No se midió el mismo protocolo en Colab ni en CPU, por lo que no se informa una ventaja temporal frente a esos entornos.")
P("El protocolo común empleó AdamW, tasa inicial de aprendizaje de 0,0003, decaimiento de pesos de 0,0001, entropía cruzada ponderada por frecuencia inversa de clase y suavizado de etiquetas igual a cero. El lote físico fue de 16 imágenes, con acumulación de dos pasos para un lote efectivo de 32. Se entrenaron todas las capas desde el inicio, con recorte de norma del gradiente a uno y programación coseno de la tasa de aprendizaje con horizonte de 16 épocas. Se fijó un máximo de 16 épocas, paciencia de cuatro y límite de 15 minutos por ejecución.")
P("ResNet50 y EfficientNetV2 B0 utilizaron precisión mixta FP16. Un intento inicial de MobileNetV4 con FP16 produjo valores no finitos y se excluyó de la comparación. Las ejecuciones válidas de MobileNetV4 y EfficientViT utilizaron BF16. Esta decisión se documenta como parte del protocolo y limita atribuir todas las diferencias exclusivamente a la arquitectura. La auditoría de migración conservó los hashes de las ejecuciones FP16 válidas. El tiempo reportado corresponde a cada entrenamiento exitoso registrado y no incluye descargas, pruebas de compatibilidad, el intento fallido ni la evaluación externa posterior.")

image("figura1_metodologia_600dpi.png",
      "Figura 1. Metodología efectivamente ejecutada. PlantDoc se reserva del ajuste de estos cuatro modelos y se interpreta como evaluación descriptiva por su observación en una fase previa. El diagrama no representa validación cruzada completa ni validación prospectiva en campo.",15.6)

H("3 5 Métricas y elección del candidato",2)
P("Se calcularon exactitud, F1 macro, coeficiente de correlación de Matthews y matrices de confusión. El F1 de una clase equivale al doble del producto de precisión y sensibilidad dividido por su suma; el promedio macro asigna el mismo peso a cada clase incluida. En PlantVillage se promedian tres clases. En PlantDoc se promedian solamente sus dos clases de referencia presentes; las predicciones de sano continúan contando como errores para la clase verdadera. Por tanto, comparar directamente ambos F1 mezcla cambio de datos y cambio del conjunto de clases promediadas.")
P("Para una comparación secundaria con las mismas clases de referencia se retiraron las 28 hojas sanas de la validación interna y se recalculó F1 macro sobre las 400 imágenes enfermas restantes, manteniendo las tres salidas posibles. Las diferencias entre este F1 interno y el externo se expresan en puntos porcentuales. Este análisis posterior iguala las clases evaluadas, pero no iguala prevalencia, contexto de captura ni criterios de anotación; sus diferencias no estiman un efecto causal del dominio.")
P("La regla de selección registrada antes de incorporar los resultados externos consistió en elegir el modelo de menor tiempo entre los que alcanzaran un F1 interno al menos igual al máximo entre la referencia piloto de 0,979324 y el ResNet50 actual de 0,993108. La regla compara estimaciones puntuales de un solo pliegue y no constituye una prueba estadística de no inferioridad. PlantDoc no intervino en esa elección. Además de métricas globales, se examinaron sensibilidad, especificidad y valor predictivo positivo para la clase compatible con tizón tardío.")

H("3 6 Calibración y auditoría numérica",2)
P("Se ajustó una temperatura escalar por modelo mediante minimización de pérdida logarítmica en la misma validación interna usada para seleccionar la mejor época. El ajuste utilizó L-BFGS sobre el logaritmo de la temperatura; después de optimizar, el resultado se recortó al intervalo de 0,05 a 20. Se aplicó la temperatura congelada al conjunto externo. Al no existir un conjunto independiente de calibración, las métricas internas posteriores al ajuste son optimistas como evaluación de generalización y no deben interpretarse como una validación separada.")
P("El error de calibración esperado, ECE, se calculó con 15 intervalos de confianza, ponderando la diferencia absoluta entre exactitud y confianza media de cada intervalo por su frecuencia. También se informó la pérdida logarítmica negativa, NLL, expresada como media por imagen. La NLL archivada por el evaluador original recorta probabilidades a un mínimo de 0,000000000001. Ese recorte impone una penalización máxima aproximada de 27,631 por observación y puede ocultar errores extremos.")
P("Para el manuscrito se añadió una auditoría estable de NLL directamente en log-espacio, usando logsumexp sobre los logits de los modelos congelados. Se reprodujeron las ocho matrices de confusión y se verificaron los hashes de los cuatro pesos. No se reentrenaron redes, no se recalibraron temperaturas y no se reemplazaron silenciosamente las métricas archivadas. Las tablas de este artículo identifican explícitamente la NLL estable; los archivos originales permiten contrastar ambas definiciones. Que BF16 evite valores no finitos no garantiza logits bien escalados ni probabilidades confiables.")

H("3 7 Incertidumbre y trazabilidad",2)
P("Se estimaron intervalos de confianza percentiles del 95 % para el F1 externo mediante 5000 remuestreos con reemplazo de los 206 grupos perceptuales de PlantDoc, con semilla 20261118. Cada grupo aporta todas sus imágenes y los cuatro modelos comparten las mismas extracciones de grupos. El principio de remuestreo se basa en bootstrap [14]; la unidad elegida aquí es el grupo disponible, no una parcela de campo. Los intervalos son condicionales a este conjunto observado y no incorporan variación entre entrenamientos, campañas agrícolas ni incertidumbre de las etiquetas.")
P("Se conservaron identificadores de ejecución, hashes de checkpoints, configuración y manifiesto. La reproducción volvió a obtener las matrices completas de validación y PlantDoc a partir de los pesos guardados. Los gráficos y tablas del artículo se generan de los resultados congelados y del análisis derivado. Las verificaciones de clasificación no constituyen una garantía de determinismo en cualquier dispositivo, biblioteca o modo de precisión.")


H("4 Resultados")
H("4 1 Convergencia y recursos de entrenamiento",2)
P("Las cuatro ejecuciones válidas terminaron en menos de cinco minutos. La suma de los tiempos registrados fue de 758,46 segundos, equivalente a 12 minutos y 38 segundos. MobileNetV4 fue el más rápido con 149,61 segundos; EfficientViT B1 requirió 270,29 segundos. El mayor pico de memoria CUDA asignada fue de ResNet50, 1216,41 MiB. La unidad es MiB porque el registro divide bytes entre 1024², aunque el campo original utiliza el sufijo mb. Esta medida no equivale a toda la memoria reservada por el controlador ni al consumo total de la GPU.")
table("Tabla 2. Ejecuciones válidas en la RTX 3050 Laptop.",
      ["Modelo","Parámetros en millones","Tiempo s","Pico CUDA MiB","Épocas total y mejor","Precisión"],
      [[names[i],F(m["parameters"]/1e6,2),F(m["metrics"]["train_seconds"],2),
        F(m["metrics"]["gpu_peak_memory_mb"],1),
        str(len(m["history"]["val_macro_f1_epoch"]))+" / "+str(m["best_epoch"]),
        {"float16":"FP16","bfloat16":"BF16"}[m["train"]["amp_dtype"]]]
       for i,m in enumerate(models)],
      [4.1,2.5,2.2,2.6,2.7,1.9])
P("El F1 interno fue de 0,9931 para ResNet50, 0,9933 para EfficientNetV2 B0, 0,9867 para MobileNetV4 y 1,0000 para EfficientViT B1. La diferencia entre los dos primeros corresponde a distintos errores aislados en la clase minoritaria, no a una validación amplia de superioridad. EfficientViT acertó las 428 imágenes de validación. Sus curvas muestran convergencia dentro del presupuesto establecido, aunque una trayectoria por modelo no permite estimar estabilidad entre semillas.")
image("figura2_aprendizaje_600dpi.png",
      "Figura 2. F1 macro de validación durante cada entrenamiento válido. Las marcas identifican la época seleccionada. Se muestra un único pliegue; el eje vertical comienza en 0,60 para facilitar la lectura de la convergencia.")

H("4 2 Rendimiento externo y comparación de clases",2)
P("El rendimiento externo fue sustancialmente menor en las cuatro arquitecturas. MobileNetV4 obtuvo el mayor F1 macro puntual en PlantDoc, 0,5849, mientras que EfficientViT alcanzó la mayor exactitud, 0,5865. EfficientNetV2 presentó el menor F1 externo, 0,5043. El orden cambia según la métrica porque las clases y los tipos de error tienen efectos distintos sobre cada promedio.")
table("Tabla 3. Clasificación interna y externa con modelos congelados.",
      ["Modelo","F1 interno tres clases","F1 PlantDoc dos clases","IC 95 % F1 PlantDoc","Exactitud PlantDoc","MCC PlantDoc"],
      [[names[i],F(m["metrics"]["val_macro_f1"],4),
        F(audit[m["architecture"]]["external_f1_two"],4),
        F(audit[m["architecture"]]["external_cluster_bootstrap_f1_ci95"][0],3)+" a "+F(audit[m["architecture"]]["external_cluster_bootstrap_f1_ci95"][1],3),
        F(m["metrics"]["external_plantdoc_papa_accuracy"],4),
        F(m["metrics"]["external_plantdoc_papa_mcc"],4)]
       for i,m in enumerate(models)],
      [4.0,2.4,2.4,3.1,2.3,1.8])
P("Los intervalos por remuestreo de grupos fueron amplios: 0,508–0,648 en ResNet50, 0,433–0,571 en EfficientNetV2, 0,512–0,650 en MobileNetV4 y 0,503–0,639 en EfficientViT. Se presentan como incertidumbre condicional del F1 de cada modelo. El solapamiento de intervalos marginales no se interpreta como una prueba de igualdad, ausencia de diferencia o equivalencia entre redes; no se realizó una prueba pareada de superioridad.")
P("La comparación secundaria con las mismas dos clases de referencia arrojó F1 internos de 1,0000, 0,9987, 0,9800 y 1,0000, respectivamente. Frente a PlantDoc, las brechas fueron de 42,10, 49,44, 39,51 y 42,69 puntos porcentuales. Esta corrección confirma que el descenso descriptivo persiste al igualar las clases promediadas, aunque no permite atribuir su magnitud únicamente al contexto de captura.")
image("figura3_transferencia_600dpi.png",
      "Figura 3. Comparación secundaria del F1 macro sobre las dos clases enfermas presentes en ambos conjuntos. La validación interna incluye 400 imágenes y PlantDoc 208. Las barras de error corresponden al IC percentil del 95 % por remuestreo de grupos externos. La comparación no ajusta diferencias de prevalencia ni anotación.")

H("4 3 Errores de clasificación relevantes para la aplicación",2)
P("En las 98 imágenes de PlantDoc etiquetadas como tizón tardío, EfficientViT clasificó correctamente 82 y MobileNetV4 71. ResNet50 acertó 56 y EfficientNetV2 28. El mayor número de aciertos de EfficientViT en esta clase se acompañó de 68 imágenes de otra enfermedad clasificadas como tizón tardío, frente a 41 en ResNet50. Esta distribución exige considerar el costo de falsos positivos y falsos negativos antes de definir umbrales de uso.")
table("Tabla 4. Métricas externas de la clase compatible con tizón tardío.",
      ["Modelo","Sensibilidad","Especificidad","Valor predictivo positivo","Sensibilidad de otra enfermedad"],
      [[names[i],
        F(m["metrics"]["external_plantdoc_papa_sensitivity_sintomas_compatibles_tizon_tardio"],3),
        F(m["metrics"]["external_plantdoc_papa_specificity_sintomas_compatibles_tizon_tardio"],3),
        F([56/97,28/52,71/128,82/150][i],3),
        F([61/110,81/110,49/110,40/110][i],3)] for i,m in enumerate(models)],
      [4.0,2.7,2.7,2.6,3.8])
P("Las cuatro redes emitieron también predicciones de sano sobre referencias enfermas: 12 casos en ResNet50, 11 en EfficientNetV2, nueve en MobileNetV4 y tres en EfficientViT. Como PlantDoc no contiene hojas sanas en este subconjunto, no puede estimarse su sensibilidad externa para sano ni una especificidad del tizón frente a sanos. La especificidad de la tabla 4 usa como negativos las imágenes de otra enfermedad, no una población de hojas sanas.")
image("figura4_matrices_600dpi.png",
      "Figura 4. Matrices de confusión externas. Las filas son referencias públicas y las columnas predicciones; TT indica síntomas compatibles con tizón tardío. La fila sana es cero porque el subconjunto no incluye referencias de esa clase. Se mantiene la misma escala de color entre modelos.",14.2)

H("4 4 Calibración y estabilidad numérica",2)
P("Las temperaturas estimadas fueron 0,5363 para ResNet50, 0,1050 para EfficientNetV2, 20 para MobileNetV4 y 0,5336 para EfficientViT. En MobileNetV4 se alcanzó el límite superior permitido; el valor no demuestra que se haya encontrado un óptimo sin restricciones. La temperatura positiva conserva la clase de máxima probabilidad, por lo que las matrices de clasificación son iguales antes y después de esta transformación.")
table("Tabla 5. Temperatura y calibración externa antes y después del ajuste interno.",
      ["Modelo","T","ECE antes","ECE después","NLL estable antes","NLL estable después"],
      [[names[i],F(m["metrics"]["temperature"],3),
        F(m["evaluation"]["external_plantdoc_papa"]["calibration"]["before"]["ece"],4),
        F(m["evaluation"]["external_plantdoc_papa"]["calibration"]["after"]["ece"],4),
        F(audit[m["architecture"]]["diagnostics"]["external_plantdoc_papa"]["stable_nll"]["before"],4),
        F(audit[m["architecture"]]["diagnostics"]["external_plantdoc_papa"]["stable_nll"]["after"],4)]
       for i,m in enumerate(models)],
      [4.1,1.5,2.3,2.3,2.9,2.9])
P("El ECE externo aumentó de 0,2452 a 0,3304 en ResNet50, de 0,4035 a 0,4756 en EfficientNetV2 y de 0,3558 a 0,3823 en EfficientViT. MobileNetV4 mostró el comportamiento opuesto, con reducción de 0,4046 a 0,0700. La NLL externa estable sigue esa dirección general: empeora en los tres primeros modelos con temperatura menor que uno y mejora en MobileNetV4, de 9,2042 a 1,0287. La NLL de EfficientNetV2 después de calibrar asciende a 31,2448, valor que el recorte del evaluador original no podía reflejar correctamente.")
image("figura5_calibracion_600dpi.png",
      "Figura 5. ECE externo antes y después de aplicar la temperatura estimada con validación interna. Un valor menor indica menor discrepancia entre confianza y exactitud según los 15 intervalos usados. No equivale a una validación de seguridad agronómica.")
P("El caso de MobileNetV4 ilustra el efecto del cálculo numérico. En validación interna, la NLL estable descendió de 201,4215 a 10,3292 con temperatura 20; el cálculo archivado con probabilidades recortadas mostraba 0,2783 y 0,4995. Inferir un fracaso del optimizador a partir de esa última pareja sería incorrecto porque el recorte había ocultado la mayor parte de la penalización original. Al mismo tiempo, su ECE interno empeoró de 0,0164 a 0,1964. Reducir NLL no implica necesariamente reducir el ECE de intervalos. Estas observaciones justifican informar ambos indicadores y conservar explícitamente la definición numérica empleada.")

H("4 5 Selección e integración en PapaSana",2)
P("La regla interna seleccionó ResNet50. EfficientNetV2 superó por una pequeña diferencia su F1, pero requirió más tiempo; EfficientViT obtuvo el mejor F1 interno con mayor duración. MobileNetV4 fue el más rápido, pero no alcanzó el umbral interno fijado. Esta elección se conserva como resultado del procedimiento y no se reinterpreta como selección por rendimiento en PlantDoc. Tampoco implica que ResNet50 esté validado para uso en campo.")
P("El laboratorio de PapaSana presenta la comparación de cuatro modelos, curvas de entrenamiento, matrices, métricas de calibración, exploración de datos y un diagrama metodológico. Las figuras de la aplicación se exportan como PNG con metadatos de 600 dpi y ancho físico configurable; las tablas se copian como HTML con formato y texto de respaldo. El manuscrito incorpora figuras científicas generadas a 600 dpi. La densidad de exportación facilita la maquetación, pero no agrega información experimental a los resultados.")
P("La carga del informe utiliza un snapshot verificable con identificadores, procedencia y limitaciones, sin depender de consultar MLflow durante la visualización. La publicación de estos resultados no modifica automáticamente el modelo servido por el diagnóstico. La selección científica, la promoción operativa y la validación agronómica son decisiones distintas en el ciclo del sistema.")

H("5 Discusión")
H("5 1 Transferencia entre conjuntos y utilidad práctica",2)
P("El principal hallazgo es la separación entre rendimiento interno y externo. El control por grupos evita compartir imágenes de una misma hoja identificada entre entrenamiento y validación, pero no elimina diferencias en fondos, iluminación, encuadre, severidad o criterios de etiqueta entre fuentes. PlantDoc tampoco constituye una muestra prospectiva de la población objetivo. Por ello, el descenso observado es compatible con un problema de transferencia, aunque este diseño no permite aislar qué factores lo producen.")
P("La hipótesis de aprendizaje de atajos visuales [9] motiva futuras pruebas con fondos controlados, segmentación o capturas repetidas, sin darla por demostrada. Para PapaSana, un F1 interno elevado sirve como comprobación de ajuste al corpus, pero ofrece evidencia insuficiente para automatizar una recomendación de manejo agrícola. La colección de una cohorte local, con metadatos por planta y validación de especialistas, tiene mayor prioridad que seguir ajustando modelos sobre PlantDoc hasta mejorar su puntuación.")
P("Las diferencias entre sensibilidad al tizón y reconocimiento de otras enfermedades muestran por qué no basta con ordenar redes por exactitud. EfficientViT identifica más referencias de tizón tardío, pero también asigna esa categoría a muchas imágenes de otra enfermedad. La elección de un umbral o política de abstención requiere costos agronómicos, prevalencia y capacidad de revisión que no se midieron aquí. No sería justificable derivarlos solamente del mayor F1 o de la menor duración de entrenamiento.")

H("5 2 Interpretación de la incertidumbre y la calibración",2)
P("La mejora de calibración interna no fue transportable de manera uniforme. En tres arquitecturas, temperaturas menores que uno aumentaron la confianza y empeoraron las métricas externas de calibración. La excepción de MobileNetV4 debe interpretarse junto con su escala extrema de logits y el límite de temperatura. No demuestra que una única técnica de calibración resuelva de forma general la incertidumbre fuera de distribución.")
P("La auditoría numérica añade un hallazgo metodológico relevante para estudios pequeños: métricas con la misma denominación pueden diferir de manera material si recortan probabilidades en lugar de trabajar en log-espacio. En este caso, la diferencia alteraba incluso la dirección aparente de la mejora interna de MobileNetV4. La conservación de logits o la posibilidad de reconstruirlos a partir de pesos y datos permite detectar ese problema sin modificar retrospectivamente los experimentos.")
P("Los intervalos externos incorporan dependencia entre imágenes perceptualmente relacionadas, pero no resuelven la falta de repetición de entrenamiento ni el posible ruido de etiquetas. Un resultado puntual de 0,5849 frente a 0,5790 no sustenta una afirmación de superioridad. Para contrastar redes se requieren un protocolo independiente, unidades de muestreo de campo y un análisis pareado preespecificado con potencia y efecto de interés definidos.")

H("5 3 Recursos y reproducibilidad",2)
P("La comparación demuestra que estas cuatro configuraciones pueden ajustarse en una GPU de laptop de 4 GiB dentro del presupuesto temporal registrado. No demuestra que una arquitectura sea intrínsecamente más eficiente en cualquier hardware, resolución o precisión. El protocolo común permite una comparación práctica acotada, pero no iguala el potencial de optimización de cada red; configuraciones propias de arquitectura podrían modificar el orden.")
P("La implementación exportable aporta trazabilidad entre experimento y comunicación científica. No sustituye revisión de datos ni aumenta la validez de una métrica por presentarla en una figura de alta resolución. Mantener el manifiesto, los hashes y los identificadores de ejecución permite comprobar qué cálculo sustenta cada tabla y distinguir las mediciones originales de los análisis posteriores.")

H("5 4 Limitaciones y siguiente validación",2)
P("El estudio usa un solo pliegue y una semilla por modelo, con selección de época y temperatura sobre la misma validación. El piloto previo y la observación histórica de PlantDoc limitan su independencia. El corpus tiene pocos sanos en PlantVillage y ninguno en el subconjunto externo; no representa variedades, regiones y etapas del cultivo de forma controlada. Los grupos perceptuales son aproximaciones y faltan identificadores externos por planta, parcela y fecha.")
P("Las etiquetas públicas no se confirmaron mediante examen agronómico o de laboratorio. No se midieron enfermedad presintomática, tiempo hasta detección, calidad de Grad-CAM frente a máscaras de lesión, efecto de alertas climáticas, utilidad de decisiones, latencia de inferencia en dispositivos finales ni consumo energético. No existen datos de usuarios de campo ni evidencia de beneficios productivos. Estas limitaciones excluyen presentar la aplicación como un diagnóstico etiológico o una intervención validada.")
P("La siguiente evaluación debe fijar previamente un conjunto local independiente con hojas sanas y varias enfermedades, confirmar etiquetas con especialistas y separar entrenamiento, selección y calibración. Se propone repetir semillas y pliegues agrupados por planta o parcela, conservar un conjunto externo intacto y evaluar abstención, calibración y costos de error. Las alertas climáticas y la revisión agronómica deberán estudiarse como componentes adicionales con sus propios resultados.")

H("6 Conclusiones")
P("Cuatro arquitecturas preentrenadas alcanzaron F1 macro interno entre 0,9867 y 1,0000 con entrenamientos válidos de 149,6 a 270,3 segundos en una RTX 3050 Laptop. La evaluación descriptiva en PlantDoc obtuvo F1 de 0,5043 a 0,5849 y evidenció una transferencia limitada incluso al comparar las mismas dos clases de referencia. El mejor rendimiento interno y el menor tiempo no identificaron un ganador externo validado.")
P("La temperatura estimada internamente no mejoró de forma uniforme la calibración externa. El análisis estable de NLL mostró que el recorte de probabilidades ocultaba penalizaciones extremas y podía conducir a una lectura equivocada del ajuste. ResNet50 permanece como candidato de la regla interna registrada, sujeto a una evaluación independiente antes de su promoción para uso de campo.")
P("PapaSana integra resultados reproducibles y exportables para apoyar la elaboración del artículo. El aporte actual es experimental y metodológico: comparación de modelos, auditoría de calibración y trazabilidad del reporte. La detección temprana, la confirmación del agente causal y la utilidad agronómica permanecen como objetivos por validar.")


H("Disponibilidad de datos y código")
P("El código base de PapaSana se encuentra en https://github.com/Janoq25/papasana/. Las fuentes de imágenes y sus revisiones se indican en las referencias y en los archivos de procedencia. La versión local usada para este manuscrito conserva configuraciones, manifiesto, registros, pesos y análisis derivados. No se afirma que todos estos artefactos locales estén ya publicados en el repositorio remoto ni depositados con DOI. La preparación de un paquete público reproducible y su revisión de licencias quedan pendientes antes de someter el manuscrito.")
P("Los datos derivados se encuentran en ml/data/comparacion-cuatro/results.json y en backend/app/data/training_reports/papasana-cuatro-gpu-20261118.json. El análisis secundario y las figuras se conservan en docs/articulo-20261118. El archivo analisis_derivado.json contiene los intervalos por grupos y la NLL estable; analysis.py registra el procedimiento de reconstrucción de predicciones. No se incluyen datos personales de agricultores en esta evaluación de imágenes públicas.")

H("Declaraciones de autoría y preparación")
P("La autoría se conserva como Quiroz Rodríguez y Zavaleta Carranza, de acuerdo con el entregable previo. La distribución individual de contribuciones CRediT, afiliaciones, ORCID, correspondencia, financiación y declaración de conflictos debe ser completada y confirmada por los autores antes del envío. No se atribuyen aprobaciones éticas, financiamiento ni validaciones institucionales que no estén documentadas.")
P("Se utilizaron herramientas basadas en modelos de lenguaje para asistir en la revisión del flujo computacional, generación de scripts y preparación del borrador. La evidencia numérica procede de artefactos de ejecución y verificaciones descritas en métodos. Los autores deben revisar el contenido, las referencias y la exactitud del análisis y asumir responsabilidad por la versión final. Este texto es un manuscrito de trabajo; no acredita aceptación editorial ni clasificación Q1 o Q2.")

H("Referencias")
refs=[
("1","Mohanty SP, Hughes DP, Salathé M. Using Deep Learning for Image-Based Plant Disease Detection. Frontiers in Plant Science. 2016;7:1419. doi:10.3389/fpls.2016.01419.",
"https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2016.01419/full"),
("2","Singh D, Jain N, Jain P, Kayal P, Kumawat S, Batra N. PlantDoc: A Dataset for Visual Plant Disease Detection. CODS COMAD. 2020. doi:10.1145/3371158.3371196. Prepublicación de los autores de 2019.",
"https://arxiv.org/abs/1911.10317"),
("3","He K, Zhang X, Ren S, Sun J. Deep Residual Learning for Image Recognition. CVPR. 2016:770–778. doi:10.1109/CVPR.2016.90.",
"https://openaccess.thecvf.com/content_cvpr_2016/html/He_Deep_Residual_Learning_CVPR_2016_paper.html"),
("4","Tan M, Le QV. EfficientNetV2: Smaller Models and Faster Training. Proceedings of Machine Learning Research. 2021;139:10096–10106.",
"https://proceedings.mlr.press/v139/tan21a.html"),
("5","Qin D et al. MobileNetV4: Universal Models for the Mobile Ecosystem. ECCV. 2024. doi:10.1007/978-3-031-73661-2_5.",
"https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/05647.pdf"),
("6","Cai H, Li J, Hu M, Gan C, Han S. EfficientViT: Lightweight Multi-Scale Attention for High-Resolution Dense Prediction. ICCV. 2023:17302–17313.",
"https://openaccess.thecvf.com/content/ICCV2023/html/Cai_EfficientViT_Lightweight_Multi-Scale_Attention_for_High-Resolution_Dense_Prediction_ICCV_2023_paper.html"),
("7","Guo C, Pleiss G, Sun Y, Weinberger KQ. On Calibration of Modern Neural Networks. Proceedings of Machine Learning Research. 2017;70:1321–1330.",
"https://proceedings.mlr.press/v70/guo17a.html"),
("8","Selvaraju RR et al. Grad-CAM: Visual Explanations From Deep Networks via Gradient-Based Localization. ICCV. 2017:618–626. doi:10.1109/ICCV.2017.74.",
"https://openaccess.thecvf.com/content_iccv_2017/html/Selvaraju_Grad-CAM_Visual_Explanations_ICCV_2017_paper.html"),
("9","Geirhos R et al. Shortcut learning in deep neural networks. Nature Machine Intelligence. 2020;2:665–673. doi:10.1038/s42256-020-00257-z.",
"https://www.nature.com/articles/s42256-020-00257-z"),
("10","Kapoor S, Narayanan A. Leakage and the reproducibility crisis in machine-learning-based science. Patterns. 2023;4:100804. doi:10.1016/j.patter.2023.100804.",
"https://arxiv.org/abs/2207.07048"),
("11","Mohanty SP y colaboradores. PlantVillage Dataset. Documentación de datos y archivo de identificación de hojas. Revisión 7f7ecc7e1eaca78107e3affe7cb5abd9427e139a. Consultado el 18 de noviembre de 2026.",
"https://raw.githubusercontent.com/spMohanty/PlantVillage-Dataset/7f7ecc7e1eaca78107e3affe7cb5abd9427e139a/README_HF.md"),
("12","Kayal P y colaboradores. PlantDoc Dataset. Repositorio de datos. Revisión 5467f6012d78d1c446145d5f582da6096f852ae8. Consultado el 18 de noviembre de 2026.",
"https://github.com/pratikkayal/PlantDoc-Dataset/tree/5467f6012d78d1c446145d5f582da6096f852ae8"),
("13","timm. Fichas de los modelos pretrained ResNet50, EfficientNetV2 B0, MobileNetV4 Conv Medium y EfficientViT B1. Las revisiones de pesos se conservan en model_sources.json. Consultado el 18 de noviembre de 2026.",
"https://huggingface.co/timm/resnet50.a1_in1k ; https://huggingface.co/timm/tf_efficientnetv2_b0.in1k ; https://huggingface.co/timm/mobilenetv4_conv_medium.e500_r224_in1k ; https://huggingface.co/timm/efficientvit_b1.r224_in1k"),
("14","Efron B. Bootstrap Methods: Another Look at the Jackknife. The Annals of Statistics. 1979;7:1–26. doi:10.1214/aos/1176344552.",
"https://doi.org/10.1214/aos/1176344552")
]
for n,bib,url in refs:
    p=P("["+n+"] "+bib+" "+url)
    p.paragraph_format.space_after=Pt(7)
    for run in p.runs:run.font.size=Pt(10)
(BASE/"fuentes.json").write_text(json.dumps([{"id":n,"reference":b,"url":u} for n,b,u in refs],ensure_ascii=False,indent=2),encoding="utf-8")

H("Apéndice A Identificación de los experimentos")
P("La siguiente identificación corresponde a las ejecuciones válidas y al manifiesto utilizado. El intento FP16 no finito de MobileNetV4 queda fuera de estas cuatro filas. La semilla de entrenamiento es 2026; el bootstrap usa la semilla 20261118 con 5000 réplicas y 206 grupos externos.")
table("Tabla A1. Identificadores de las ejecuciones reportadas.",
      ["Modelo","Run ID"],
      [[names[i],m["run_id"]] for i,m in enumerate(models)],[6.0,10.0])
P("SHA-256 del manifiesto: "+a["manifest_sha256"])
P("Huella del contrato de comparación: "+a["source_fingerprint"])
P("Los hashes de pesos coinciden entre el snapshot y la reconstrucción de predicciones. Se reprodujeron las cuatro matrices internas y las cuatro externas. Las figuras incluidas contienen metadatos de 600 dpi. El conjunto de comparaciones no incorpora validación cruzada completa, búsqueda de hiperparámetros ejecutada ni validación agronómica prospectiva.")
doc.save(OUT)
(BASE/"manuscrito.md").write_text("\n".join(text),encoding="utf-8")
(BASE/"work/artifact.md").write_text(
    "Manuscrito nuevo basado en los resultados congelados del 18 de noviembre de 2026.\n"
    "Referencia académica: articulo_q1.docx original preservado. Times New Roman, texto negro y estructura IMRyD ampliada.\n"
    "Página Letter con figuras científicas a 600 dpi, tablas editables y encabezados negros sin líneas decorativas.\n"
    "No se inventan afiliaciones, financiación, validación de campo ni resultados de CV.\n"
    "NLL estable y bootstrap son análisis secundarios identificados. Renderizar e inspeccionar todas las páginas antes de entregar.\n",
    encoding="utf-8")
print(json.dumps({"docx":str(OUT),"bytes":OUT.stat().st_size,"paragraphs":len(doc.paragraphs),"tables":len(doc.tables),"figures":len(doc.inline_shapes)},ensure_ascii=False))

