"""La matriz RBAC se aplica en el backend: cada endpoint × cada rol semilla."""

import pytest
from sqlalchemy import select

from app.models import AuditLog, Role
from app.seed.data import LETTER_TO_ACTION, ROLES
from tests.conftest import login

MATRIX = {code: {f"{m}:{LETTER_TO_ACTION[c]}" for m, letters in matrix.items() for c in letters}
          for code, _, _, _, matrix in ROLES}

ENDPOINTS = [
    ("GET", "/api/v1/users", "usuarios:ver", None),
    ("GET", "/api/v1/roles", "usuarios:ver", None),
    ("GET", "/api/v1/roles/catalogo-permisos", "usuarios:ver", None),
    ("POST", "/api/v1/roles", "usuarios:crear", {"code": "ROL_PRUEBA", "name": "Rol de prueba"}),
    ("POST", "/api/v1/users", "usuarios:crear",
     {"email": "nuevo@demo.papasana.pe", "full_name": "Usuario Nuevo", "password": "ClaveSegura-2026",
      "role_id": 1}),
    ("GET", "/api/v1/audit", "bitacora:ver", None),
    ("GET", "/api/v1/audit/module-time", "bitacora:ver", None),
    ("GET", "/api/v1/audit/verify", "bitacora:ver", None),
    ("GET", "/api/v1/settings", "configuracion:ver", None),
    ("PUT", "/api/v1/settings/seguridad.minutos_bloqueo", "configuracion:editar", {"value": 20}),
    # Fase 3
    ("GET", "/api/v1/dashboard", "dashboard:ver", None),
    ("GET", "/api/v1/dashboard/opciones", "dashboard:ver", None),
    ("GET", "/api/v1/reportes/catalogo", "reportes:ver", None),
    ("GET", "/api/v1/reportes/opciones", "reportes:ver", None),
    ("GET", "/api/v1/reportes", "reportes:ver", None),
    # Fase 4
    ("GET", "/api/v1/laboratorio/modelos", "laboratorio:ver", None),
    ("GET", "/api/v1/laboratorio/promociones", "laboratorio:ver", None),
    ("GET", "/api/v1/datasets", "datasets:ver", None),
    ("GET", "/api/v1/datasets/exportar", "datasets:exportar", None),
]

CASES = [(role, *ep) for role in MATRIX for ep in ENDPOINTS]


@pytest.mark.parametrize("role,method,path,permission,body", CASES,
                         ids=[f"{c[0]}-{c[1]}-{c[2]}" for c in CASES])
def test_matriz_de_permisos(client, role, method, path, permission, body):
    headers = login(client, role)
    r = client.request(method, path, headers=headers, json=body)
    if permission in MATRIX[role]:
        assert r.status_code < 400, f"{role} debería poder {permission}: {r.status_code} {r.text}"
    else:
        assert r.status_code == 403, f"{role} NO debería poder {permission}: {r.status_code}"
        assert r.json()["code"] == "sin_permiso"


def test_auditor_solo_lectura_de_bitacora_y_reportes(db):
    auditor = db.scalar(select(Role).where(Role.code == "AUDITOR"))
    assert auditor.permission_keys == {"bitacora:ver", "bitacora:exportar", "reportes:ver", "reportes:exportar"}


def test_acceso_denegado_queda_en_la_bitacora(client, db):
    headers = login(client, "TECNICO")
    assert client.get("/api/v1/users", headers=headers).status_code == 403
    ev = db.scalar(select(AuditLog).where(AuditLog.event_type == "acceso_denegado"))
    assert ev is not None and ev.result == "fallo" and ev.module_code == "usuarios"


def test_desactivar_usuario_requiere_permiso_eliminar(client):
    # Un rol con usuarios:editar pero sin usuarios:eliminar no puede desactivar cuentas.
    admin = login(client, "ADMINISTRADOR")
    role = client.post("/api/v1/roles", headers=admin, json={"code": "EDITOR_USUARIOS", "name": "Editor"}).json()
    client.put(f"/api/v1/roles/{role['id']}/permisos", headers=admin,
               json={"permissions": ["usuarios:ver", "usuarios:editar"]})
    tecnico = client.get("/api/v1/users", headers=admin, params={"q": "tecnico"}).json()["items"][0]
    client.patch(f"/api/v1/users/{tecnico['id']}", headers=admin, json={"role_id": role["id"]})
    editor = login(client, "TECNICO")
    target = client.get("/api/v1/users", headers=editor, params={"q": "auditor"}).json()["items"][0]
    r = client.patch(f"/api/v1/users/{target['id']}", headers=editor, json={"is_active": False})
    assert r.status_code == 403
