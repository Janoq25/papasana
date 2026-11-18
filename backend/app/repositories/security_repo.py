import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import (
    Module,
    PasswordResetToken,
    Permission,
    Role,
    User,
    UserSession,
)


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))

    def search(
        self, *, q: str | None, role_id: int | None, is_active: bool | None, page: int, size: int
    ) -> tuple[list[User], int]:
        stmt = select(User)
        if q:
            like = f"%{q.strip().lower()}%"
            stmt = stmt.where(func.lower(User.email).like(like) | func.lower(User.full_name).like(like))
        if role_id is not None:
            stmt = stmt.where(User.role_id == role_id)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self.db.scalars(stmt.order_by(User.full_name).offset((page - 1) * size).limit(size)).all()
        return list(items), total

    def count_active_with_role(self, role_id: int) -> int:
        return self.db.scalar(
            select(func.count()).select_from(User).where(User.role_id == role_id, User.is_active.is_(True))
        ) or 0

    def count_with_role(self, role_id: int) -> int:
        return self.db.scalar(select(func.count()).select_from(User).where(User.role_id == role_id)) or 0

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user


class RoleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, role_id: int) -> Role | None:
        return self.db.get(Role, role_id)

    def by_code(self, code: str) -> Role | None:
        return self.db.scalar(select(Role).where(Role.code == code))

    def list_all(self) -> list[Role]:
        return list(self.db.scalars(select(Role).order_by(Role.id)).all())

    def permissions_by_keys(self, keys: set[str]) -> list[Permission]:
        perms = self.db.scalars(select(Permission).join(Module)).all()
        return [p for p in perms if p.key in keys]

    def all_permissions(self) -> list[Permission]:
        return list(self.db.scalars(select(Permission).join(Module).order_by(Module.sort_order)).all())

    def modules(self) -> list[Module]:
        return list(self.db.scalars(select(Module).order_by(Module.sort_order)).all())

    def module_codes(self) -> set[str]:
        return set(self.db.scalars(select(Module.code)).all())


class SessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, session_id: uuid.UUID) -> UserSession | None:
        return self.db.get(UserSession, session_id)

    def by_token_hash(self, token_hash: str) -> UserSession | None:
        return self.db.scalar(select(UserSession).where(UserSession.refresh_token_hash == token_hash))

    def by_previous_hash(self, token_hash: str) -> UserSession | None:
        return self.db.scalar(select(UserSession).where(UserSession.previous_token_hash == token_hash))

    def add(self, s: UserSession) -> UserSession:
        self.db.add(s)
        self.db.flush()
        return s

    def revoke_all_for_user(
        self, user_id: uuid.UUID, reason: str, now: datetime, except_id: uuid.UUID | None = None
    ) -> int:
        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=now, revoke_reason=reason)
        )
        if except_id is not None:
            stmt = stmt.where(UserSession.id != except_id)
        return self.db.execute(stmt).rowcount or 0


class PasswordResetRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, t: PasswordResetToken) -> None:
        self.db.add(t)
        self.db.flush()

    def by_hash(self, token_hash: str) -> PasswordResetToken | None:
        return self.db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))

    def invalidate_for_user(self, user_id: uuid.UUID, now: datetime) -> None:
        self.db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
            .values(used_at=now)
        )
