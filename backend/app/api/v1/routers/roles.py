from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, require_permission
from app.api.v1.serializers import role_out
from app.db.session import get_db
from app.repositories.security_repo import UserRepository
from app.schemas.role import RoleCreate, RoleOut, RolePermissionsIn, RoleUpdate
from app.services.role_service import RoleService

# Roles y permisos forman parte del módulo "usuarios" (seguridad).
router = APIRouter(prefix="/roles", tags=["Roles y permisos"])


@router.get("", response_model=list[RoleOut], summary="Listar roles con sus permisos")
def list_roles(_: CurrentUser = Depends(require_permission("usuarios", "ver")), db: Session = Depends(get_db)):
    return [role_out(r, n) for r, n in RoleService(db).list_with_counts()]


@router.get("/catalogo-permisos", summary="Módulos y acciones disponibles para la matriz")
def permission_catalog(_: CurrentUser = Depends(require_permission("usuarios", "ver")),
                       db: Session = Depends(get_db)):
    return RoleService(db).catalog()


@router.post("", response_model=RoleOut, status_code=201, summary="Crear rol")
def create_role(body: RoleCreate, current: CurrentUser = Depends(require_permission("usuarios", "crear")),
                db: Session = Depends(get_db)):
    role = RoleService(db).create(body.model_dump(), current.user, current.session.id)
    return role_out(role, 0)


@router.patch("/{role_id}", response_model=RoleOut, summary="Editar rol")
def update_role(role_id: int, body: RoleUpdate,
                current: CurrentUser = Depends(require_permission("usuarios", "editar")),
                db: Session = Depends(get_db)):
    role = RoleService(db).update(role_id, body.model_dump(exclude_unset=True), current.user, current.session.id)
    return role_out(role, UserRepository(db).count_with_role(role.id))


@router.put("/{role_id}/permisos", response_model=RoleOut, summary="Reemplazar los permisos del rol")
def set_permissions(role_id: int, body: RolePermissionsIn,
                    current: CurrentUser = Depends(require_permission("usuarios", "editar")),
                    db: Session = Depends(get_db)):
    role = RoleService(db).set_permissions(role_id, body.permissions, current.user, current.session.id)
    return role_out(role, UserRepository(db).count_with_role(role.id))


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar rol (no del sistema)")
def delete_role(role_id: int, current: CurrentUser = Depends(require_permission("usuarios", "eliminar")),
                db: Session = Depends(get_db)):
    RoleService(db).delete(role_id, current.user, current.session.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
