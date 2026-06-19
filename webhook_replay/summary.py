from datetime import datetime
from typing import Dict, List, Optional

from .models import ReplayResult, ReplaySummary, WebhookRequest
from .storage import Storage


class SummaryGenerator:
    def __init__(self, storage: Optional[Storage] = None):
        self.storage = storage or Storage()

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

    def get_failed_requests(self, results: List[ReplayResult]) -> List[ReplayResult]:
        return [r for r in results if not r.success]

    def get_successful_requests(self, results: List[ReplayResult]) -> List[ReplayResult]:
        return [r for r in results if r.success]

    def format_text_summary(self, summary: ReplaySummary) -> str:
        lines = [
            "=" * 60,
            "WEBHOOK REPLAY SUMMARY",
            "=" * 60,
            f"Total Requests:    {summary.total_requests}",
            f"Successful:        {summary.success_count}",
            f"Failed:            {summary.failed_count}",
            f"Success Rate:      {summary.success_rate}%",
            f"Total Duration:    {summary.total_duration_ms}ms",
            f"Average Duration:  {summary.average_duration_ms}ms",
            f"Start Time:        {summary.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"End Time:          {summary.end_time.strftime('%Y-%m-%d %H:%M:%S') if summary.end_time else 'N/A'}",
            "=" * 60,
        ]

        if summary.failed_count > 0:
            lines.extend(["", "FAILED REQUESTS:", "-" * 60])
            for req_id, result in summary.results.items():
                if not result.success:
                    lines.append(f"  ID:     {req_id}")
                    lines.append(f"  Status: {result.status_code or 'Error'}")
                    if result.error_message:
                        lines.append(f"  Error:  {result.error_message}")
                    lines.append("")

        return "\n".join(lines)

    def format_json_summary(self, summary: ReplaySummary) -> str:
        import json

        return json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False)

    def get_storage_stats(self) -> Dict[str, int]:
        from .models import WebhookStatus

        return {
            "total": self.storage.count(),
            "pending": self.storage.count(WebhookStatus.PENDING),
            "success": self.storage.count(WebhookStatus.SUCCESS),
            "failed": self.storage.count(WebhookStatus.FAILED),
            "archived": self.storage.count(WebhookStatus.ARCHIVED),
        }
