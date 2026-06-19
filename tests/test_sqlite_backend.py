import json
from datetime import datetime
from pathlib import Path

import pytest

from webhook_replay.models import ArchiveFilter, WebhookRequest, WebhookStatus
from webhook_replay.storage.sqlite_backend import SqliteStorageBackend


class TestSqliteSchemaInit:
    def test_creates_db_file_on_init(self, tmp_db: Path):
        assert not tmp_db.exists()
        SqliteStorageBackend(db_path=tmp_db)
        assert tmp_db.exists()

    def test_creates_parent_directory(self, tmp_path: Path):
        db_path = tmp_path / "subdir" / "deep" / "test.db"
        SqliteStorageBackend(db_path=db_path)
        assert db_path.exists()

    def test_idempotent_init(self, tmp_db: Path):
        SqliteStorageBackend(db_path=tmp_db)
        SqliteStorageBackend(db_path=tmp_db)
        backend = SqliteStorageBackend(db_path=tmp_db)
        assert backend.count() == 0


class TestSqliteSaveAndGet:
    def test_save_and_get_request(self, sqlite_backend: SqliteStorageBackend):
        req = WebhookRequest(
            id="save001",
            url="https://example.com/hook",
            method="POST",
            headers={"Content-Type": "application/json"},
            body='{"key": "value"}',
            status=WebhookStatus.ARCHIVED,
        )
        sqlite_backend.save_request(req)
        got = sqlite_backend.get_request("save001")
        assert got is not None
        assert got.id == "save001"
        assert str(got.url) == "https://example.com/hook"
        assert got.method == "POST"
        assert got.headers == {"Content-Type": "application/json"}
        assert got.body == '{"key": "value"}'
        assert got.status == WebhookStatus.ARCHIVED

    def test_get_nonexistent_returns_none(self, sqlite_backend: SqliteStorageBackend):
        assert sqlite_backend.get_request("no_such_id") is None

    def test_save_upsert(self, sqlite_backend: SqliteStorageBackend):
        req = WebhookRequest(
            id="upsert001",
            url="https://example.com/v1",
            body="original",
            status=WebhookStatus.PENDING,
        )
        sqlite_backend.save_request(req)

        req.body = "updated"
        req.status = WebhookStatus.SUCCESS
        sqlite_backend.save_request(req)

        got = sqlite_backend.get_request("upsert001")
        assert got is not None
        assert got.body == "updated"
        assert got.status == WebhookStatus.SUCCESS

    def test_save_preserves_headers_json(self, sqlite_backend: SqliteStorageBackend):
        req = WebhookRequest(
            id="hdr001",
            url="https://example.com/h",
            headers={"X-Custom": "val1", "Authorization": "Bearer xyz"},
            body="{}",
        )
        sqlite_backend.save_request(req)
        got = sqlite_backend.get_request("hdr001")
        assert got.headers == {"X-Custom": "val1", "Authorization": "Bearer xyz"}

    def test_save_preserves_original_signature(self, sqlite_backend: SqliteStorageBackend):
        req = WebhookRequest(
            id="sig001",
            url="https://example.com/s",
            body="{}",
            original_signature="sha256=abc123",
            signature_header="X-Hub-Signature-256",
        )
        sqlite_backend.save_request(req)
        got = sqlite_backend.get_request("sig001")
        assert got.original_signature == "sha256=abc123"
        assert got.signature_header == "X-Hub-Signature-256"


