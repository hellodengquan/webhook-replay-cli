from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from ..models import ReplayResult, ReplaySummary, WebhookStatus
from ..storage import StorageBackend
from .base import SummaryRenderer
from .json_renderer import JsonSummaryRenderer
from .markdown_renderer import MarkdownSummaryRenderer
from .text_renderer import TextSummaryRenderer


class SummaryFormat(str, Enum):
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"


_RENDERER_MAP: Dict[SummaryFormat, type[SummaryRenderer]] = {
    SummaryFormat.TEXT: TextSummaryRenderer,
    SummaryFormat.JSON: JsonSummaryRenderer,
    SummaryFormat.MARKDOWN: MarkdownSummaryRenderer,
}


def get_summary_renderer(format: SummaryFormat | str) -> SummaryRenderer:
    if isinstance(format, str):
        format = SummaryFormat(format.lower())
    renderer_cls = _RENDERER_MAP.get(format)
    if not renderer_cls:
        raise ValueError(f"Unsupported summary format: {format}")
    return renderer_cls()


class SummaryGenerator:
    def __init__(self, storage: Optional[StorageBackend] = None):
        self.storage = storage

    def generate_summary(self, results: List[ReplayResult]) -> ReplaySummary:
        success_count = sum(1 for r in results if r.success)
        failed_count = len(results) - success_count
        total_duration = sum(r.duration_ms for r in results)
        avg_duration = total_duration / len(results) if results else 0

        results_dict = {r.request_id: r for r in results}

        return ReplaySummary(
            total_requests=len(results),
            success_count=success_count,
            failed_count=failed_count,
            total_duration_ms=round(total_duration, 2),
            average_duration_ms=round(avg_duration, 2),
            results=results_dict,
            end_time=datetime.now(),
        )

    def render_summary(
        self,
        summary: ReplaySummary,
        format: SummaryFormat | str = SummaryFormat.TEXT,
    ) -> str:
        renderer = get_summary_renderer(format)
        return renderer.render(summary)

    def get_failed_requests(self, results: List[ReplayResult]) -> List[ReplayResult]:
        return [r for r in results if not r.success]

    def get_successful_requests(self, results: List[ReplayResult]) -> List[ReplayResult]:
        return [r for r in results if r.success]

    def format_text_summary(self, summary: ReplaySummary) -> str:
        return self.render_summary(summary, SummaryFormat.TEXT)

    def format_json_summary(self, summary: ReplaySummary) -> str:
        return self.render_summary(summary, SummaryFormat.JSON)

    def format_markdown_summary(self, summary: ReplaySummary) -> str:
        return self.render_summary(summary, SummaryFormat.MARKDOWN)

    def get_storage_stats(self) -> Dict[str, int]:
        if not self.storage:
            return {}
        return {
            "total": self.storage.count(),
            "pending": self.storage.count(WebhookStatus.PENDING),
            "success": self.storage.count(WebhookStatus.SUCCESS),
            "failed": self.storage.count(WebhookStatus.FAILED),
            "archived": self.storage.count(WebhookStatus.ARCHIVED),
        }


__all__ = [
    "SummaryRenderer",
    "TextSummaryRenderer",
    "JsonSummaryRenderer",
    "MarkdownSummaryRenderer",
    "SummaryFormat",
    "get_summary_renderer",
    "SummaryGenerator",
]
