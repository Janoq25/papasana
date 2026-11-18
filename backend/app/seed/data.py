"""Datos semilla: módulos, matriz de permisos (docs/fase0_plan.md §4), departamentos y usuarios demo."""

# code, nombre, ruta, fase, requiere_permiso
MODULES = [
    ("dashboard", "Dashboard", "/dashboard", 3, True),
    ("parcelas", "Parcelas", "/parcelas", 2, True),
    ("catalogos", "Catálogos", "/catalogos", 2, True),
    ("diagnostico", "Captura y diagnóstico", "/diagnostico", 2, True),
    ("validacion", "Validación por experto", "/validacion", 2, True),
    ("laboratorio", "Laboratorio de modelos", "/laboratorio", 4, True),
    ("alertas", "Riesgo climático y alertas", "/alertas", 5, True),
    ("asistente", "Asistente IA", "/asistente", 6, True),
    ("base_documental", "Base documental RAG", "/base-documental", 6, True),
    ("reportes", "Reportes", "/reportes", 3, True),
    ("bitacora", "Bitácora de auditoría", "/bitacora", 1, True),
    ("usuarios", "Usuarios, roles y permisos", "/usuarios", 1, True),
    ("configuracion", "Configuración del sistema", "/configuracion", 1, True),
    ("datasets", "Datasets y licencias", "/datasets", 4, True),
    ("perfil", "Mi perfil", "/perfil", 1, False),
    ("notificaciones", "Notificaciones", "/notificaciones", 3, False),
    ("auth", "Autenticación", None, 1, False),
]

LETTER_TO_ACTION = {"V": "ver", "C": "crear", "E": "editar", "D": "eliminar", "X": "exportar", "A": "aprobar"}

# code, nombre, descripción, alcance de datos, matriz {módulo: letras}
ROLES = [
    ("ADMINISTRADOR", "Administrador", "Gestiona usuarios, roles, configuración y aprueba modelos.", "todo", {
        "dashboard": "VX", "parcelas": "VCEDX", "catalogos": "VCED", "diagnostico": "VDX", "validacion": "V",
        "laboratorio": "VA", "alertas": "VCEDXA", "asistente": "V", "base_documental": "VCED",
        "reportes": "VCX", "bitacora": "VX", "usuarios": "VCEDX", "configuracion": "VE", "datasets": "VCED",
    }),
    ("INVESTIGADOR", "Investigador / Científico de datos",
     "Entrena, evalúa y propone versiones de modelos; analiza resultados.", "todo", {
        "dashboard": "VX", "parcelas": "VX", "catalogos": "V", "diagnostico": "VX", "validacion": "V",
        "laboratorio": "VCEX", "alertas": "VX", "asistente": "V", "base_documental": "V", "reportes": "VCX",
        "configuracion": "V", "datasets": "VCEX",
    }),
    ("AGRONOMO", "Especialista agrónomo",
     "Valida diagnósticos (human-in-the-loop) y gestiona alertas de su región.", "region", {
        "dashboard": "VX", "parcelas": "VCEX", "catalogos": "VCE", "diagnostico": "VCX", "validacion": "VEA",
        "laboratorio": "V", "alertas": "VCEXA", "asistente": "V", "base_documental": "V", "reportes": "VCX",
        "datasets": "V",
    }),
    ("TECNICO", "Técnico de campo / Productor",
     "Registra parcelas asignadas y sube fotografías para diagnóstico.", "propio", {
        "dashboard": "V", "parcelas": "VCE", "catalogos": "V", "diagnostico": "VC", "alertas": "V",
        "asistente": "V", "reportes": "VCX",
    }),
    ("AUDITOR", "Auditor", "Acceso de solo lectura a la bitácora y los reportes.", "todo", {
        "reportes": "VX", "bitacora": "VX",
    }),
]

# Departamentos del Perú (código ubigeo INEI de 6 dígitos)
DEPARTAMENTOS = [
    ("010000", "Amazonas"), ("020000", "Áncash"), ("030000", "Apurímac"), ("040000", "Arequipa"),
    ("050000", "Ayacucho"), ("060000", "Cajamarca"), ("070000", "Callao"), ("080000", "Cusco"),
    ("090000", "Huancavelica"), ("100000", "Huánuco"), ("110000", "Ica"), ("120000", "Junín"),
    ("130000", "La Libertad"), ("140000", "Lambayeque"), ("150000", "Lima"), ("160000", "Loreto"),
    ("170000", "Madre de Dios"), ("180000", "Moquegua"), ("190000", "Pasco"), ("200000", "Piura"),
    ("210000", "Puno"), ("220000", "San Martín"), ("230000", "Tacna"), ("240000", "Tumbes"),
    ("250000", "Ucayali"),
]

