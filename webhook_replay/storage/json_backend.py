import json
from pathlib import Path
from typing import Dict, List, Optional

from .base import StorageBackend


class JsonStorageBackend(StorageBackend):
    """JSON 文件后端：只负责路径管理 + 文件原子读写。"""

    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.home() / ".webhook_replay"
        self.requests_file = self.base_path / "requests.json"
        super().__init__()

    def _ensure_initialized(self) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)
        if not self.requests_file.exists():
            self.requests_file.write_text(json.dumps([]))

    def _read_all_raw(self) -> List[Dict]:
        try:
            with open(self.requests_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_all_raw(self, rows: List[Dict]) -> None:
        with open(self.requests_file, "w") as f:
            json.dump(rows, f, indent=2, default=str)
