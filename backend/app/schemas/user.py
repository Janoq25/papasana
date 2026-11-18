import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, computed_field

from app.core.security import now_utc
from app.schemas.common import ORMModel


class RoleBrief(ORMModel):
    id: int
    code: str
    name: str
    data_scope: str


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    full_name: str
    institution: str | None
    phone: str | None
    region_code: str | None
    role: RoleBrief
    is_active: bool
    locked_until: datetime | None
    last_login_at: datetime | None
    created_at: datetime
    photo_key: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def is_locked(self) -> bool:
        return bool(self.locked_until and self.locked_until > now_utc())

    @computed_field
    @property
    def has_photo(self) -> bool:
        return bool(self.photo_key)


class MeOut(UserOut):
    preferences: dict[str, Any]
    permissions: list[str] = []
    session_settings: dict[str, Any] = {}


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=1, max_length=128)
    role_id: int
    institution: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=30, pattern=r"^[0-9+\-\s()]*$")
    region_code: str | None = Field(default=None, pattern=r"^\d{6}$")


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=160)
    institution: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=30, pattern=r"^[0-9+\-\s()]*$")
    region_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    role_id: int | None = None
    is_active: bool | None = None


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=160)
    institution: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=30, pattern=r"^[0-9+\-\s()]*$")
    region_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    preferences: dict[str, Any] | None = None


class UbigeoOut(ORMModel):
    code: str
    name: str
    level: str
    parent_code: str | None
