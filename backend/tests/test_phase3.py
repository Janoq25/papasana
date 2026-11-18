"""Fase 3: dashboard, reportes (R-01 a R-10 y B-01 × PDF/Word/Excel), notificaciones internas."""

import io
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.security import now_utc
from app.models import AuditLog, Notification, Parcel, User, UserSession
from app.reports.definitions import REPORTS
from app.seed.demo_activity import N_DIAGNOSES, seed_demo_activity
from app.services.diagnosis_service import DiagnosisService
from app.services.report_service import ReportService
from tests.conftest import DEMO, login
from tests.test_phase2_unit import noise_jpeg

R = "/api/v1/reportes"


@pytest.fixture
def demo(db, storage):
    """Actividad de ejemplo (48 diagnósticos sintéticos) dentro de la transacción de la prueba."""
    assert seed_demo_activity(db, storage) == N_DIAGNOSES
    db.commit()
    return N_DIAGNOSES


@pytest.fixture
def rclient(ml_client, monkeypatch):
    """Cliente con la cola de reportes interceptada (el worker se simula llamando a ReportService.run)."""
    jobs: list[str] = []
    monkeypatch.setattr("app.api.v1.routers.reports.generate_report.delay", lambda job_id: jobs.append(job_id))
    ml_client.report_jobs = jobs
    return ml_client


def _parcel_id(db, code):
    return db.scalar(select(Parcel.id).where(Parcel.code == code))


def _user(db, role):
    return db.scalar(select(User).where(User.email == DEMO[role]))


def _generate(client, db, storage, headers, code, fmt="pdf", filters=None):
    r = client.post(R, headers=headers, json={"code": code, "format": fmt, "filters": filters or {}})
    assert r.status_code == 202, r.text
    job = ReportService(db, storage).run(uuid.UUID(r.json()["id"]))
    return job


# --- Dashboard ---------------------------------------------------------------------------------------

def test_dashboard_con_actividad_de_ejemplo(client, demo):
    adm = login(client, "ADMINISTRADOR")
    r = client.get("/api/v1/dashboard", headers=adm)
    assert r.status_code == 200, r.text
    d = r.json()
    k = d["kpis"]
    assert k["diagnosticos"] == demo and k["diagnosticos_ejemplo"] == demo
    assert sum(c["total"] for c in k["por_categoria"]) == demo
    assert abs(sum(c["porcentaje"] for c in k["por_categoria"]) - 1) < 1e-9
    assert k["parcelas"] >= 4
    # Indicadores de fases posteriores: no se inventan valores
    assert k["alertas_activas"]["valor"] is None and k["parcelas_en_riesgo"]["valor"] is None
    assert k["precision_modelo"]["valor"] is None and "DEMO" in k["precision_modelo"]["motivo"]
    assert k["acuerdo_experto"]["n"] == k["acuerdo_experto"]["confirma"] + k["acuerdo_experto"]["corrige"]
    # Tendencia completa y sin huecos
    series = d["tendencia"]["series"]
    assert sum(sum(p[c] for c in ("sano", "sospechoso", "tizon_tardio_compatible")) for p in series) == demo
    assert d["tendencia"]["granularidad"] in ("dia", "semana")
    assert {r["codigo"] for r in d["por_region"]} == {"120000", "080000"}
    assert sum(v["total"] for v in d["por_variedad"]) == demo
    assert len(d["mapa"]) == demo and not d["mapa_truncado"]
    assert d["modelo"]["is_demo"] is True


def test_dashboard_respeta_el_alcance_del_rol(client, db, demo):
    agr = client.get("/api/v1/dashboard", headers=login(client, "AGRONOMO")).json()
    assert {r["codigo"] for r in agr["por_region"]} == {"120000"}  # el agrónomo de Junín no ve Cusco
    tec = client.get("/api/v1/dashboard", headers=login(client, "TECNICO")).json()
    adm = client.get("/api/v1/dashboard", headers=login(client, "ADMINISTRADOR"),
                     params={"parcel_id": _parcel_id(db, "DEMO-JUN-001")}).json()
    adm2 = client.get("/api/v1/dashboard", headers=login(client, "ADMINISTRADOR"),
                      params={"parcel_id": _parcel_id(db, "DEMO-JUN-002")}).json()
    assert tec["kpis"]["diagnosticos"] == adm["kpis"]["diagnosticos"] + adm2["kpis"]["diagnosticos"]
    assert tec["kpis"]["parcelas"] == 2
    assert client.get("/api/v1/dashboard", headers=login(client, "AUDITOR")).status_code == 403


