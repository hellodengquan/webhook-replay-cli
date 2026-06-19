from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, HttpUrl


class WebhookStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    ARCHIVED = "archived"


class WebhookRequest(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    url: HttpUrl
    method: str = "POST"
    headers: Dict[str, str] = Field(default_factory=dict)
    body: str
    timestamp: datetime = Field(default_factory=datetime.now)
    status: WebhookStatus = WebhookStatus.PENDING
    original_signature: Optional[str] = None
    signature_header: str = "X-Webhook-Signature"

    model_config = {"from_attributes": True}


class ReplayResult(BaseModel):
    request_id: str
    success: bool
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: float
    timestamp: datetime = Field(default_factory=datetime.now)
    new_signature: Optional[str] = None
    retried: bool = False

    model_config = {"from_attributes": True}


class ReplaySummary(BaseModel):
    total_requests: int
    success_count: int
    failed_count: int
    total_duration_ms: float
    average_duration_ms: float
    results: Dict[str, ReplayResult] = Field(default_factory=dict)
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return round(self.success_count / self.total_requests * 100, 2)


class ArchiveFilter(BaseModel):
    status: Optional[WebhookStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    url_pattern: Optional[str] = None
    limit: Optional[int] = None
    offset: int = 0
