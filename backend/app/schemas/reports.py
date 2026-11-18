import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ReportRequest(BaseModel):
    code: str = Field(pattern=r"^[RB]-\d{2}$", examples=["R-01"])
    format: Literal["pdf", "docx", "xlsx"]
    filters: dict = Field(default_factory=dict)


class ReportJobOut(ORMModel):
    id: uuid.UUID
    report_code: str
    report_title: str | None = None
    format: str
    filters: dict
    status: str
    file_name: str | None
    size_bytes: int | None
    row_count: int | None
    error: str | None
    download_count: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class NotificationOut(ORMModel):
    id: int
    kind: str
    title: str
    body: str | None
    link: str | None
    entity_type: str | None
    entity_id: str | None
    created_at: datetime
    read_at: datetime | None


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    total: int
    page: int
    size: int
    unread: int


class NotificationSummary(BaseModel):
    unread: int
    recent: list[NotificationOut]