def test_dashboard_filtros(client, db, demo):
    adm = login(client, "ADMINISTRADOR")
    old = client.get("/api/v1/dashboard", headers=adm, params={"date_from": "2020-01-01", "date_to": "2020-01-31"})
    assert old.json()["kpis"]["diagnosticos"] == 0 and len(old.json()["tendencia"]["series"]) == 31
    cus = client.get("/api/v1/dashboard", headers=adm, params={"region_code": "080000"}).json()
    assert {r["codigo"] for r in cus["por_region"]} == {"080000"}
    assert client.get("/api/v1/dashboard", headers=adm,
                      params={"date_from": "2026-02-01", "date_to": "2026-01-01"}).status_code == 422
    tec = login(client, "TECNICO")
    r = client.get("/api/v1/dashboard", headers=tec, params={"parcel_id": _parcel_id(db, "DEMO-CUS-001")})
    assert r.status_code == 404


# --- Catálogo y generación de reportes -------------------------------------------------------------------

def test_catalogo_de_reportes_segun_el_rol(client):
    tec = {r["code"] for r in client.get(f"{R}/catalogo", headers=login(client, "TECNICO")).json()}
    assert tec == {"R-01", "R-02", "R-03", "R-04", "R-06", "R-07", "R-08", "R-09"}
    aud = client.get(f"{R}/catalogo", headers=login(client, "AUDITOR")).json()
    assert {r["code"] for r in aud} == set(REPORTS)
    r01 = next(r for r in aud if r["code"] == "R-01")
    assert [f["key"] for f in r01["filters"]][:2] == ["date_from", "date_to"]
    assert r01["formats"] == ["pdf", "docx", "xlsx"]
    opts = client.get(f"{R}/opciones", headers=login(client, "TECNICO")).json()
    assert {p["code"] for p in opts["parcels"]} == {"DEMO-JUN-001", "DEMO-JUN-002"}
    assert [t["email"] for t in opts["technicians"]] == [DEMO["TECNICO"]] and opts["roles"] == []


CASES = [(code, fmt) for code in REPORTS for fmt in ("pdf", "docx", "xlsx")]


@pytest.mark.parametrize("code,fmt", CASES, ids=[f"{c}-{f}" for c, f in CASES])
def test_cada_reporte_se_genera_y_abre_en_cada_formato(rclient, db, storage, demo, code, fmt):
    adm = login(rclient, "ADMINISTRADOR")
    job = _generate(rclient, db, storage, adm, code, fmt)
    assert job.status == "listo", job.error
    assert job.file_name.startswith(code) and job.file_name.endswith(f".{fmt}")
    r = rclient.get(f"{R}/{job.id}/descarga", headers=adm)
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    data = r.content
    if fmt == "pdf":
        assert data.startswith(b"%PDF") and len(data) > 1500
    elif fmt == "docx":
        import docx

        text = "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)
        assert code in text and REPORTS[code].title in text
    else:
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(data))
        resumen = [c.value for row in wb["Resumen"].iter_rows(max_col=2) for c in row if c.value]
        assert any(code in str(v) for v in resumen)
        assert len(wb.sheetnames) >= 2  # "Resumen" + una hoja por tabla
        if REPORTS[code].uses_model:
            assert any("DEMO / NO VALIDADO" in str(v) for v in resumen)


def test_reporte_r01_con_datos_y_alcance_del_tecnico(rclient, db, storage, demo):
    import openpyxl

    tec = login(rclient, "TECNICO")
    job = _generate(rclient, db, storage, tec, "R-01", "xlsx", {"category": "tizon_tardio_compatible"})
    assert job.status == "listo"
    wb = openpyxl.load_workbook(io.BytesIO(rclient.get(f"{R}/{job.id}/descarga", headers=tec).content))
    sheet = wb["Detalle de diagnósticos"]
    parcels = {row[1] for row in sheet.iter_rows(min_row=2, values_only=True) if row[0] is not None}
    categories = {row[3] for row in sheet.iter_rows(min_row=2, values_only=True) if row[0] is not None}
    assert parcels and parcels <= {"DEMO-JUN-001", "DEMO-JUN-002"}
    assert categories == {"Tizón tardío: síntomas compatibles"}
    assert job.row_count >= len(parcels)


