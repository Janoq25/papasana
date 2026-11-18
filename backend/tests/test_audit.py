import json
import time

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.db.audit_sql import VERIFY_QUERY
from app.models import AuditLog
from tests.conftest import login

EVENTS = "/api/v1/audit/module-events"


def test_entrada_y_salida_de_modulo_con_duracion(client, db):
    headers = login(client, "INVESTIGADOR")
    entry = client.post(EVENTS, headers=headers, json={"module_code": "dashboard", "event": "entrada"})
    assert entry.status_code == 200
    time.sleep(0.05)
    exit_ = client.post(EVENTS, headers=headers, json={
        "module_code": "dashboard", "event": "salida", "entry_event_id": entry.json()["event_id"],
        "reason": "navegacion"})
    assert exit_.status_code == 200
    assert exit_.json()["duration_ms"] >= 40
    # Idempotente: una segunda salida (beacon + fetch) no duplica el registro
    again = client.post(EVENTS, headers=headers, json={
        "module_code": "dashboard", "event": "salida", "entry_event_id": entry.json()["event_id"]})
    assert again.json()["event_id"] == exit_.json()["event_id"]
    ev = db.get(AuditLog, exit_.json()["event_id"])
    assert ev.related_event_id == entry.json()["event_id"] and ev.after["motivo"] == "navegacion"


def test_modulo_desconocido(client):
    headers = login(client, "INVESTIGADOR")
    r = client.post(EVENTS, headers=headers, json={"module_code": "inexistente", "event": "entrada"})
    assert r.status_code == 422


def test_no_se_puede_cerrar_la_entrada_de_otro_usuario(client):
    a = login(client, "INVESTIGADOR")
    entry = client.post(EVENTS, headers=a, json={"module_code": "dashboard", "event": "entrada"}).json()
    b = login(client, "AGRONOMO")
    r = client.post(EVENTS, headers=b, json={"module_code": "dashboard", "event": "salida",
                                              "entry_event_id": entry["event_id"]})
    assert r.status_code == 403


def test_beacon_registra_salida_con_cookie_de_sesion(client, db):
    headers = login(client, "TECNICO")
    entry = client.post(EVENTS, headers=headers, json={"module_code": "perfil", "event": "entrada"}).json()
    payload = {"module_code": "perfil", "event": "salida", "entry_event_id": entry["event_id"],
               "reason": "pestana_oculta"}
    r = client.post("/api/v1/audit/beacon", content=json.dumps(payload), headers={"Content-Type": "text/plain"})
    assert r.status_code == 204
    ev = db.scalar(select(AuditLog).where(AuditLog.related_event_id == entry["event_id"]))
    assert ev is not None and ev.after["motivo"] == "pestana_oculta"


def test_beacon_sin_cookie_no_registra(client):
    r = client.post("/api/v1/audit/beacon", content="{}", headers={"Content-Type": "text/plain"})
    assert r.status_code == 204


def test_consulta_filtros_y_tiempo_por_modulo(client):
    headers = login(client, "AUDITOR")
    r = client.get("/api/v1/audit", headers=headers, params={"event_type": "login", "size": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1 and all(i["event_type"] == "login" for i in body["items"])
    assert len(body["items"][0]["hash"]) == 64
    assert client.get("/api/v1/audit/module-time", headers=headers).status_code == 200


def test_cadena_integra_y_hash_encadenado(client, db):
    headers = login(client, "AUDITOR")
    r = client.get("/api/v1/audit/verify", headers=headers)
    assert r.status_code == 200 and r.json()["ok"] is True
    rows = db.scalars(select(AuditLog).order_by(AuditLog.seq)).all()
    for prev, cur in zip(rows, rows[1:], strict=False):
        assert cur.prev_hash == prev.hash


def test_usuario_de_aplicacion_no_puede_modificar_ni_borrar(client, db):
    login(client, "AUDITOR")
    for sql in ("UPDATE auditoria.audit_log SET result = 'fallo'",
                "DELETE FROM auditoria.audit_log",
                "TRUNCATE auditoria.audit_log"):
        with pytest.raises(DBAPIError, match="permission denied"):
            with db.begin_nested():
                db.execute(text(sql))


def _insert_rows(conn, n=3):
    for i in range(n):
        conn.execute(text("INSERT INTO auditoria.audit_log(event_type, result, after) "
                          "VALUES ('accion', 'exito', CAST(:a AS jsonb))"), {"a": json.dumps({"i": i})})
    return conn.execute(text("SELECT seq FROM auditoria.audit_log ORDER BY seq")).scalars().all()


def test_trigger_impide_modificar_incluso_al_propietario(owner_engine):
    with owner_engine.connect() as conn:
        trans = conn.begin()
        try:
            _insert_rows(conn, 1)
            for sql in ("UPDATE auditoria.audit_log SET result = 'fallo'",
                        "DELETE FROM auditoria.audit_log",
                        "TRUNCATE auditoria.audit_log"):
                with pytest.raises(DBAPIError, match="inmutable"):
                    with conn.begin_nested():
                        conn.execute(text(sql))
        finally:
            trans.rollback()


@pytest.mark.parametrize("tamper,expected", [
    ("UPDATE auditoria.audit_log SET after = CAST('{\"i\": 99}' AS jsonb) WHERE seq = :s", "contenido_alterado"),
    ("DELETE FROM auditoria.audit_log WHERE seq = :s", "cadena_rota"),
])
def test_verificacion_detecta_manipulacion(owner_engine, tamper, expected):
    with owner_engine.connect() as conn:
        trans = conn.begin()
        try:
            seqs = _insert_rows(conn, 3)
            assert conn.execute(text(VERIFY_QUERY)).first() is None
            target = seqs[1]
            # Simula a un atacante con privilegios de propietario que desactiva el trigger.
            conn.execute(text("ALTER TABLE auditoria.audit_log DISABLE TRIGGER trg_audit_no_update_delete"))
            conn.execute(text(tamper), {"s": target})
            broken = conn.execute(text(VERIFY_QUERY)).mappings().first()
            assert broken is not None
            assert broken["motivo"] == expected
            assert broken["seq"] in (target, seqs[2])
        finally:
            trans.rollback()
