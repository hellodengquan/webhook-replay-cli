import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from ..models import ArchiveFilter, WebhookStatus
from .base import StorageBackend


class SqliteStorageBackend(StorageBackend):
    """SQLite 后端：只负责 schema 定义 + 原生 SQL 原子操作。"""

    SCHEMA_SQL = """
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
    INDEX_SQL = [
        "CREATE INDEX IF NOT EXISTS idx_status ON webhook_requests(status)",
        "CREATE INDEX IF NOT EXISTS idx_timestamp ON webhook_requests(timestamp)",
    ]

    COLUMNS = (
        "id", "url", "method", "headers", "body",
        "timestamp", "status", "original_signature", "signature_header",
    )

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".webhook_replay" / "requests.db"
        super().__init__()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_initialized(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            conn.execute(self.SCHEMA_SQL)
            for idx in self.INDEX_SQL:
                conn.execute(idx)
            conn.commit()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict:
        data = dict(row)
        data["headers"] = json.loads(data["headers"]) if data["headers"] else {}
        return data

    @staticmethod
    def _row_to_params(row: Dict) -> tuple:
        headers = json.dumps(row.get("headers", {}), ensure_ascii=False)
        return (
            row["id"],
            row["url"],
            row["method"],
            headers,
            row["body"],
            row["timestamp"],
            row["status"],
            row.get("original_signature"),
            row["signature_header"],
        )

    def _read_all_raw(self) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.execute(f"SELECT {', '.join(self.COLUMNS)} FROM webhook_requests")
            return [self._row_to_dict(r) for r in cursor.fetchall()]

    def _write_all_raw(self, rows: List[Dict]) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM webhook_requests")
            if rows:
                placeholders = ", ".join("?" for _ in self.COLUMNS)
                conn.executemany(
                    f"INSERT INTO webhook_requests ({', '.join(self.COLUMNS)}) VALUES ({placeholders})",
                    [self._row_to_params(r) for r in rows],
                )
            conn.commit()

    def _upsert_row(self, row: Dict) -> None:
        placeholders = ", ".join("?" for _ in self.COLUMNS)
        with self._get_connection() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO webhook_requests ({', '.join(self.COLUMNS)}) "
                f"VALUES ({placeholders})",
                self._row_to_params(row),
            )
            conn.commit()

    def _delete_row(self, request_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM webhook_requests WHERE id = ?",
                (request_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def _count_rows(self, status: Optional[WebhookStatus] = None) -> int:
        query = "SELECT COUNT(*) FROM webhook_requests"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status.value)
        with self._get_connection() as conn:
            return conn.execute(query, params).fetchone()[0]

    @staticmethod
    def _build_where(filter: Optional[ArchiveFilter]) -> tuple[str, list]:
        if not filter:
            return "", []
        conditions, params = [], []
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

    def list_requests(self, filter: Optional[ArchiveFilter] = None):
        where, params = self._build_where(filter)
        query = f"SELECT {', '.join(self.COLUMNS)} FROM webhook_requests {where} ORDER BY timestamp DESC"
        if filter and filter.limit:
            offset = filter.offset or 0
            query += f" LIMIT {filter.limit} OFFSET {offset}"
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._deserialize(self._row_to_dict(r)) for r in rows]