def test_filtros_de_reporte_validados(rclient):
    adm = login(rclient, "ADMINISTRADOR")
    r = rclient.post(R, headers=adm, json={"code": "R-03", "format": "pdf", "filters": {"date_from": "2026-01-01"}})
    assert r.status_code == 422 and r.json()["code"] == "filtros_invalidos"  # R-03 no admite fechas
    r = rclient.post(R, headers=adm, json={"code": "R-01", "format": "pdf",
                                           "filters": {"date_from": "2026-03-01", "date_to": "2026-01-01"}})
    assert r.status_code == 422 and r.json()["code"] == "filtros_invalidos"
    r = rclient.post(R, headers=adm, json={"code": "R-01", "format": "pdf", "filters": {"inventado": 1}})
    assert r.status_code == 422
    assert rclient.post(R, headers=adm, json={"code": "R-01", "format": "odt"}).status_code == 422
    assert rclient.post(R, headers=adm, json={"code": "R-99", "format": "pdf"}).status_code == 404
    assert rclient.report_jobs == []


def test_permisos_y_bitacora_de_reportes(rclient, db, storage):
    tec = login(rclient, "TECNICO")
    r = rclient.post(R, headers=tec, json={"code": "R-05", "format": "pdf"})
    assert r.status_code == 403  # la actividad de usuarios requiere además bitacora:ver
    denied = db.scalar(select(AuditLog).where(AuditLog.event_type == "acceso_denegado",
                                              AuditLog.entity_id == "R-05"))
    assert denied is not None
    aud = login(rclient, "AUDITOR")
    job = _generate(rclient, db, storage, aud, "B-01", "xlsx", {"event_type": "login"})
    assert job.status == "listo"
    # Otro usuario no ve ni descarga el reporte ajeno
    assert rclient.get(f"{R}/{job.id}", headers=tec).status_code == 404
    assert rclient.get(f"{R}/{job.id}/descarga", headers=tec).status_code == 404
    assert rclient.get(f"{R}/{job.id}/descarga", headers=aud).status_code == 200
    events = db.scalars(select(AuditLog).where(AuditLog.entity_type == "reporte",
                                               AuditLog.entity_id == str(job.id))).all()
    assert {e.action for e in events} == {"exportar", "descargar"}
    assert all(e.module_code == "bitacora" for e in events)
    hist = rclient.get(R, headers=aud).json()
    assert hist["total"] == 1 and hist["items"][0]["download_count"] == 1
    assert hist["items"][0]["report_title"] == "Bitácora de auditoría"


def test_limite_de_reportes_en_proceso(rclient):
    adm = login(rclient, "ADMINISTRADOR")
    for _ in range(5):
        assert rclient.post(R, headers=adm, json={"code": "R-04", "format": "pdf"}).status_code == 202
    r = rclient.post(R, headers=adm, json={"code": "R-04", "format": "pdf"})
    assert r.status_code == 422 and r.json()["code"] == "demasiados_reportes"


def test_reporte_no_listo_y_permiso_revocado(rclient, db, storage):
    adm = login(rclient, "ADMINISTRADOR")
    jid = rclient.post(R, headers=adm, json={"code": "R-04", "format": "pdf"}).json()["id"]
    r = rclient.get(f"{R}/{jid}/descarga", headers=adm)
    assert r.status_code == 422 and r.json()["code"] == "reporte_no_listo"
    # Si el solicitante pierde el permiso antes de que el worker lo procese, el job termina en error
    admin = _user(db, "ADMINISTRADOR")
    admin.is_active = False
    db.commit()
    job = ReportService(db, storage).run(uuid.UUID(jid))
    assert job.status == "error" and "activo" in job.error


# --- Notificaciones (A4) ---------------------------------------------------------------------------------

