from abc import ABC, abstractmethod

from ..models import ReplaySummary


class SummaryRenderer(ABC):
    @abstractmethod
    def render(self, summary: ReplaySummary) -> str: ...
