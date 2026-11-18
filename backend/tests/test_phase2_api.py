import io

import pytest
from sqlalchemy import select

from app.models import AuditLog, Diagnosis, Image, Parcel, UploadBatch
from app.services.diagnosis_service import DiagnosisService
from tests.conftest import login
from tests.test_phase2_unit import gps_exif, noise_jpeg

D = "/api/v1/diagnosticos"


def _parcel_id(db, code):
    return db.scalar(select(Parcel.id).where(Parcel.code == code))


def _square(lon=-75.25, lat=-12.05, d=0.001):
    return {"type": "Polygon", "coordinates": [[[lon, lat], [lon + d, lat], [lon + d, lat + d], [lon, lat + d],
                                                [lon, lat]]]}


def _upload(client, headers, parcel_id, raw=None, name="hoja.jpg", **form):
    data = {"parcel_id": str(parcel_id), **{k: str(v) for k, v in form.items()}}
    return client.post(D, headers=headers, data=data,
                       files={"file": (name, raw if raw is not None else noise_jpeg(), "image/jpeg")})


# --- Catálogos ----------------------------------------------------------------------------------

def test_catalogos_lectura_y_permisos(client):
    tec = login(client, "TECNICO")
    r = client.get("/api/v1/catalogos/variedades", headers=tec)
    assert r.status_code == 200 and "Yungay" in [v["name"] for v in r.json()]
    enf = client.get("/api/v1/catalogos/enfermedades", headers=tec).json()
    assert any(e["is_target"] and "Phytophthora" in e["causal_agent"] for e in enf)
    assert client.post("/api/v1/catalogos/variedades", headers=tec, json={"name": "Nueva"}).status_code == 403
    agr = login(client, "AGRONOMO")
    r = client.post("/api/v1/catalogos/variedades", headers=agr, json={"name": "Variedad X", "group": "nativa"})
    assert r.status_code == 201
    vid = r.json()["id"]
    assert client.patch(f"/api/v1/catalogos/variedades/{vid}", headers=agr,
                        json={"group": "mejorada"}).json()["group"] == "mejorada"
    assert client.delete(f"/api/v1/catalogos/variedades/{vid}", headers=agr).status_code == 403  # sin eliminar
    adm = login(client, "ADMINISTRADOR")
    assert client.delete(f"/api/v1/catalogos/variedades/{vid}", headers=adm).status_code == 204
    assert client.post("/api/v1/catalogos/variedades", headers=adm,
                       json={"name": "Variedad X", "group": "invalido"}).status_code == 422
    assert client.get("/api/v1/catalogos/inexistente", headers=adm).status_code == 422


def test_importar_ubigeo_csv(client):
    adm = login(client, "ADMINISTRADOR")
    csv = "ubigeo;nombre\n120100;Huancayo\n120101;Huancayo\n120114;Sicaya\n999901;Sin padre\n"
    r = client.post("/api/v1/catalogos/ubigeo/importar", headers=adm,
                    files={"file": ("ubigeo.csv", csv.encode(), "text/csv")})
    assert r.status_code == 200 and r.json() == {"filas_leidas": 4, "creados": 3}
    dist = client.get("/api/v1/catalogos/ubigeo", headers=adm, params={"level": "distrito", "parent": "120100"})
    assert [d["name"] for d in dist.json()] == ["Huancayo", "Sicaya"]


# --- Parcelas -----------------------------------------------------------------------------------

def test_alcance_de_parcelas_por_rol(client):
    def codes(role):
        h = login(client, role)
        return {p["code"] for p in client.get("/api/v1/parcelas", headers=h, params={"size": 200}).json()["items"]}

    assert {"DEMO-JUN-001", "DEMO-JUN-002", "DEMO-JUN-003", "DEMO-CUS-001"} <= codes("ADMINISTRADOR")
    agr = codes("AGRONOMO")  # región Junín
    assert "DEMO-JUN-003" in agr and "DEMO-CUS-001" not in agr
    assert codes("TECNICO") == {"DEMO-JUN-001", "DEMO-JUN-002"}  # solo las asignadas
    assert client.get("/api/v1/parcelas", headers=login(client, "AUDITOR")).status_code == 403


