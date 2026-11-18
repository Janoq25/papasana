import uuid

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, require_permission
from app.api.v1.serializers import me_out
from app.core.config import get_settings
from app.core.errors import BusinessRuleError, PermissionDeniedError
from app.db.session import get_db
from app.schemas.common import Message, Page
from app.schemas.user import MeOut, ProfileUpdate, UserCreate, UserOut, UserUpdate
from app.services.auth_service import AuthService
from app.services.storage_service import StorageService, get_storage
from app.services.user_service import UserService

router = APIRouter(tags=["Usuarios y perfil"])


# --- Perfil propio -----------------------------------------------------------------------------

@router.patch("/users/me", response_model=MeOut, summary="Actualizar mi perfil")
def update_me(body: ProfileUpdate, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = UserService(db).update_profile(current.user, body.model_dump(exclude_unset=True), current.session.id)
    return me_out(db, user)


@router.post("/users/me/photo", response_model=Message, summary="Subir mi foto de perfil")
async def upload_my_photo(
    file: UploadFile = File(...),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
):
    max_bytes = get_settings().max_photo_bytes
    raw = await file.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise BusinessRuleError(f"La foto no debe superar {max_bytes // (1024 * 1024)} MB.")
    UserService(db).set_photo(current.user, raw, storage, current.session.id)
    return Message(message="Foto actualizada.")


@router.get("/users/{user_id}/photo", summary="Foto de perfil", response_class=Response)
def get_photo(
    user_id: uuid.UUID,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
):
    if user_id != current.user.id and not current.can("usuarios", "ver"):
        raise PermissionDeniedError("No tiene permiso para ver esta foto.")
    data = UserService(db).get_photo(user_id, storage)
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})


# --- Administración de usuarios ------------------------------------------------------------------

@router.get("/users", response_model=Page[UserOut], summary="Listar usuarios")
def list_users(
    q: str | None = Query(default=None, max_length=100),
    role_id: int | None = None,
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    _: CurrentUser = Depends(require_permission("usuarios", "ver")),
    db: Session = Depends(get_db),
):
    items, total = UserService(db).search(q=q, role_id=role_id, is_active=is_active, page=page, size=size)
    return Page[UserOut](items=[UserOut.model_validate(u) for u in items], total=total, page=page, size=size)


@router.post("/users", response_model=UserOut, status_code=201, summary="Crear usuario")
def create_user(body: UserCreate, current: CurrentUser = Depends(require_permission("usuarios", "crear")),
                db: Session = Depends(get_db)):
    return UserService(db).create(body.model_dump(), current.user, current.session.id)


@router.get("/users/{user_id}", response_model=UserOut, summary="Detalle de usuario")
def get_user(user_id: uuid.UUID, _: CurrentUser = Depends(require_permission("usuarios", "ver")),
             db: Session = Depends(get_db)):
    return UserService(db).get(user_id)


@router.patch("/users/{user_id}", response_model=UserOut, summary="Editar usuario (incluye rol y estado)")
def update_user(user_id: uuid.UUID, body: UserUpdate,
                current: CurrentUser = Depends(require_permission("usuarios", "editar")),
                db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if data.get("is_active") is False and not current.can("usuarios", "eliminar"):
        raise PermissionDeniedError("Desactivar usuarios requiere el permiso usuarios:eliminar.")
    return UserService(db).update(user_id, data, current.user, current.session.id)


@router.post("/users/{user_id}/unlock", response_model=UserOut, summary="Desbloquear cuenta")
def unlock_user(user_id: uuid.UUID, current: CurrentUser = Depends(require_permission("usuarios", "editar")),
                db: Session = Depends(get_db)):
    return UserService(db).unlock(user_id, current.user, current.session.id)


@router.post("/users/{user_id}/send-reset", response_model=Message,
             summary="Enviar enlace de restablecimiento al usuario")
def send_reset(user_id: uuid.UUID, _: CurrentUser = Depends(require_permission("usuarios", "editar")),
               db: Session = Depends(get_db)):
    user = UserService(db).get(user_id)
    AuthService(db).forgot_password(user.email)
    return Message(message="Se envió el enlace de restablecimiento.")
