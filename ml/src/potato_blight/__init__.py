"""potato_blight: entrenamiento y evaluación de los modelos de AP-01, separados de la aplicación.

Etiquetas por síntoma (docs/decisiones.md D-01): sano · sintomas_compatibles_tizon_tardio · otra_enfermedad_foliar.
"""

CLASSES = ["sano", "sintomas_compatibles_tizon_tardio", "otra_enfermedad_foliar"]
__version__ = "0.4.0"
