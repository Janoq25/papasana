import io

from PIL import Image
from sqlalchemy import select

from app.models import AuditLog, Role
from tests.conftest import DEMO, login


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (40, 120, 40)).save(buf, format="PNG")
    return buf.getvalue()


def _role_id(db, code):
    return db.scalar(select(Role.id).where(Role.code == code))


def _find_user(client, headers, q):
    return client.get("/api/v1/users", headers=headers, params={"q": q}).json()["items"][0]


# --- Usuarios ----------------------------------------------------------------------------------

def test_crear_usuario_y_conflicto(client, db, admin_headers):
    body = {"email": "Nuevo.Tecnico@demo.papasana.pe", "full_name": "Nuevo Técnico",
            "password": "ClaveSegura-2026", "role_id": _role_id(db, "TECNICO"), "region_code": "080000"}
    r = client.post("/api/v1/users", headers=admin_headers, json=body)
    assert r.status_code == 201, r.text
    assert r.json()["email"] == "nuevo.tecnico@demo.papasana.pe"
    assert client.post("/api/v1/users", headers=admin_headers, json=body).status_code == 409
    ev = db.scalar(select(AuditLog).where(AuditLog.entity_type == "usuario", AuditLog.action == "crear"))
    assert ev.after["email"] == "nuevo.tecnico@demo.papasana.pe" and "password_hash" not in ev.after


def test_crear_usuario_valida_contrasena_y_region(client, db, admin_headers):
    base = {"email": "x@demo.papasana.pe", "full_name": "Usuario X", "role_id": _role_id(db, "TECNICO")}
    weak = client.post("/api/v1/users", headers=admin_headers, json=base | {"password": "corta"})
    assert weak.status_code == 422
    bad_region = client.post("/api/v1/users", headers=admin_headers,
                             json=base | {"password": "ClaveSegura-2026", "region_code": "999999"})
    assert bad_region.status_code == 422


def test_listar_y_filtrar_usuarios(client, admin_headers):
    r = client.get("/api/v1/users", headers=admin_headers, params={"q": "agrono"})
    assert r.status_code == 200
    assert [u["email"] for u in r.json()["items"]] == [DEMO["AGRONOMO"]]


def test_editar_rol_de_usuario_queda_en_bitacora(client, db, admin_headers):
    target = _find_user(client, admin_headers, "tecnico")
    new_role = _role_id(db, "AGRONOMO")
    r = client.patch(f"/api/v1/users/{target['id']}", headers=admin_headers, json={"role_id": new_role})
    assert r.status_code == 200 and r.json()["role"]["code"] == "AGRONOMO"
    ev = db.scalar(select(AuditLog).where(AuditLog.entity_id == target["id"], AuditLog.action == "editar"))
    assert ev.before["role_id"] != ev.after["role_id"] == new_role


