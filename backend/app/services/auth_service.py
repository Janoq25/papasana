"""Autenticación: login con bloqueo, sesiones con refresh rotativo, logout, recuperación de contraseña."""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import get_request_context
from app.core.errors import AccountLockedError, AuthError, BusinessRuleError
from app.core.security import (
    create_access_token,
    hash_password,
    new_opaque_token,
    now_utc,
    password_needs_rehash,
    password_policy_errors,
    sha256_hex,
    verify_password,
)
from app.models import PasswordResetToken, User, UserSession
from app.repositories.security_repo import PasswordResetRepository, SessionRepository, UserRepository
from app.services.audit_service import AuditService
from app.services.email_service import enqueue_email, password_reset_email
from app.services.settings_service import SettingsService

GENERIC_LOGIN_ERROR = "Correo o contraseña incorrectos."


@dataclass
class IssuedTokens:
    access_token: str
    expires_in: int
    refresh_token: str
    user: User
    session: UserSession


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.sessions = SessionRepository(db)
        self.resets = PasswordResetRepository(db)
        self.audit = AuditService(db)
        self.settings = SettingsService(db)

    # --- Login ------------------------------------------------------------------------------

    def login(self, email: str, password: str) -> IssuedTokens:
        now = now_utc()
        user = self.users.by_email(email)
        if user is None:
            verify_password(password, None)  # iguala el tiempo de respuesta
            self.audit.log("login_fallido", user_email=email.strip().lower()[:254], module_code="auth",
                           action="login", result="fallo", error_detail="usuario_inexistente")
            self.db.commit()
            raise AuthError(GENERIC_LOGIN_ERROR, code="credenciales_invalidas")

        if user.locked_until and user.locked_until > now:
            minutes = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
            self.audit.log("login_fallido", user=user, module_code="auth", action="login", result="fallo",
                           error_detail="cuenta_bloqueada")
            self.db.commit()
            raise AccountLockedError(
                f"Cuenta bloqueada temporalmente por intentos fallidos. Intente nuevamente en {minutes} min.")

        if not verify_password(password, user.password_hash) or not user.is_active:
            reason = "cuenta_inactiva" if user.is_active is False else "contrasena_incorrecta"
            if user.is_active:
                user.failed_attempts += 1
                max_attempts = int(self.settings.get("seguridad.max_intentos_login"))
                if user.failed_attempts >= max_attempts:
                    lock_minutes = int(self.settings.get("seguridad.minutos_bloqueo"))
                    user.locked_until = now + timedelta(minutes=lock_minutes)
                    user.failed_attempts = 0
                    self.audit.log("bloqueo_cuenta", user=user, module_code="auth", action="bloquear",
                                   entity_type="usuario", entity_id=user.id, result="exito",
                                   after={"bloqueada_hasta": user.locked_until.isoformat(),
                                          "intentos": max_attempts})
            self.audit.log("login_fallido", user=user, module_code="auth", action="login", result="fallo",
                           error_detail=reason)
            self.db.commit()
            raise AuthError(GENERIC_LOGIN_ERROR, code="credenciales_invalidas")

        user.failed_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        tokens = self._open_session(user)
        self.audit.log("login", user=user, session_id=tokens.session.id, module_code="auth", action="login")
        self.db.commit()
        return tokens

    def _open_session(self, user: User) -> IssuedTokens:
        s = get_settings()
        ctx = get_request_context()
        now = now_utc()
        raw = new_opaque_token()
        session = self.sessions.add(UserSession(
            user_id=user.id,
            refresh_token_hash=sha256_hex(raw),
            ip=ctx.ip,
            user_agent=(ctx.user_agent or "")[:500] or None,
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(days=s.refresh_token_days),
        ))
        access, expires_in = create_access_token(user.id, session.id, user.role.code)
        return IssuedTokens(access, expires_in, raw, user, session)

    # --- Sesiones -----------------------------------------------------------------------------

    def inactivity_limit(self) -> timedelta:
        return timedelta(minutes=int(self.settings.get("seguridad.minutos_inactividad")))

    def expire_if_idle(self, session: UserSession) -> bool:
        """Revoca la sesión si superó el tiempo de inactividad. Devuelve True si expiró."""
        now = now_utc()
        if session.revoked_at is None and now - session.last_seen_at > self.inactivity_limit():
            session.revoked_at = now
            session.revoke_reason = "inactividad"
            self.audit.log(
                "sesion_expirada", user=session.user, session_id=session.id, module_code="auth",
                action="expirar", duration_ms=int((now - session.created_at).total_seconds() * 1000),
                after={"motivo": "inactividad", "ultima_actividad": session.last_seen_at.isoformat()},
            )
            self.db.commit()
            return True
        return False

    def refresh(self, raw_token: str | None) -> IssuedTokens:
        if not raw_token:
            raise AuthError("Sesión no encontrada.")
        token_hash = sha256_hex(raw_token)
        session = self.sessions.by_token_hash(token_hash)
        if session is None:
            reused = self.sessions.by_previous_hash(token_hash)
            if reused is not None and reused.revoked_at is None:
                reused.revoked_at = now_utc()
                reused.revoke_reason = "reuso_token"
                self.audit.log("sesion_expirada", user=reused.user, session_id=reused.id, module_code="auth",
                               action="revocar", result="fallo", error_detail="reuso_de_refresh_token")
                self.db.commit()
            raise AuthError("Sesión no válida. Inicie sesión nuevamente.")
        now = now_utc()
        if session.revoked_at is not None or session.expires_at <= now or not session.user.is_active:
            raise AuthError("La sesión ha finalizado. Inicie sesión nuevamente.")
        if self.expire_if_idle(session):
            raise AuthError("La sesión expiró por inactividad.", code="sesion_expirada")

        new_raw = new_opaque_token()
        session.previous_token_hash = session.refresh_token_hash
        session.refresh_token_hash = sha256_hex(new_raw)
        session.last_seen_at = now
        access, expires_in = create_access_token(session.user.id, session.id, session.user.role.code)
        self.db.commit()
        return IssuedTokens(access, expires_in, new_raw, session.user, session)

    def session_from_refresh_cookie(self, raw_token: str | None) -> UserSession | None:
        if not raw_token:
            return None
        session = self.sessions.by_token_hash(sha256_hex(raw_token))
        if session is None or session.revoked_at is not None or session.expires_at <= now_utc():
            return None
        return session

    def logout(self, session: UserSession, reason: str = "logout") -> None:
        if session.revoked_at is not None:
            return
        now = now_utc()
        session.revoked_at = now
        session.revoke_reason = "inactividad" if reason == "inactividad" else "logout"
        event = "sesion_expirada" if reason == "inactividad" else "logout"
        self.audit.log(event, user=session.user, session_id=session.id, module_code="auth", action="logout",
                       duration_ms=int((now - session.created_at).total_seconds() * 1000),
                       after={"motivo": reason})
        self.db.commit()

    # --- Contraseñas --------------------------------------------------------------------------

    def _check_policy(self, password: str) -> None:
        errors = password_policy_errors(password, int(self.settings.get("seguridad.longitud_minima_contrasena")))
        if errors:
            raise BusinessRuleError("La contraseña no cumple la política.", detail=errors,
                                    code="contrasena_debil")

    def forgot_password(self, email: str) -> None:
        user = self.users.by_email(email)
        if user is None or not user.is_active:
            self.audit.log("accion", user_email=email.strip().lower()[:254], module_code="auth",
                           action="solicitar_recuperacion", result="fallo", error_detail="usuario_no_valido")
            self.db.commit()
            return
        s = get_settings()
        now = now_utc()
        self.resets.invalidate_for_user(user.id, now)
        raw = new_opaque_token()
        self.resets.add(PasswordResetToken(user_id=user.id, token_hash=sha256_hex(raw),
                                           expires_at=now + timedelta(minutes=s.password_reset_minutes)))
        self.audit.log("accion", user=user, module_code="auth", action="solicitar_recuperacion",
                       entity_type="usuario", entity_id=user.id)
        self.db.commit()
        link = f"{s.frontend_url.rstrip('/')}/restablecer?token={raw}"
        subject, body = password_reset_email(user.full_name, link, s.password_reset_minutes)
        enqueue_email(user.email, subject, body)

    def reset_password(self, raw_token: str, new_password: str) -> None:
        now = now_utc()
        token = self.resets.by_hash(sha256_hex(raw_token))
        if token is None or token.used_at is not None or token.expires_at <= now:
            raise BusinessRuleError("El enlace no es válido o ha expirado.", code="token_invalido")
        self._check_policy(new_password)
        user = self.users.get(token.user_id)
        assert user is not None
        user.password_hash = hash_password(new_password)
        user.password_changed_at = now
        user.failed_attempts = 0
        user.locked_until = None
        token.used_at = now
        revoked = self.sessions.revoke_all_for_user(user.id, "cambio_contrasena", now)
        self.audit.log("accion", user=user, module_code="auth", action="restablecer_contrasena",
                       entity_type="usuario", entity_id=user.id, after={"sesiones_revocadas": revoked})
        self.db.commit()

    def change_password(self, user: User, session: UserSession, current: str, new: str) -> None:
        if not verify_password(current, user.password_hash):
            self.audit.log("accion", user=user, session_id=session.id, module_code="perfil",
                           action="cambiar_contrasena", result="fallo", error_detail="contrasena_actual_incorrecta")
            self.db.commit()
            raise BusinessRuleError("La contraseña actual no es correcta.", code="contrasena_actual_incorrecta")
        if current == new:
            raise BusinessRuleError("La nueva contraseña debe ser distinta de la actual.")
        self._check_policy(new)
        now = now_utc()
        user.password_hash = hash_password(new)
        user.password_changed_at = now
        revoked = self.sessions.revoke_all_for_user(user.id, "cambio_contrasena", now, except_id=session.id)
        self.audit.log("accion", user=user, session_id=session.id, module_code="perfil",
                       action="cambiar_contrasena", entity_type="usuario", entity_id=user.id,
                       after={"otras_sesiones_revocadas": revoked})
        self.db.commit()
