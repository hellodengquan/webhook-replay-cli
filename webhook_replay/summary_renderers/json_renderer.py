import json

from ..models import ReplaySummary
from .base import SummaryRenderer


class JsonSummaryRenderer(SummaryRenderer):
    def __init__(self, indent: int = 2, ensure_ascii: bool = False):
        self.indent = indent
        self.ensure_ascii = ensure_ascii

    def render(self, summary: ReplaySummary) -> str:
        return json.dumps(
            summary.model_dump(mode="json"),
            indent=self.indent,
            ensure_ascii=self.ensure_ascii,
        )
