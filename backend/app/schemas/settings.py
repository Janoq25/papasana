from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SettingOut(BaseModel):
    key: str
    value: Any
    description: str
    type: str
    min: float | None
    max: float | None
    updated_at: datetime | None


class SettingUpdate(BaseModel):
    value: Any
