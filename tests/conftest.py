from datetime import datetime
from pathlib import Path

import pytest

from webhook_replay.models import (
    ReplayResult,
    ReplaySummary,
    WebhookRequest,
    WebhookStatus,
)
from webhook_replay.storage.sqlite_backend import SqliteStorageBackend


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def sqlite_backend(tmp_db: Path) -> SqliteStorageBackend:
    return SqliteStorageBackend(db_path=tmp_db)


@pytest.fixture
def sample_requests() -> list[WebhookRequest]:
    return [
        WebhookRequest(
            id="req001",
            url="https://api.example.com/webhook",
            method="POST",
            headers={"Content-Type": "application/json", "X-Webhook-Signature": "sig001"},
            body='{"event": "user.created"}',
            timestamp=datetime(2026, 1, 15, 10, 30, 0),
            status=WebhookStatus.ARCHIVED,
            original_signature="sig001",
        ),
        WebhookRequest(
            id="req002",
            url="https://api.example.com/notify",
            method="POST",
            headers={"Content-Type": "application/json"},
            body='{"event": "order.placed"}',
            timestamp=datetime(2026, 3, 20, 14, 0, 0),
            status=WebhookStatus.FAILED,
        ),
        WebhookRequest(
            id="req003",
            url="https://other.service.com/hook",
            method="GET",
            body="",
            timestamp=datetime(2026, 5, 10, 8, 0, 0),
            status=WebhookStatus.SUCCESS,
        ),
    ]


@pytest.fixture
def sample_summary() -> ReplaySummary:
    results = {
        "abc123": ReplayResult(
            request_id="abc123",
            success=True,
            status_code=200,
            duration_ms=150.5,
            timestamp=datetime(2026, 6, 19, 10, 0, 0),
        ),
        "def456": ReplayResult(
            request_id="def456",
            success=False,
            status_code=500,
            error_message="Internal Server Error",
            duration_ms=500.2,
            timestamp=datetime(2026, 6, 19, 10, 0, 1),
        ),
        "ghi789": ReplayResult(
            request_id="ghi789",
            success=True,
            status_code=201,
            duration_ms=75.3,
            timestamp=datetime(2026, 6, 19, 10, 0, 2),
        ),
    }
    return ReplaySummary(
        total_requests=3,
        success_count=2,
        failed_count=1,
        total_duration_ms=726.0,
        average_duration_ms=242.0,
        results=results,
        start_time=datetime(2026, 6, 19, 10, 0, 0),
        end_time=datetime(2026, 6, 19, 10, 0, 3),
    )


@pytest.fixture
def all_failed_summary() -> ReplaySummary:
    results = {
        "fail001": ReplayResult(
            request_id="fail001",
            success=False,
            status_code=503,
            error_message="Service Unavailable",
            duration_ms=1200.0,
        ),
        "fail002": ReplayResult(
            request_id="fail002",
            success=False,
            error_message="Connection Timeout",
            duration_ms=30000.0,
        ),
    }
    return ReplaySummary(
        total_requests=2,
        success_count=0,
        failed_count=2,
        total_duration_ms=31200.0,
        average_duration_ms=15600.0,
        results=results,
        start_time=datetime(2026, 6, 19, 11, 0, 0),
        end_time=datetime(2026, 6, 19, 11, 0, 5),
    )


@pytest.fixture
def all_success_summary() -> ReplaySummary:
    results = {
        "ok001": ReplayResult(
            request_id="ok001",
            success=True,
            status_code=200,
            duration_ms=50.0,
        ),
    }
    return ReplaySummary(
        total_requests=1,
        success_count=1,
        failed_count=0,
        total_duration_ms=50.0,
        average_duration_ms=50.0,
        results=results,
        start_time=datetime(2026, 6, 19, 12, 0, 0),
        end_time=datetime(2026, 6, 19, 12, 0, 1),
    )


@pytest.fixture
def empty_summary() -> ReplaySummary:
    return ReplaySummary(
        total_requests=0,
        success_count=0,
        failed_count=0,
        total_duration_ms=0.0,
        average_duration_ms=0.0,
        results={},
        start_time=datetime(2026, 6, 19, 13, 0, 0),
        end_time=datetime(2026, 6, 19, 13, 0, 0),
    )