class TestSqliteList:
    def test_list_all(self, sqlite_backend: SqliteStorageBackend, sample_requests):
        for req in sample_requests:
            sqlite_backend.save_request(req)
        result = sqlite_backend.list_requests()
        assert len(result) == 3

    def test_list_ordered_by_timestamp_desc(self, sqlite_backend: SqliteStorageBackend, sample_requests):
        for req in sample_requests:
            sqlite_backend.save_request(req)
        result = sqlite_backend.list_requests()
        timestamps = [r.timestamp for r in result]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_list_filter_by_status(self, sqlite_backend: SqliteStorageBackend, sample_requests):
        for req in sample_requests:
            sqlite_backend.save_request(req)
        result = sqlite_backend.list_requests(ArchiveFilter(status=WebhookStatus.FAILED))
        assert len(result) == 1
        assert result[0].id == "req002"

    def test_list_filter_by_url_pattern(self, sqlite_backend: SqliteStorageBackend, sample_requests):
        for req in sample_requests:
            sqlite_backend.save_request(req)
        result = sqlite_backend.list_requests(ArchiveFilter(url_pattern="other.service"))
        assert len(result) == 1
        assert result[0].id == "req003"

    def test_list_filter_by_date_range(self, sqlite_backend: SqliteStorageBackend, sample_requests):
        for req in sample_requests:
            sqlite_backend.save_request(req)
        f = ArchiveFilter(
            start_date=datetime(2026, 2, 1),
            end_date=datetime(2026, 4, 30),
        )
        result = sqlite_backend.list_requests(f)
        assert len(result) == 1
        assert result[0].id == "req002"

    def test_list_filter_with_limit(self, sqlite_backend: SqliteStorageBackend, sample_requests):
        for req in sample_requests:
            sqlite_backend.save_request(req)
        result = sqlite_backend.list_requests(ArchiveFilter(limit=2))
        assert len(result) == 2

    def test_list_filter_combined(self, sqlite_backend: SqliteStorageBackend, sample_requests):
        for req in sample_requests:
            sqlite_backend.save_request(req)
        f = ArchiveFilter(
            status=WebhookStatus.ARCHIVED,
            url_pattern="example.com",
        )
        result = sqlite_backend.list_requests(f)
        assert len(result) == 1
        assert result[0].id == "req001"

    def test_list_empty_db(self, sqlite_backend: SqliteStorageBackend):
        result = sqlite_backend.list_requests()
        assert result == []


class TestSqliteUpdateStatus:
    def test_update_status(self, sqlite_backend: SqliteStorageBackend):
        req = WebhookRequest(
            id="upd001",
            url="https://example.com/u",
            body="{}",
            status=WebhookStatus.PENDING,
        )
        sqlite_backend.save_request(req)
        sqlite_backend.update_status("upd001", WebhookStatus.SUCCESS)

        got = sqlite_backend.get_request("upd001")
        assert got.status == WebhookStatus.SUCCESS
        assert sqlite_backend.count(WebhookStatus.SUCCESS) == 1
        assert sqlite_backend.count(WebhookStatus.PENDING) == 0

    def test_update_nonexistent_no_error(self, sqlite_backend: SqliteStorageBackend):
        sqlite_backend.update_status("ghost", WebhookStatus.FAILED)


class TestSqliteDelete:
    def test_delete_existing(self, sqlite_backend: SqliteStorageBackend):
        req = WebhookRequest(id="del001", url="https://example.com/d", body="{}")
        sqlite_backend.save_request(req)
        assert sqlite_backend.delete_request("del001") is True
        assert sqlite_backend.get_request("del001") is None

    def test_delete_nonexistent(self, sqlite_backend: SqliteStorageBackend):
        assert sqlite_backend.delete_request("ghost") is False


class TestSqliteClearAll:
    def test_clear_all(self, sqlite_backend: SqliteStorageBackend, sample_requests):
        for req in sample_requests:
            sqlite_backend.save_request(req)
        assert sqlite_backend.count() == 3
        cleared = sqlite_backend.clear_all()
        assert cleared == 3
        assert sqlite_backend.count() == 0

    def test_clear_empty_db(self, sqlite_backend: SqliteStorageBackend):
        cleared = sqlite_backend.clear_all()
        assert cleared == 0


class TestSqliteCount:
    def test_count_all(self, sqlite_backend: SqliteStorageBackend, sample_requests):
        for req in sample_requests:
            sqlite_backend.save_request(req)
        assert sqlite_backend.count() == 3

    def test_count_by_status(self, sqlite_backend: SqliteStorageBackend, sample_requests):
        for req in sample_requests:
            sqlite_backend.save_request(req)
        assert sqlite_backend.count(WebhookStatus.ARCHIVED) == 1
        assert sqlite_backend.count(WebhookStatus.FAILED) == 1
        assert sqlite_backend.count(WebhookStatus.SUCCESS) == 1
        assert sqlite_backend.count(WebhookStatus.PENDING) == 0
