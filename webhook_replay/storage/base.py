from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from ..models import ArchiveFilter, WebhookRequest, WebhookStatus


class StorageBackend(ABC):
    """
    存储后端抽象基类。

    使用 Template Method 模式：
      - 基础 CRUD 流程（序列化/反序列化、过滤排序、默认
        update_status / count / clear_all）在基类中固定；
      - 子类仅实现原子化的低阶钩子方法：
        * _ensure_initialized  — 存储初始化
        * _read_all_raw        — 读取全部原始行
        * _write_all_raw       — 全量写回原始行（JSON 等后端）
        * _upsert_row          — 按 id 插入/更新（子类可覆写）
        * _delete_row          — 按 id 删除（子类可覆写）
        * _count_rows          — 计数（子类可覆写）
    """

    def __init__(self) -> None:
        self._ensure_initialized()

    @abstractmethod
    def _ensure_initialized(self) -> None: ...

    @abstractmethod
    def _read_all_raw(self) -> List[Dict]: ...

    @abstractmethod
    def _write_all_raw(self, rows: List[Dict]) -> None: ...

    def _upsert_row(self, row: Dict) -> None:
        rows = self._read_all_raw()
        existing_idx = None
        for i, r in enumerate(rows):
            if r["id"] == row["id"]:
                existing_idx = i
                break
        if existing_idx is not None:
            rows[existing_idx] = row
        else:
            rows.append(row)
        self._write_all_raw(rows)

    def _delete_row(self, request_id: str) -> bool:
        rows = self._read_all_raw()
        original_len = len(rows)
        rows = [r for r in rows if r["id"] != request_id]
        changed = len(rows) != original_len
        if changed:
            self._write_all_raw(rows)
        return changed

    def _count_rows(self, status: Optional[WebhookStatus] = None) -> int:
        filter = ArchiveFilter(status=status) if status else None
        return len(self.list_requests(filter))

    @staticmethod
    def _serialize(request: WebhookRequest) -> Dict:
        return request.model_dump(mode="json")

    @staticmethod
    def _deserialize(row: Dict) -> WebhookRequest:
        return WebhookRequest.model_validate(row)

    def _apply_filter_and_sort(
        self,
        requests: List[WebhookRequest],
        filter: Optional[ArchiveFilter],
    ) -> List[WebhookRequest]:
        if filter:
            if filter.status:
                requests = [r for r in requests if r.status == filter.status]
            if filter.start_date:
                requests = [r for r in requests if r.timestamp >= filter.start_date]
            if filter.end_date:
                requests = [r for r in requests if r.timestamp <= filter.end_date]
            if filter.url_pattern:
                requests = [
                    r for r in requests
                    if filter.url_pattern.lower() in str(r.url).lower()
                ]
            if filter.offset:
                requests = requests[filter.offset:]
            if filter.limit:
                requests = requests[: filter.limit]

        requests.sort(key=lambda r: r.timestamp, reverse=True)
        return requests

    def save_request(self, request: WebhookRequest) -> None:
        self._upsert_row(self._serialize(request))

    def get_request(self, request_id: str) -> Optional[WebhookRequest]:
        for r in self._read_all_raw():
            if r["id"] == request_id:
                return self._deserialize(r)
        return None

    def list_requests(self, filter: Optional[ArchiveFilter] = None) -> List[WebhookRequest]:
        rows = self._read_all_raw()
        requests = [self._deserialize(r) for r in rows]
        return self._apply_filter_and_sort(requests, filter)

    def update_status(self, request_id: str, status: WebhookStatus) -> None:
        request = self.get_request(request_id)
        if request:
            request.status = status
            self.save_request(request)

    def delete_request(self, request_id: str) -> bool:
        return self._delete_row(request_id)

    def clear_all(self) -> int:
        count = self._count_rows()
        self._write_all_raw([])
        return count

    def count(self, status: Optional[WebhookStatus] = None) -> int:
        return self._count_rows(status)
