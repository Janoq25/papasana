"""Roles configurables y matriz de permisos (módulo × acción)."""

from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.models import Role, User
from app.models.security import ACTIONS, DATA_SCOPES
from app.repositories.security_repo import RoleRepository, UserRepository
from app.services.audit_service import AuditService

ADMIN_ROLE = "ADMINISTRADOR"
# Permisos que el rol Administrador no puede perder (evita quedarse sin acceso a la gestión).
ADMIN_REQUIRED = {"usuarios:ver", "usuarios:editar"}
ROLE_FIELDS = ["id", "code", "name", "description", "data_scope"]


class RoleService:
    def __init__(self, db: Session):
        self.db = db
        self.roles = RoleRepository(db)
        self.audit = AuditService(db)

    def get(self, role_id: int) -> Role:
        role = self.roles.get(role_id)
        if role is None:
            raise NotFoundError("Rol no encontrado.")
        return role

    def list_with_counts(self) -> list[tuple[Role, int]]:
        users = UserRepository(self.db)
        return [(r, users.count_with_role(r.id)) for r in self.roles.list_all()]

    def catalog(self) -> dict:
        modules = [m for m in self.roles.modules() if m.requires_permission]
        perms = {(p.module.code, p.action) for p in self.roles.all_permissions()}
        return {
            "acciones": list(ACTIONS),
            "modulos": [
                {"code": m.code, "name": m.name, "phase": m.phase,
                 "acciones": [a for a in ACTIONS if (m.code, a) in perms]}
                for m in modules
            ],
        }

    def _snap(self, role: Role) -> dict:
        return {c: getattr(role, c) for c in ROLE_FIELDS}

    def create(self, data: dict[str, Any], actor: User, session_id) -> Role:
        code = data["code"].strip().upper()
        if self.roles.by_code(code):
            raise ConflictError("Ya existe un rol con ese código.")
        if data.get("data_scope", "propio") not in DATA_SCOPES:
            raise BusinessRuleError("Alcance de datos inválido.")
        role = Role(code=code, name=data["name"].strip(), description=data.get("description"),
                    data_scope=data.get("data_scope", "propio"), is_system=False)
        self.db.add(role)
        self.db.flush()
        self.audit.log("accion", user=actor, session_id=session_id, module_code="usuarios", action="crear",
                       entity_type="rol", entity_id=role.id, after=self._snap(role))
        self.db.commit()
        return role

    def update(self, role_id: int, data: dict[str, Any], actor: User, session_id) -> Role:
        role = self.get(role_id)
        before = self._snap(role)
        if "data_scope" in data and data["data_scope"] not in DATA_SCOPES:
            raise BusinessRuleError("Alcance de datos inválido.")
        for field in ("name", "description", "data_scope"):
            if field in data and data[field] is not None:
                setattr(role, field, data[field])
        self.db.flush()
        self.audit.log("accion", user=actor, session_id=session_id, module_code="usuarios", action="editar",
                       entity_type="rol", entity_id=role.id, before=before, after=self._snap(role))
        self.db.commit()
        return role

    def delete(self, role_id: int, actor: User, session_id) -> None:
        role = self.get(role_id)
        if role.is_system:
            raise BusinessRuleError("Los roles del sistema no se pueden eliminar.")
        if UserRepository(self.db).count_with_role(role.id) > 0:
            raise BusinessRuleError("El rol tiene usuarios asignados; reasígnelos antes de eliminarlo.")
        before = self._snap(role) | {"permisos": sorted(role.permission_keys)}
        self.db.delete(role)
        self.audit.log("accion", user=actor, session_id=session_id, module_code="usuarios",
                       action="eliminar", entity_type="rol", entity_id=role_id, before=before)
        self.db.commit()

    def set_permissions(self, role_id: int, keys: list[str], actor: User, session_id) -> Role:
        role = self.get(role_id)
        wanted = set(keys)
        available = self.roles.permissions_by_keys(wanted)
        unknown = wanted - {p.key for p in available}
        if unknown:
            raise BusinessRuleError("Permisos desconocidos.", detail=sorted(unknown))
        if role.code == ADMIN_ROLE and not ADMIN_REQUIRED <= wanted:
            raise BusinessRuleError(
                "El rol Administrador debe conservar los permisos de ver y editar usuarios.",
                detail=sorted(ADMIN_REQUIRED - wanted))
        before = sorted(role.permission_keys)
        role.permissions = available
        self.db.flush()
        after = sorted(role.permission_keys)
        self.audit.log(
            "accion", user=actor, session_id=session_id, module_code="usuarios", action="cambiar_permisos",
            entity_type="rol", entity_id=role.id,
            before={"permisos": before},
            after={"permisos": after,
                   "agregados": sorted(set(after) - set(before)),
                   "quitados": sorted(set(before) - set(after))},
        )
        self.db.commit()
        return role