# email, nombre, rol, institución, región
DEMO_USERS = [
    ("admin@demo.papasana.pe", "Ana Administradora", "ADMINISTRADOR", "Equipo PapaSana", "150000"),
    ("investigador@demo.papasana.pe", "Iván Investigador", "INVESTIGADOR", "Universidad (demo)", "150000"),
    ("agronomo@demo.papasana.pe", "Alicia Agrónoma", "AGRONOMO", "Agencia agraria (demo)", "120000"),
    ("tecnico@demo.papasana.pe", "Teodoro Técnico", "TECNICO", "Comunidad campesina (demo)", "120000"),
    ("auditor@demo.papasana.pe", "Aurora Auditora", "AUDITOR", "Control interno (demo)", "150000"),
]

# --- Fase 2: catálogos --------------------------------------------------------------------------
# Solo nombres de variedades cultivadas en el Perú. La susceptibilidad al tizón tardío se deja vacía:
# debe completarse con una fuente verificable (p. ej. fichas técnicas del INIA).
VARIETIES = [
    ("Yungay", "mejorada"), ("Canchán", "mejorada"), ("Única", "mejorada"), ("Perricholi", "mejorada"),
    ("Amarilis", "mejorada"), ("Huayro", "nativa"), ("Peruanita", "nativa"), ("Amarilla Tumbay", "nativa"),
]

# code, nombre, orden, descripción
STAGES = [
    ("emergencia", "Emergencia", 1, "Aparición de los brotes sobre la superficie del suelo."),
    ("vegetativo", "Desarrollo vegetativo", 2, "Crecimiento de tallos y hojas."),
    ("tuberizacion", "Inicio de tuberización", 3, "Formación de estolones e inicio de tubérculos."),
    ("floracion", "Floración", 4, "Aparición de botones florales y flores."),
    ("llenado", "Llenado de tubérculos", 5, "Engrosamiento de los tubérculos."),
    ("senescencia", "Senescencia / madurez", 6, "Amarillamiento del follaje y madurez de tubérculos."),
]

_SOURCE_DISEASES = "Descripción general de referencia; contrastar con material técnico de INIA/SENASA/FAO."
# nombre, agente, síntomas clave, rasgos distintivos, es_objetivo
DISEASES = [
    ("Tizón tardío", "Phytophthora infestans (oomiceto)",
     "Lesiones irregulares de aspecto acuoso, verde oscuro a marrón, a menudo desde bordes o puntas de la hoja.",
     "Con humedad alta puede verse un halo de esporulación blanquecina en el envés, en el margen de la lesión.",
     True),
    ("Tizón temprano", "Alternaria solani (hongo)",
     "Manchas marrones con anillos concéntricos (aspecto de diana), frecuentemente con halo amarillo.",
     "Suele empezar en hojas viejas (inferiores); lesiones más secas y delimitadas que las del tizón tardío.",
     False),
    ("Moho gris", "Botrytis cinerea (hongo)",
     "Lesiones marrones, a menudo en forma de cuña desde el borde de la hoja.",
     "Con humedad puede desarrollar un moho gris pulverulento.", False),
    ("Daño por helada", "Abiótico (temperaturas bajo cero)",
     "Ennegrecimiento y necrosis de tejidos tiernos después de una helada.",
     "Afecta de forma uniforme a las partes expuestas; sin esporulación ni anillos concéntricos.", False),
    ("Fitotoxicidad", "Abiótico (productos químicos)",
     "Quemaduras o manchas tras aplicaciones de agroquímicos.",
     "Patrón asociado a la aplicación (gotas, bordes); aparece en hojas tratadas al mismo tiempo.", False),
]

DEMO_MODEL = {
    "model_key": "demo-resnet50-imagenet-v1",
    "architecture": "resnet50",
    "display_name": "DEMO / no validado · ResNet50 (ImageNet) con cabeza sin entrenar",
    "stage": "demo",
    "is_demo": True,
    "label_scheme": "sintoma",
    "classes": ["sano", "sintomas_compatibles_tizon_tardio", "otra_enfermedad_foliar"],
    "temperature": 1.0,
    "notes": "Sin valor diagnóstico. Solo para probar el flujo de punta a punta (docs/decisiones.md D-16).",
}

# --- Fase 2: productores y parcelas de ejemplo (ficticios) ---------------------------------------
PRODUCERS = [
    ("Comunidad campesina demo de Sicaya", "120000"),
    ("Asociación de productores demo de Concepción", "120000"),
    ("Productor demo de Chinchero", "080000"),
]


def _rect(lon: float, lat: float, dlon: float = 0.0012, dlat: float = 0.0009) -> dict:
    ring = [[lon, lat], [lon + dlon, lat], [lon + dlon, lat + dlat], [lon, lat + dlat], [lon, lat]]
    return {"type": "Polygon", "coordinates": [ring]}


