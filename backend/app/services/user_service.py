"""Gestión de usuarios y perfil propio."""

import io
import uuid
from typing import Any

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.security import hash_password, now_utc, password_policy_errors
from app.models import Ubigeo, User
from app.repositories.security_repo import RoleRepository, SessionRepository, UserRepository
from app.services.audit_service import AuditService, snapshot
from app.services.settings_service import SettingsService
from app.services.storage_service import StorageService

ADMIN_ROLE = "ADMINISTRADOR"
USER_FIELDS = ["id", "email", "full_name", "institution", "phone", "region_code", "role_id", "is_active",
               "locked_until"]
PROFILE_FIELDS = ["full_name", "institution", "phone", "region_code", "preferences"]
ALLOWED_PHOTO_FORMATS = {"JPEG", "PNG", "WEBP"}


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.roles = RoleRepository(db)
        self.audit = AuditService(db)

    def get(self, user_id: uuid.UUID) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado.")
        return user

    def search(self, **filters) -> tuple[list[User], int]:
        return self.users.search(**filters)

    # --- Validaciones -------------------------------------------------------------------------

    def _check_region(self, code: str | None) -> None:
        if code and self.db.get(Ubigeo, code) is None:
            raise BusinessRuleError("La región seleccionada no existe.")

    def _check_password(self, password: str) -> None:
        min_len = int(SettingsService(self.db).get("seguridad.longitud_minima_contrasena"))
        errors = password_policy_errors(password, min_len)
        if errors:
            raise BusinessRuleError("La contraseña no cumple la política.", detail=errors, code="contrasena_debil")

    def _is_last_active_admin(self, user: User) -> bool:
        return (user.role.code == ADMIN_ROLE and user.is_active
                and self.users.count_active_with_role(user.role_id) <= 1)

    # --- CRUD ---------------------------------------------------------------------------------

    def create(self, data: dict[str, Any], actor: User, session_id) -> User:
        email = data["email"].strip().lower()
        if self.users.by_email(email):
            raise ConflictError("Ya existe un usuario con ese correo.")
        role = self.roles.get(data["role_id"])
        if role is None:
            raise BusinessRuleError("El rol indicado no existe.")
        self._check_region(data.get("region_code"))
        self._check_password(data["password"])
        user = self.users.add(User(
            email=email,
            password_hash=hash_password(data["password"]),
            full_name=data["full_name"].strip(),
            institution=data.get("institution"),
            phone=data.get("phone"),
            region_code=data.get("region_code"),
            role_id=role.id,
            password_changed_at=now_utc(),
        ))
        self.db.refresh(user)
        self.audit.log("accion", user=actor, session_id=session_id, module_code="usuarios", action="crear",
                       entity_type="usuario", entity_id=user.id, after=snapshot(user, USER_FIELDS))
        self.db.commit()
        return user

    def update(self, user_id: uuid.UUID, data: dict[str, Any], actor: User, session_id) -> User:
        user = self.get(user_id)
        before = snapshot(user, USER_FIELDS)
        if "role_id" in data and data["role_id"] != user.role_id:
            if user.id == actor.id:
                raise BusinessRuleError("No puede cambiar su propio rol.")
            if self.roles.get(data["role_id"]) is None:
                raise BusinessRuleError("El rol indicado no existe.")
            if self._is_last_active_admin(user):
                raise BusinessRuleError("Debe existir al menos un Administrador activo.")
        if data.get("is_active") is False and user.is_active:
            if user.id == actor.id:
                raise BusinessRuleError("No puede desactivar su propia cuenta.")
            if self._is_last_active_admin(user):
                raise BusinessRuleError("Debe existir al menos un Administrador activo.")
        if "region_code" in data:
            self._check_region(data["region_code"])
        for field in ("full_name", "institution", "phone", "region_code", "role_id", "is_active"):
            if field in data:
                setattr(user, field, data[field])
        self.db.flush()
        if data.get("is_active") is False:
            SessionRepository(self.db).revoke_all_for_user(user.id, "desactivado", now_utc())
        if "role_id" in data:
            self.db.expire(user, ["role"])
        after = snapshot(user, USER_FIELDS)
        self.audit.log("accion", user=actor, session_id=session_id, module_code="usuarios", action="editar",
                       entity_type="usuario", entity_id=user.id, before=before, after=after)
        self.db.commit()
        return user

    def unlock(self, user_id: uuid.UUID, actor: User, session_id) -> User:
        user = self.get(user_id)
        before = snapshot(user, ["locked_until", "failed_attempts"])
        user.locked_until = None
        user.failed_attempts = 0
        self.audit.log("accion", user=actor, session_id=session_id, module_code="usuarios",
                       action="desbloquear", entity_type="usuario", entity_id=user.id, before=before,
                       after={"locked_until": None, "failed_attempts": 0})
        self.db.commit()
        return user

    # --- Perfil propio ------------------------------------------------------------------------

    def update_profile(self, user: User, data: dict[str, Any], session_id) -> User:
        before = snapshot(user, PROFILE_FIELDS)
        if "region_code" in data:
            self._check_region(data["region_code"])
        for field in PROFILE_FIELDS:
            if field in data:
                setattr(user, field, data[field])
        self.db.flush()
        self.audit.log("accion", user=user, session_id=session_id, module_code="perfil", action="editar",
                       entity_type="usuario", entity_id=user.id, before=before,
                       after=snapshot(user, PROFILE_FIELDS))
        self.db.commit()
        return user

    def set_photo(self, user: User, raw: bytes, storage: StorageService, session_id) -> None:
        s = get_settings()
        if len(raw) > s.max_photo_bytes:
            raise BusinessRuleError(f"La foto no debe superar {s.max_photo_bytes // (1024 * 1024)} MB.")
        try:
            img = Image.open(io.BytesIO(raw))
            fmt = img.format
            img.verify()
            img = Image.open(io.BytesIO(raw))
        except (UnidentifiedImageError, OSError) as e:
            raise BusinessRuleError("El archivo no es una imagen válida.") from e
        if fmt not in ALLOWED_PHOTO_FORMATS:
            raise BusinessRuleError("Formato no permitido. Use JPEG, PNG o WebP.")
        # Re-codificar elimina metadatos EXIF (incluida la ubicación) y normaliza el tamaño.
        img = img.convert("RGB")
        img.thumbnail((512, 512))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=88)
        key = f"usuarios/{user.id}.jpg"
        storage.put_bytes(s.bucket_profiles, key, out.getvalue(), "image/jpeg")
        user.photo_key = key
        self.audit.log("accion", user=user, session_id=session_id, module_code="perfil",
                       action="actualizar_foto", entity_type="usuario", entity_id=user.id)
        self.db.commit()

    def get_photo(self, user_id: uuid.UUID, storage: StorageService) -> bytes:
        user = self.get(user_id)
        if not user.photo_key:
            raise NotFoundError("El usuario no tiene foto.")
        return storage.get_bytes(get_settings().bucket_profiles, user.photo_key)