def test_crear_parcela_valida_y_auditoria(client, db):
    tec = login(client, "TECNICO")
    r = client.post("/api/v1/parcelas", headers=tec, json={"name": "Mi parcela", "region_code": "120000",
                                                           "geometry": _square()})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["code"].startswith("PAR-") and 1.0 < body["area_ha"] < 1.4  # ~0.001° × 0.001° ≈ 1.2 ha
    assert body["geometry"]["type"] == "Polygon" and len(body["centroid"]) == 2
    # El técnico queda asignado a la parcela que crea y la ve en su listado
    codes = {p["code"] for p in client.get("/api/v1/parcelas", headers=tec).json()["items"]}
    assert body["code"] in codes
    ev = db.scalar(select(AuditLog).where(AuditLog.entity_type == "parcela", AuditLog.action == "crear"))
    assert ev.after["geometria"]["type"] == "Polygon"


@pytest.mark.parametrize("geometry,fragment", [
    ({"type": "Polygon", "coordinates": [[[-75.25, -12.05], [-75.24, -12.04], [-75.25, -12.04],
                                          [-75.24, -12.05], [-75.25, -12.05]]]}, "no es válido"),
    (_square(lon=2.35, lat=48.85), "dentro del Perú"),
    ({"type": "Polygon", "coordinates": [[[-75.25, -12.05], [-75.24, -12.05], [-75.25, -12.05]]]}, "3 vértices"),
])
def test_poligonos_invalidos(client, geometry, fragment):
    adm = login(client, "ADMINISTRADOR")
    r = client.post("/api/v1/parcelas", headers=adm, json={"name": "X parcela", "region_code": "120000",
                                                           "geometry": geometry})
    assert r.status_code == 422 and fragment in r.json()["message"]


def test_agronomo_no_registra_fuera_de_su_region(client):
    agr = login(client, "AGRONOMO")
    r = client.post("/api/v1/parcelas", headers=agr, json={"name": "Fuera", "region_code": "080000",
                                                           "geometry": _square(lon=-72.0, lat=-13.5)})
    assert r.status_code == 403


def test_editar_geometria_asignar_y_desactivar(client, db):
    pid = _parcel_id(db, "DEMO-JUN-003")
    agr = login(client, "AGRONOMO")
    r = client.patch(f"/api/v1/parcelas/{pid}", headers=agr,
                     json={"geometry": _square(lon=-75.3128, lat=-11.9189, d=0.002)})
    assert r.status_code == 200 and r.json()["area_ha"] > 4
    users = client.get("/api/v1/parcelas/asignables", headers=agr).json()
    tecnico = next(u for u in users if u["role_name"].startswith("Técnico"))
    r = client.put(f"/api/v1/parcelas/{pid}/asignaciones", headers=agr, json={"user_ids": [tecnico["id"]]})
    assert r.status_code == 200
    tec = login(client, "TECNICO")
    assert client.get(f"/api/v1/parcelas/{pid}", headers=tec).status_code == 200
    # Desactivar requiere parcelas:eliminar (el agrónomo no lo tiene)
    assert client.patch(f"/api/v1/parcelas/{pid}", headers=agr, json={"is_active": False}).status_code == 403
    adm = login(client, "ADMINISTRADOR")
    assert client.patch(f"/api/v1/parcelas/{pid}", headers=adm, json={"is_active": False}).json()["is_active"] is False


def test_geojson_para_el_mapa(client):
    fc = client.get("/api/v1/parcelas/geojson", headers=login(client, "TECNICO")).json()
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) == 2
    assert fc["features"][0]["geometry"]["type"] == "Polygon"


