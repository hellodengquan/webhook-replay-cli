from enum import Enum
from pathlib import Path
from typing import Optional

from .base import StorageBackend
from .json_backend import JsonStorageBackend
from .sqlite_backend import SqliteStorageBackend


class StorageType(str, Enum):
    JSON = "json"
    SQLITE = "sqlite"


def get_storage_backend(
    storage_type: StorageType = StorageType.JSON,
    path: Optional[Path] = None,
) -> StorageBackend:
    if storage_type == StorageType.JSON:
        return JsonStorageBackend(path)
    elif storage_type == StorageType.SQLITE:
        return SqliteStorageBackend(path)
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")


class Storage(StorageBackend):
    def __init__(
        self,
        storage_type: StorageType = StorageType.JSON,
        path: Optional[Path] = None,
    ):
        self._backend = get_storage_backend(storage_type, path)
        self.storage_type = storage_type

    @property
    def backend(self) -> StorageBackend:
        return self._backend

    def save_request(self, request) -> None:
        return self._backend.save_request(request)

    def get_request(self, request_id: str):
        return self._backend.get_request(request_id)

    def list_requests(self, filter=None):
        return self._backend.list_requests(filter)

    def update_status(self, request_id: str, status) -> None:
        return self._backend.update_status(request_id, status)

    def delete_request(self, request_id: str) -> bool:
        return self._backend.delete_request(request_id)

    def clear_all(self) -> int:
        return self._backend.clear_all()

    def count(self, status=None) -> int:
        return self._backend.count(status)


__all__ = [
    "StorageBackend",
    "JsonStorageBackend",
    "SqliteStorageBackend",
    "StorageType",
    "get_storage_backend",
    "Storage",
]