def test_admin_no_puede_desactivarse_ni_cambiar_su_rol(client, db, admin_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    r1 = client.patch(f"/api/v1/users/{me['id']}", headers=admin_headers, json={"is_active": False})
    r2 = client.patch(f"/api/v1/users/{me['id']}", headers=admin_headers,
                      json={"role_id": _role_id(db, "AUDITOR")})
    assert r1.status_code == r2.status_code == 422


def test_desactivar_usuario_revoca_sus_sesiones(client, admin_headers):
    tecnico = login(client, "TECNICO")
    target = _find_user(client, admin_headers, "tecnico")
    r = client.patch(f"/api/v1/users/{target['id']}", headers=admin_headers, json={"is_active": False})
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me", headers=tecnico).status_code == 401


def test_enviar_enlace_de_restablecimiento(client, admin_headers, emails):
    target = _find_user(client, admin_headers, "auditor")
    assert client.post(f"/api/v1/users/{target['id']}/send-reset", headers=admin_headers).status_code == 200
    assert emails and emails[0][0] == DEMO["AUDITOR"]


# --- Perfil ------------------------------------------------------------------------------------

def test_perfil_propio_y_foto(client):
    headers = login(client, "TECNICO")
    r = client.patch("/api/v1/users/me", headers=headers,
                     json={"phone": "+51 999 888 777", "preferences": {"tema": "claro"}})
    assert r.status_code == 200 and r.json()["phone"] == "+51 999 888 777"
    up = client.post("/api/v1/users/me/photo", headers=headers, files={"file": ("f.png", _png(), "image/png")})
    assert up.status_code == 200
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["has_photo"] is True
    photo = client.get(f"/api/v1/users/{me['id']}/photo", headers=headers)
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/jpeg"
    assert max(Image.open(io.BytesIO(photo.content)).size) <= 512  # re-codificada y reducida (sin EXIF)


def test_foto_invalida(client):
    headers = login(client, "TECNICO")
    r = client.post("/api/v1/users/me/photo", headers=headers,
                    files={"file": ("x.png", b"no soy una imagen", "image/png")})
    assert r.status_code == 422


def test_no_se_ve_la_foto_de_otro_sin_permiso(client):
    other = _find_user(client, login(client, "ADMINISTRADOR"), "auditor")
    tecnico = login(client, "TECNICO")
    assert client.get(f"/api/v1/users/{other['id']}/photo", headers=tecnico).status_code == 403


def test_regiones(client):
    headers = login(client, "TECNICO")
    r = client.get("/api/v1/catalogos/ubigeo", headers=headers)
    assert r.status_code == 200 and len(r.json()) == 25


# --- Roles y permisos --------------------------------------------------------------------------

def test_cambiar_permisos_registra_agregados_y_quitados(client, db, admin_headers):
    role_id = _role_id(db, "TECNICO")
    current = next(r for r in client.get("/api/v1/roles", headers=admin_headers).json() if r["id"] == role_id)
    wanted = sorted((set(current["permissions"]) - {"reportes:exportar"}) | {"dashboard:exportar"})
    r = client.put(f"/api/v1/roles/{role_id}/permisos", headers=admin_headers, json={"permissions": wanted})
    assert r.status_code == 200 and r.json()["permissions"] == wanted
    ev = db.scalar(select(AuditLog).where(AuditLog.action == "cambiar_permisos"))
    assert ev.after["agregados"] == ["dashboard:exportar"]
    assert ev.after["quitados"] == ["reportes:exportar"]


def test_permisos_desconocidos_y_proteccion_del_admin(client, db, admin_headers):
    r1 = client.put(f"/api/v1/roles/{_role_id(db, 'TECNICO')}/permisos", headers=admin_headers,
                    json={"permissions": ["inventado:ver"]})
    r2 = client.put(f"/api/v1/roles/{_role_id(db, 'ADMINISTRADOR')}/permisos", headers=admin_headers,
                    json={"permissions": ["dashboard:ver"]})
    assert r1.status_code == r2.status_code == 422


def test_crear_editar_y_eliminar_rol(client, admin_headers):
    r = client.post("/api/v1/roles", headers=admin_headers,
                    json={"code": "observador", "name": "Observador", "data_scope": "region"})
    assert r.status_code == 201 and r.json()["code"] == "OBSERVADOR"
    rid = r.json()["id"]
    assert client.patch(f"/api/v1/roles/{rid}", headers=admin_headers,
                        json={"name": "Observador regional"}).json()["name"] == "Observador regional"
    assert client.post("/api/v1/roles", headers=admin_headers,
                       json={"code": "OBSERVADOR", "name": "Duplicado"}).status_code == 409
    assert client.delete(f"/api/v1/roles/{rid}", headers=admin_headers).status_code == 204


def test_no_se_elimina_rol_del_sistema(client, db, admin_headers):
    assert client.delete(f"/api/v1/roles/{_role_id(db, 'AUDITOR')}", headers=admin_headers).status_code == 422


def test_catalogo_de_permisos(client, admin_headers):
    body = client.get("/api/v1/roles/catalogo-permisos", headers=admin_headers).json()
    assert body["acciones"] == ["ver", "crear", "editar", "eliminar", "exportar", "aprobar"]
    codes = [m["code"] for m in body["modulos"]]
    assert "bitacora" in codes and "perfil" not in codes


# --- Configuración -----------------------------------------------------------------------------

def test_actualizar_parametro_y_validaciones(client, db, admin_headers):
    r = client.put("/api/v1/settings/seguridad.minutos_inactividad", headers=admin_headers, json={"value": 45})
    assert r.status_code == 200 and r.json()["value"] == 45
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    assert me["session_settings"]["minutos_inactividad"] == 45
    ev = db.scalar(select(AuditLog).where(AuditLog.entity_id == "seguridad.minutos_inactividad"))
    assert ev.before == {"valor": 30} and ev.after == {"valor": 45}
    assert client.put("/api/v1/settings/seguridad.minutos_inactividad", headers=admin_headers,
                      json={"value": 2}).status_code == 422
    assert client.put("/api/v1/settings/diagnostico.umbral_revision", headers=admin_headers,
                      json={"value": "alto"}).status_code == 422
    assert client.put("/api/v1/settings/no.existe", headers=admin_headers, json={"value": 1}).status_code == 404


def test_listar_parametros(client, admin_headers):
    keys = [s["key"] for s in client.get("/api/v1/settings", headers=admin_headers).json()]
    assert "diagnostico.umbral_revision" in keys and "aviso.supervision_profesional" in keys


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"
