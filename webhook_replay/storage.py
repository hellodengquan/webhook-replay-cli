import json
from pathlib import Path
from typing import List, Optional

from .models import ArchiveFilter, WebhookRequest, WebhookStatus


class Storage:
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.home() / ".webhook_replay"
        self.requests_file = self.base_path / "requests.json"
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)
        if not self.requests_file.exists():
            self.requests_file.write_text(json.dumps([]))

    def _load_requests(self) -> List[dict]:
        try:
            with open(self.requests_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_requests(self, requests: List[dict]) -> None:
        with open(self.requests_file, "w") as f:
            json.dump(requests, f, indent=2, default=str)

    def save_request(self, request: WebhookRequest) -> None:
        requests = self._load_requests()
        existing = next((r for r in requests if r["id"] == request.id), None)
        request_dict = request.model_dump(mode="json")
        if existing:
            idx = requests.index(existing)
            requests[idx] = request_dict
        else:
            requests.append(request_dict)
        self._save_requests(requests)

    def get_request(self, request_id: str) -> Optional[WebhookRequest]:
        requests = self._load_requests()
        for r in requests:
            if r["id"] == request_id:
                return WebhookRequest.model_validate(r)
        return None

    def list_requests(self, filter: Optional[ArchiveFilter] = None) -> List[WebhookRequest]:
        requests = self._load_requests()
        webhook_requests = [WebhookRequest.model_validate(r) for r in requests]

        if filter:
            if filter.status:
                webhook_requests = [r for r in webhook_requests if r.status == filter.status]
            if filter.start_date:
                webhook_requests = [r for r in webhook_requests if r.timestamp >= filter.start_date]
            if filter.end_date:
                webhook_requests = [r for r in webhook_requests if r.timestamp <= filter.end_date]
            if filter.url_pattern:
                webhook_requests = [
                    r for r in webhook_requests if filter.url_pattern.lower() in str(r.url).lower()
                ]
            if filter.offset:
                webhook_requests = webhook_requests[filter.offset:]
            if filter.limit:
                webhook_requests = webhook_requests[: filter.limit]

        webhook_requests.sort(key=lambda r: r.timestamp, reverse=True)
        return webhook_requests

    def update_status(self, request_id: str, status: WebhookStatus) -> None:
        request = self.get_request(request_id)
        if request:
            request.status = status
            self.save_request(request)

    def delete_request(self, request_id: str) -> bool:
        requests = self._load_requests()
        original_len = len(requests)
        requests = [r for r in requests if r["id"] != request_id]
        if len(requests) != original_len:
            self._save_requests(requests)
            return True
        return False

    def clear_all(self) -> int:
        count = len(self._load_requests())
        self._save_requests([])
        return count

    def count(self, status: Optional[WebhookStatus] = None) -> int:
        requests = self.list_requests(ArchiveFilter(status=status) if status else None)
        return len(requests)