def test_notificacion_de_reporte_listo(rclient, db, storage):
    adm = login(rclient, "ADMINISTRADOR")
    _generate(rclient, db, storage, adm, "R-04", "docx")
    s = rclient.get("/api/v1/notificaciones/resumen", headers=adm).json()
    assert s["unread"] == 1 and s["recent"][0]["kind"] == "reporte_listo" and s["recent"][0]["link"] == "/reportes"
    nid = s["recent"][0]["id"]
    # Otro usuario no puede marcarla
    assert rclient.post(f"/api/v1/notificaciones/{nid}/leida", headers=login(rclient, "TECNICO")).status_code == 404
    assert rclient.post(f"/api/v1/notificaciones/{nid}/leida", headers=adm).status_code == 204
    assert rclient.get("/api/v1/notificaciones/resumen", headers=adm).json()["unread"] == 0
    page = rclient.get("/api/v1/notificaciones", headers=adm, params={"unread_only": True}).json()
    assert page["total"] == 0 and page["unread"] == 0


def test_notificacion_de_caso_pendiente_al_especialista(ml_client, db, fake_ml):
    fake_ml.confidence = 0.55  # bajo el umbral: pendiente de revisión
    tec = login(ml_client, "TECNICO")
    r = ml_client.post("/api/v1/diagnosticos", headers=tec, data={"parcel_id": str(_parcel_id(db, "DEMO-JUN-001"))},
                       files={"file": ("hoja.jpg", noise_jpeg(), "image/jpeg")})
    assert r.status_code == 201 and r.json()["status"] == "pendiente_revision"
    notes = db.scalars(select(Notification).where(Notification.kind == "revision_pendiente")).all()
    # Solo el agrónomo (validacion:aprobar y región Junín); ni el técnico ni los roles sin "aprobar"
    assert [n.user_id for n in notes] == [_user(db, "AGRONOMO").id]
    assert notes[0].link == "/validacion" and "DEMO-JUN-001" in notes[0].body
    agr = login(ml_client, "AGRONOMO")
    assert ml_client.post("/api/v1/notificaciones/leer-todas", headers=agr).json() == {"marcadas": 1}


def test_un_lote_genera_una_sola_notificacion(ml_client, db, storage, fake_ml):
    fake_ml.confidence = 0.5
    tec = login(ml_client, "TECNICO")
    files = [("files", (f"h{i}.jpg", noise_jpeg(), "image/jpeg")) for i in range(3)]
    body = ml_client.post("/api/v1/diagnosticos/lote", headers=tec, files=files,
                          data={"parcel_id": str(_parcel_id(db, "DEMO-JUN-002"))}).json()
    svc = DiagnosisService(db, storage, fake_ml)
    for image_id in ml_client.queued:
        svc.process_batch_image(uuid.UUID(image_id))
    notes = db.scalars(select(Notification).where(Notification.kind == "revision_pendiente")).all()
    assert len(notes) == 1 and notes[0].title == "3 casos nuevos pendientes de validación"
    assert notes[0].entity_type == "lote" and notes[0].entity_id == body["id"]


def test_consultas_en_segundo_plano_no_cuentan_como_actividad(client, db):
    adm = login(client, "ADMINISTRADOR")
    session = db.scalar(select(UserSession).where(UserSession.user_id == _user(db, "ADMINISTRADOR").id)
                        .order_by(UserSession.created_at.desc()))
    old = now_utc() - timedelta(minutes=10)
    session.last_seen_at = old
    db.commit()
    assert client.get("/api/v1/notificaciones/resumen", headers={**adm, "X-Background": "1"}).status_code == 200
    db.refresh(session)
    assert session.last_seen_at == old
    client.get("/api/v1/notificaciones/resumen", headers=adm)
    db.refresh(session)
    assert session.last_seen_at > old


def test_no_se_pueden_borrar_reportes_ni_notificaciones(db):
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    # El historial de reportes y las notificaciones no se borran (el usuario de la aplicación no tiene DELETE)
    for table in ("reportes.report_jobs", "notificaciones.notifications"):
        with pytest.raises(ProgrammingError):
            with db.begin_nested():
                db.execute(text(f"DELETE FROM {table}"))