def test_productores(client):
    agr = login(client, "AGRONOMO")
    r = client.post("/api/v1/productores", headers=agr, json={"name": "Productor nuevo", "region_code": "120000"})
    assert r.status_code == 201
    assert "Productor nuevo" in [p["name"] for p in client.get("/api/v1/productores", headers=agr).json()]


# --- Diagnóstico --------------------------------------------------------------------------------

def test_diagnostico_completo_con_gradcam_y_bitacora(ml_client, db, fake_ml, storage):
    tec = login(ml_client, "TECNICO")
    pid = _parcel_id(db, "DEMO-JUN-001")
    raw = noise_jpeg(exif=gps_exif(-12.01535, -75.2899))  # dentro de la parcela
    r = _upload(ml_client, tec, pid, raw)
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["category"] == "tizon_tardio_compatible" and d["status"] == "pendiente_revision"
    assert d["requires_review"] is False and d["confidence"] == pytest.approx(0.91)
    assert d["model"]["is_demo"] is True and "DEMO" in d["model"]["display_name"]
    assert d["image"]["gps_source"] == "exif" and d["image"]["inside_parcel"] is True
    assert d["image"]["location"]["lat"] == pytest.approx(-12.01535, abs=1e-5)
    assert d["has_gradcam"] and "profesional" in d["disclaimer"]
    img = ml_client.get(f"{D}/{d['id']}/imagen", headers=tec)
    assert img.status_code == 200 and img.content == raw
    cam = ml_client.get(f"{D}/{d['id']}/gradcam", headers=tec)
    assert cam.status_code == 200 and cam.headers["content-type"] == "image/png"
    ev = db.scalar(select(AuditLog).where(AuditLog.action == "diagnosticar"))
    assert ev.after["modelo_demo"] is True and ev.after["categoria"] == "tizon_tardio_compatible"


def test_confianza_baja_requiere_revision(ml_client, db, fake_ml):
    fake_ml.predicted, fake_ml.confidence = "sano", 0.55
    r = _upload(ml_client, login(ml_client, "TECNICO"), _parcel_id(db, "DEMO-JUN-001"))
    assert r.json()["category"] == "sospechoso" and r.json()["requires_review"] is True


def test_sano_con_confianza_alta_no_va_a_la_bandeja(ml_client, db, fake_ml):
    fake_ml.predicted, fake_ml.confidence = "sano", 0.97
    r = _upload(ml_client, login(ml_client, "TECNICO"), _parcel_id(db, "DEMO-JUN-001"))
    assert r.json()["status"] == "automatico"


def test_gps_del_dispositivo_fuera_de_la_parcela(ml_client, db):
    r = _upload(ml_client, login(ml_client, "TECNICO"), _parcel_id(db, "DEMO-JUN-001"), lat=-12.2, lon=-75.1)
    img = r.json()["image"]
    assert img["gps_source"] == "dispositivo" and img["inside_parcel"] is False


def test_duplicado_exacto_y_casi_duplicado(ml_client, db):
    tec = login(ml_client, "TECNICO")
    pid = _parcel_id(db, "DEMO-JUN-001")
    from PIL import Image as PILImage

    base = PILImage.effect_noise((400, 300), 60).convert("RGB")
    buf1, buf2 = io.BytesIO(), io.BytesIO()
    base.save(buf1, format="JPEG", quality=92)
    base.point(lambda v: min(255, int(v * 1.04))).save(buf2, format="JPEG", quality=92)
    first = _upload(ml_client, tec, pid, buf1.getvalue())
    assert first.status_code == 201
    again = _upload(ml_client, tec, pid, buf1.getvalue())
    assert again.status_code == 409 and again.json()["detail"]["diagnostico_id"] == first.json()["id"]
    near = _upload(ml_client, tec, pid, buf2.getvalue())
    assert near.status_code == 201
    assert near.json()["image"]["duplicate_of_id"] == first.json()["image"]["id"]


