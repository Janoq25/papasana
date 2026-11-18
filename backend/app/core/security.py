"""Contraseñas (Argon2id), tokens JWT de acceso y tokens opacos (refresh, recuperación)."""

import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

_ph = PasswordHasher()  # Argon2id con parámetros recomendados por defecto
# Hash ficticio para igualar tiempos cuando el usuario no existe (evita enumeración)
_DUMMY_HASH = _ph.hash("contrasena-ficticia-para-igualar-tiempos")


def now_utc() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _ph.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _ph.check_needs_rehash(password_hash)


def password_policy_errors(password: str, min_length: int) -> list[str]:
    errors = []
    if len(password) < min_length:
        errors.append(f"Debe tener al menos {min_length} caracteres.")
    if len(password) > 128:
        errors.append("No debe superar 128 caracteres.")
    if not re.search(r"[a-záéíóúñ]", password):
        errors.append("Debe incluir una letra minúscula.")
    if not re.search(r"[A-ZÁÉÍÓÚÑ]", password):
        errors.append("Debe incluir una letra mayúscula.")
    if not re.search(r"\d", password):
        errors.append("Debe incluir un número.")
    return errors


def create_access_token(user_id: uuid.UUID, session_id: uuid.UUID, role_code: str) -> tuple[str, int]:
    s = get_settings()
    expires = timedelta(minutes=s.access_token_minutes)
    now = now_utc()
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "role": role_code,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + expires).timestamp()),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), int(expires.total_seconds())


def decode_access_token(token: str) -> dict:
    s = get_settings()
    payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm], options={"require": ["exp", "sub"]})
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Tipo de token inválido")
    return payload


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
