import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from ..models import ArchiveFilter, WebhookRequest, WebhookStatus
from .base import StorageBackend


class SqliteStorageBackend(StorageBackend):
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".webhook_replay" / "requests.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_requests (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    method TEXT NOT NULL DEFAULT 'POST',
                    headers TEXT NOT NULL DEFAULT '{}',
                    body TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    original_signature TEXT,
                    signature_header TEXT NOT NULL DEFAULT 'X-Webhook-Signature'
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_status ON webhook_requests(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_timestamp ON webhook_requests(timestamp)"
            )
            conn.commit()

    def _row_to_request(self, row: sqlite3.Row) -> WebhookRequest:
        data = dict(row)
        data["headers"] = json.loads(data["headers"]) if data["headers"] else {}
        return WebhookRequest.model_validate(data)

    def _build_where_clause(self, filter: Optional[ArchiveFilter]) -> tuple[str, list]:
        if not filter:
            return "", []

        conditions = []
        params = []

        if filter.status:
            conditions.append("status = ?")
            params.append(filter.status.value)
        if filter.start_date:
            conditions.append("timestamp >= ?")
            params.append(filter.start_date.isoformat())
        if filter.end_date:
            conditions.append("timestamp <= ?")
            params.append(filter.end_date.isoformat())
        if filter.url_pattern:
            conditions.append("url LIKE ?")
            params.append(f"%{filter.url_pattern}%")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return where, params

    def save_request(self, request: WebhookRequest) -> None:
        data = request.model_dump(mode="json")
        data["headers"] = json.dumps(data["headers"], ensure_ascii=False)
        data["timestamp"] = data["timestamp"]

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO webhook_requests
                (id, url, method, headers, body, timestamp, status, original_signature, signature_header)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["id"],
                    data["url"],
                    data["method"],
                    data["headers"],
                    data["body"],
                    data["timestamp"],
                    data["status"],
                    data.get("original_signature"),
                    data["signature_header"],
                ),
            )
            conn.commit()

    def get_request(self, request_id: str) -> Optional[WebhookRequest]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM webhook_requests WHERE id = ?", (request_id,)
            )
            row = cursor.fetchone()
            return self._row_to_request(row) if row else None

    def list_requests(self, filter: Optional[ArchiveFilter] = None) -> List[WebhookRequest]:
        where, params = self._build_where_clause(filter)
        query = f"SELECT * FROM webhook_requests {where} ORDER BY timestamp DESC"

        if filter and filter.limit:
            offset = filter.offset or 0
            query += f" LIMIT {filter.limit} OFFSET {offset}"

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_request(row) for row in rows]

    def update_status(self, request_id: str, status: WebhookStatus) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE webhook_requests SET status = ? WHERE id = ?",
                (status.value, request_id),
            )
            conn.commit()

    def delete_request(self, request_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM webhook_requests WHERE id = ?", (request_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def clear_all(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM webhook_requests")
            count = cursor.fetchone()[0]
            conn.execute("DELETE FROM webhook_requests")
            conn.commit()
            return count

    def count(self, status: Optional[WebhookStatus] = None) -> int:
        query = "SELECT COUNT(*) FROM webhook_requests"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status.value)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchone()[0]
