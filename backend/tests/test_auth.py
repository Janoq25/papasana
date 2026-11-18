import re
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import now_utc
from app.main import app
from app.models import AuditLog, User, UserSession
from tests.conftest import DEMO, TEST_PASSWORD, login

LOGIN = "/api/v1/auth/login"


def _events(db, event_type, email=None):
    stmt = select(AuditLog).where(AuditLog.event_type == event_type)
    if email:
        stmt = stmt.where(AuditLog.user_email == email)
    return db.scalars(stmt).all()


def test_login_ok_devuelve_token_cookie_y_permisos(client, db):
    r = client.post(LOGIN, json={"email": DEMO["AGRONOMO"], "password": TEST_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] > 0
    assert "validacion:aprobar" in body["user"]["permissions"]
    assert "usuarios:ver" not in body["user"]["permissions"]
    assert body["user"]["session_settings"]["minutos_inactividad"] == 30
    cookie = r.headers["set-cookie"].lower()
    assert "ps_refresh=" in cookie and "httponly" in cookie and "samesite=strict" in cookie
    assert _events(db, "login", DEMO["AGRONOMO"])


def test_login_fallido_mensaje_generico(client, db):
    a = client.post(LOGIN, json={"email": "nadie@demo.papasana.pe", "password": "x"})
    b = client.post(LOGIN, json={"email": DEMO["TECNICO"], "password": "incorrecta"})
    assert a.status_code == b.status_code == 401
    assert a.json()["message"] == b.json()["message"]
    assert len(_events(db, "login_fallido")) == 2


def test_bloqueo_tras_intentos_fallidos(client, db):
    for _ in range(5):
        assert client.post(LOGIN, json={"email": DEMO["TECNICO"], "password": "mal"}).status_code == 401
    r = client.post(LOGIN, json={"email": DEMO["TECNICO"], "password": TEST_PASSWORD})
    assert r.status_code == 423
    assert r.json()["code"] == "cuenta_bloqueada"
    assert _events(db, "bloqueo_cuenta", DEMO["TECNICO"])


def test_desbloqueo_por_administrador(client, db, admin_headers):
    for _ in range(5):
        client.post(LOGIN, json={"email": DEMO["TECNICO"], "password": "mal"})
    user = db.scalar(select(User).where(User.email == DEMO["TECNICO"]))
    r = client.post(f"/api/v1/users/{user.id}/unlock", headers=admin_headers)
    assert r.status_code == 200 and r.json()["is_locked"] is False
    assert client.post(LOGIN, json={"email": DEMO["TECNICO"], "password": TEST_PASSWORD}).status_code == 200


def test_refresh_rota_el_token_y_detecta_reuso(client, db):
    client.post(LOGIN, json={"email": DEMO["INVESTIGADOR"], "password": TEST_PASSWORD})
    old = client.cookies.get("ps_refresh")
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    new = client.cookies.get("ps_refresh")
    assert new and new != old
    # Reutilizar el token anterior revoca la sesión
    client.cookies.clear()
    client.cookies.set("ps_refresh", old)
    assert client.post("/api/v1/auth/refresh").status_code == 401
    assert db.scalar(select(UserSession).where(UserSession.revoke_reason == "reuso_token")) is not None


def test_logout_revoca_la_sesion(client, db):
    headers = login(client, "INVESTIGADOR")
    assert client.post("/api/v1/auth/logout", json={"reason": "logout"}).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    ev = _events(db, "logout", DEMO["INVESTIGADOR"])
    assert ev and ev[0].duration_ms is not None


def test_logout_por_inactividad_se_registra_como_sesion_expirada(client, db):
    login(client, "AUDITOR")
    client.post("/api/v1/auth/logout", json={"reason": "inactividad"})
    assert _events(db, "sesion_expirada", DEMO["AUDITOR"])


def test_expiracion_por_inactividad_en_el_servidor(client, db):
    headers = login(client, "AUDITOR")
    session = db.scalar(select(UserSession).join(User).where(User.email == DEMO["AUDITOR"]))
    session.last_seen_at = now_utc() - timedelta(hours=2)
    db.commit()
    r = client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 401 and r.json()["code"] == "sesion_expirada"
    assert _events(db, "sesion_expirada", DEMO["AUDITOR"])


def test_token_invalido(client):
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer basura"}).status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401


def test_recuperacion_de_contrasena(client, emails):
    old_headers = login(client, "TECNICO")
    r = client.post("/api/v1/auth/forgot-password", json={"email": DEMO["TECNICO"]})
    assert r.status_code == 202 and len(emails) == 1
    token = re.search(r"token=([\w\-]+)", emails[0][2]).group(1)
    weak = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "corta"})
    assert weak.status_code == 422 and weak.json()["code"] == "contrasena_debil"
    ok = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "NuevaClave-2026"})
    assert ok.status_code == 200
    # Enlace de un solo uso; las sesiones anteriores quedan revocadas
    again = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "OtraClave-2026"})
    assert again.status_code == 422
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401
    login(client, "TECNICO", "NuevaClave-2026")


def test_recuperacion_para_correo_inexistente_no_revela_nada(client, emails):
    r = client.post("/api/v1/auth/forgot-password", json={"email": "desconocido@demo.papasana.pe"})
    assert r.status_code == 202 and emails == []


def test_cambio_de_contrasena_revoca_las_otras_sesiones(client):
    headers = login(client, "AGRONOMO")
    other = login(TestClient(app), "AGRONOMO")
    bad = client.post("/api/v1/auth/change-password", headers=headers,
                      json={"current_password": "x", "new_password": "NuevaClave-2026"})
    assert bad.status_code == 422
    ok = client.post("/api/v1/auth/change-password", headers=headers,
                     json={"current_password": TEST_PASSWORD, "new_password": "NuevaClave-2026"})
    assert ok.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=other).status_code == 401
