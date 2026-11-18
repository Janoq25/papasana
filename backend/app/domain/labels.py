"""Esquema de etiquetas por síntoma (docs/decisiones.md D-01).

El modelo predice SÍNTOMAS, no el patógeno. "Confirmado" solo lo asigna un especialista en la
validación por experto, con evidencia.
"""

# Clases que predice el modelo
MODEL_CLASSES = ("sano", "sintomas_compatibles_tizon_tardio", "otra_enfermedad_foliar")

MODEL_CLASS_LABELS = {
    "sano": "Sano",
    "sintomas_compatibles_tizon_tardio": "Síntomas compatibles con tizón tardío",
    "otra_enfermedad_foliar": "Otra enfermedad foliar",
}

# Categorías que ve el usuario
CATEGORY_SANO = "sano"
CATEGORY_SOSPECHOSO = "sospechoso"
CATEGORY_TIZON = "tizon_tardio_compatible"
CATEGORIES = (CATEGORY_SANO, CATEGORY_SOSPECHOSO, CATEGORY_TIZON)

CATEGORY_LABELS = {
    CATEGORY_SANO: "Sano",
    CATEGORY_SOSPECHOSO: "Sospechoso",
    CATEGORY_TIZON: "Tizón tardío: síntomas compatibles",
}

# Estados del diagnóstico
STATUS_AUTOMATIC = "automatico"          # sano con confianza suficiente; no requiere revisión
STATUS_PENDING = "pendiente_revision"    # en la bandeja del especialista
STATUS_VALIDATED = "validado"            # el especialista confirmó la predicción
STATUS_CORRECTED = "corregido"           # el especialista cambió la etiqueta
STATUS_VOID = "anulado"

# Etiquetas finales que puede asignar el especialista
FINAL_LABELS = {
    "sano": "Sano",
    "tizon_tardio_sintomas": "Tizón tardío: síntomas compatibles (sin confirmación)",
    "tizon_tardio_confirmado": "Tizón tardío confirmado",
    "otra_enfermedad": "Otra enfermedad o daño (diagnóstico diferencial)",
    "no_determinable": "No determinable con la imagen",
}
EVIDENCE_TYPES = {
    "esporulacion": "Esporulación observada en campo (envés de la hoja)",
    "laboratorio": "Confirmación de laboratorio",
    "camara_humeda": "Prueba de cámara húmeda",
    "otro": "Otra evidencia documentada",
}

# Qué etiqueta final equivale a "confirmar" la categoría predicha
CONFIRMS = {
    CATEGORY_SANO: {"sano"},
    CATEGORY_TIZON: {"tizon_tardio_sintomas", "tizon_tardio_confirmado"},
    CATEGORY_SOSPECHOSO: set(),
}


def categorize(predicted_class: str, confidence: float, threshold: float) -> tuple[str, bool, str]:
    """Devuelve (categoría, requiere_revisión, estado).

    - requiere_revisión = confianza < umbral (§4.5 de la especificación).
    - "Sospechoso": confianza baja u otra enfermedad foliar; siempre va a la bandeja.
    - "Tizón tardío compatible": va a la bandeja para que un especialista lo confirme o corrija.
    - "Sano" con confianza suficiente: estado automático.
    """
    requires_review = confidence < threshold
    if requires_review or predicted_class == "otra_enfermedad_foliar":
        category = CATEGORY_SOSPECHOSO
    elif predicted_class == "sintomas_compatibles_tizon_tardio":
        category = CATEGORY_TIZON
    else:
        category = CATEGORY_SANO
    status = STATUS_AUTOMATIC if category == CATEGORY_SANO else STATUS_PENDING
    return category, requires_review, status
