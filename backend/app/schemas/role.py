from typing import Literal

from pydantic import BaseModel, Field


class RoleOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    data_scope: str
    is_system: bool
    user_count: int
    permissions: list[str]


class RoleCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z_]{3,40}$")
    name: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    data_scope: Literal["todo", "region", "propio"] = "propio"


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    data_scope: Literal["todo", "region", "propio"] | None = None


class RolePermissionsIn(BaseModel):
    permissions: list[str] = Field(max_length=500)