def test_fuera_de_alcance_archivo_invalido_y_servicio_caido(ml_client, db, fake_ml, storage):
    tec = login(ml_client, "TECNICO")
    assert _upload(ml_client, tec, _parcel_id(db, "DEMO-JUN-003")).status_code == 404  # no asignada
    bad = _upload(ml_client, tec, _parcel_id(db, "DEMO-JUN-001"), b"no es imagen")
    assert bad.status_code == 422 and bad.json()["code"] == "imagen_invalida"
    fake_ml.fail = True
    before = len(storage.objects)
    down = _upload(ml_client, tec, _parcel_id(db, "DEMO-JUN-001"))
    assert down.status_code == 503
    assert len(storage.objects) == before  # la foto no queda huérfana en MinIO
    assert db.scalar(select(Image).where(Image.uploaded_by.isnot(None)).limit(1)) is None


def test_alcance_del_historial(ml_client, db):
    tec = login(ml_client, "TECNICO")
    did = _upload(ml_client, tec, _parcel_id(db, "DEMO-JUN-001")).json()["id"]
    assert ml_client.get(D, headers=tec).json()["total"] == 1
    agr = login(ml_client, "AGRONOMO")  # misma región
    assert ml_client.get(f"{D}/{did}", headers=agr).status_code == 200
    assert ml_client.get(D, headers=login(ml_client, "AUDITOR")).status_code == 403


def test_anular_diagnostico(ml_client, db):
    did = _upload(ml_client, login(ml_client, "TECNICO"), _parcel_id(db, "DEMO-JUN-001")).json()["id"]
    tec = login(ml_client, "TECNICO")
    assert ml_client.post(f"{D}/{did}/anular", headers=tec, json={"reason": "foto equivocada"}).status_code == 403
    adm = login(ml_client, "ADMINISTRADOR")
    r = ml_client.post(f"{D}/{did}/anular", headers=adm, json={"reason": "foto equivocada"})
    assert r.status_code == 200 and r.json()["status"] == "anulado"
    assert ml_client.post(f"{D}/{did}/anular", headers=adm, json={"reason": "otra vez"}).status_code == 422


# --- Lotes --------------------------------------------------------------------------------------

def test_lote_con_procesamiento_en_segundo_plano(ml_client, db, storage, fake_ml):
    tec = login(ml_client, "TECNICO")
    pid = _parcel_id(db, "DEMO-JUN-002")
    files = [("files", (f"h{i}.jpg", noise_jpeg(), "image/jpeg")) for i in range(2)]
    files.append(("files", ("mala.jpg", b"basura", "image/jpeg")))
    r = ml_client.post(f"{D}/lote", headers=tec, data={"parcel_id": str(pid)}, files=files)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["total"] == 2 and [x["aceptada"] for x in body["results"]] == [True, True, False]
    assert len(ml_client.queued) == 2
    # Simula al worker de Celery
    svc = DiagnosisService(db, storage, fake_ml)
    for image_id in ml_client.queued:
        svc.process_batch_image(__import__("uuid").UUID(image_id))
        svc.process_batch_image(__import__("uuid").UUID(image_id))  # idempotente
    status = ml_client.get(f"{D}/lotes/{body['id']}", headers=tec).json()
    assert status["status"] == "completado" and status["processed"] == 2 and len(status["diagnoses"]) == 2
    assert db.scalar(select(UploadBatch.processed).where(UploadBatch.id == __import__("uuid").UUID(body["id"]))) == 2


def test_lote_excede_el_maximo(ml_client, db):
    tec = login(ml_client, "TECNICO")
    adm = login(ml_client, "ADMINISTRADOR")
    ml_client.put("/api/v1/settings/diagnostico.max_imagenes_lote", headers=adm, json={"value": 1})
    files = [("files", (f"h{i}.jpg", noise_jpeg(), "image/jpeg")) for i in range(2)]
    r = ml_client.post(f"{D}/lote", headers=tec, data={"parcel_id": str(_parcel_id(db, "DEMO-JUN-002"))}, files=files)
    assert r.status_code == 422


