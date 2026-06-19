from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import ArchiveFilter, WebhookRequest, WebhookStatus


class StorageBackend(ABC):
    @abstractmethod
    def save_request(self, request: WebhookRequest) -> None:
        ...

    @abstractmethod
    def get_request(self, request_id: str) -> Optional[WebhookRequest]:
        ...

    @abstractmethod
    def list_requests(self, filter: Optional[ArchiveFilter] = None) -> List[WebhookRequest]:
        ...

    @abstractmethod
    def update_status(self, request_id: str, status: WebhookStatus) -> None:
        ...

    @abstractmethod
    def delete_request(self, request_id: str) -> bool:
        ...

    @abstractmethod
    def clear_all(self) -> int:
        ...

    @abstractmethod
    def count(self, status: Optional[WebhookStatus] = None) -> int:
        ...