# code, nombre, índice de productor, región, variedad, estadio, altitud, geometría, asignar al técnico demo
PARCELS = [
    ("DEMO-JUN-001", "Parcela demo Sicaya alta", 0, "120000", "Yungay", "floracion", 3290,
     _rect(-75.2905, -12.0158), True),
    ("DEMO-JUN-002", "Parcela demo Sicaya baja", 0, "120000", "Canchán", "vegetativo", 3260,
     _rect(-75.2861, -12.0213), True),
    ("DEMO-JUN-003", "Parcela demo Concepción", 1, "120000", "Huayro", "tuberizacion", 3290,
     _rect(-75.3128, -11.9189), False),
    ("DEMO-CUS-001", "Parcela demo Chinchero", 2, "080000", "Peruanita", "floracion", 3760,
     _rect(-72.0498, -13.3921), False),
]

# --- Fase 4: registro de datasets (A1). Espejo de ml/datasets.yaml; NINGUNA licencia externa está verificada. ---
_PV_NOTE = ("Revisión preliminar del 2026-11-12 (sin verificar): el repositorio de GitHub no muestra una licencia en "
            "los resultados de búsqueda; Meta-Album indica CC0 1.0 para la publicación original "
            "(https://meta-album.github.io/datasets/PLT_VIL.html) y su versión en OpenML figura como CC BY-NC 4.0 "
            "(https://api.openml.org/d/44321). Hay que resolver la contradicción en la fuente oficial.")
_PD_NOTE = ("Revisión preliminar del 2026-11-12 (sin verificar): copias de terceros en Roboflow lo declaran CC BY 4.0 "
            "(https://public.roboflow.com/object-detection/plantdoc). Falta confirmarlo en el repositorio de los "
            "autores.")
DATASETS = [
    {"code": "plantvillage_papa", "name": "PlantVillage (subconjunto de papa)", "version": "2016",
     "source_url": "https://github.com/spMohanty/PlantVillage-Dataset", "license_status": "por_verificar",
     "license_notes": _PV_NOTE,
     "citation": "Hughes, D. P., & Salathé, M. (2015). An open access repository of images on plant health to enable "
                 "the development of mobile disease diagnostics. arXiv:1511.08060. Mohanty, S. P., Hughes, D. P., & "
                 "Salathé, M. (2016). Using deep learning for image-based plant disease detection. Frontiers in "
                 "Plant Science, 7, 1419.",
     "conditions": "laboratorio", "etiological_confirmation": "no", "has_group_ids": False, "role": "entrenamiento",
     "class_map": {"Potato___healthy": "sano", "Potato___Late_blight": "sintomas_compatibles_tizon_tardio",
                   "Potato___Early_blight": "otra_enfermedad_foliar"},
     "notes": "Hojas sueltas sobre fondo uniforme. Sin IDs de planta: los splits agrupan casi duplicados (dHash)."},
    {"code": "plantdoc_papa", "name": "PlantDoc (hojas de papa)", "version": "2019",
     "source_url": "https://github.com/pratikkayal/PlantDoc-Dataset", "license_status": "por_verificar",
     "license_notes": _PD_NOTE,
     "citation": "Singh, D., Jain, N., Jain, P., Kayal, P., Kumawat, S., & Batra, N. (2020). PlantDoc: A dataset for "
                 "visual plant disease detection. Proceedings of the 7th ACM IKDD CoDS and 25th COMAD, 249-253.",
     "conditions": "campo", "etiological_confirmation": "no", "has_group_ids": False, "role": "validacion_externa",
     "class_map": {"Potato leaf": "sano", "Potato leaf late blight": "sintomas_compatibles_tizon_tardio",
                   "Potato leaf early blight": "otra_enfermedad_foliar"},
     "notes": "Imágenes de internet en condiciones reales. Validación externa."},
    {"code": "app_validadas", "name": "Imágenes validadas por experto en la aplicación", "version": "continuo",
     "license": "Datos propios del proyecto (con consentimiento de los productores)", "license_status": "por_verificar",
     "license_notes": "Requiere el consentimiento informado de los productores (Ley N.° 29733) antes de usarse.",
     "conditions": "campo", "etiological_confirmation": "parcial", "has_group_ids": True,
     "role": "validacion_prospectiva",
     "class_map": {"sano": "sano", "tizon_tardio_sintomas": "sintomas_compatibles_tizon_tardio",
                   "tizon_tardio_confirmado": "sintomas_compatibles_tizon_tardio",
                   "otra_enfermedad": "otra_enfermedad_foliar"},
     "notes": "Etiqueta final del especialista; grupo = parcela (evita fuga entre entrenamiento y prueba)."},
    {"code": "sintetico_smoke", "name": "Imágenes sintéticas para la prueba de humo", "version": "1",
     "license": "Generadas por el propio código (sin terceros)", "license_status": "verificada",
     "license_notes": "Dibujos generados por programa (potato_blight.data.synthetic). Sin valor científico.",
     "conditions": "sintetico", "etiological_confirmation": "no", "has_group_ids": True, "role": "prueba_de_humo",
     "class_map": {c: c for c in ("sano", "sintomas_compatibles_tizon_tardio", "otra_enfermedad_foliar")},
     "notes": "Nunca usar para reportar métricas."},
]