# --- Validación por experto ---------------------------------------------------------------------

def test_flujo_de_validacion_experta(ml_client, db, fake_ml):
    tec = login(ml_client, "TECNICO")
    did = _upload(ml_client, tec, _parcel_id(db, "DEMO-JUN-001")).json()["id"]
    agr = login(ml_client, "AGRONOMO")
    pend = ml_client.get("/api/v1/validacion/pendientes", headers=agr).json()
    assert did in [p["id"] for p in pend["items"]]
    # El técnico no puede validar
    assert ml_client.post(f"{D}/{did}/revision", headers=tec, json={"final_label": "sano"}).status_code == 403
    # Confirmar el tizón tardío exige evidencia
    r = ml_client.post(f"{D}/{did}/revision", headers=agr, json={"final_label": "tizon_tardio_confirmado"})
    assert r.status_code == 422 and r.json()["code"] == "evidencia_requerida"
    r = ml_client.post(f"{D}/{did}/revision", headers=agr,
                       json={"final_label": "tizon_tardio_confirmado", "evidence": "esporulacion",
                             "notes": "Esporulación blanca en el envés"})
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "validado" and out["reviews"][0]["decision"] == "confirma"
    assert out["reviews"][0]["final_label_name"] == "Tizón tardío confirmado"
    # Ya no está pendiente
    assert ml_client.post(f"{D}/{did}/revision", headers=agr, json={"final_label": "sano"}).status_code == 422
    # El intento del técnico quedó como "acceso_denegado"; la validación es el evento "accion"
    denied = db.scalar(select(AuditLog).where(AuditLog.module_code == "validacion",
                                              AuditLog.event_type == "acceso_denegado"))
    assert denied is not None and denied.result == "fallo"
    ev = db.scalar(select(AuditLog).where(AuditLog.module_code == "validacion", AuditLog.action == "aprobar",
                                          AuditLog.event_type == "accion"))
    assert ev.before["estado"] == "pendiente_revision" and ev.after["evidencia"] == "esporulacion"


def test_correccion_a_otra_enfermedad(ml_client, db, fake_ml):
    fake_ml.predicted, fake_ml.confidence = "otra_enfermedad_foliar", 0.8
    did = _upload(ml_client, login(ml_client, "TECNICO"), _parcel_id(db, "DEMO-JUN-001")).json()["id"]
    agr = login(ml_client, "AGRONOMO")
    assert ml_client.post(f"{D}/{did}/revision", headers=agr,
                          json={"final_label": "otra_enfermedad"}).status_code == 422  # falta el diferencial
    alternaria = next(e for e in ml_client.get("/api/v1/catalogos/enfermedades", headers=agr).json()
                      if e["name"] == "Tizón temprano")
    r = ml_client.post(f"{D}/{did}/revision", headers=agr,
                       json={"final_label": "otra_enfermedad", "differential_disease_id": alternaria["id"]})
    assert r.json()["status"] == "corregido" and r.json()["reviews"][0]["differential"] == "Tizón temprano"
    assert db.get(Diagnosis, __import__("uuid").UUID(did)).status == "corregido"


def test_bitacora_inmutable_y_no_se_borran_diagnosticos(ml_client, db):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    _upload(ml_client, login(ml_client, "TECNICO"), _parcel_id(db, "DEMO-JUN-001"))
    with pytest.raises(DBAPIError, match="permission denied"):
        with db.begin_nested():
            db.execute(text("DELETE FROM campo.diagnoses"))


def test_etiquetas_y_modelo_activo(ml_client):
    tec = login(ml_client, "TECNICO")
    labels = ml_client.get(f"{D}/etiquetas", headers=tec).json()
    assert labels["categorias"]["tizon_tardio_compatible"] == "Tizón tardío: síntomas compatibles"
    m = ml_client.get("/api/v1/modelos/activo", headers=tec).json()
    assert m["is_demo"] is True and m["model_key"] == "demo-resnet50-imagenet-v1"
