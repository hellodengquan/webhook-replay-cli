from ..models import ReplaySummary
from .base import SummaryRenderer


class TextSummaryRenderer(SummaryRenderer):
    def render(self, summary: ReplaySummary) -> str:
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

        if summary.success_count > 0:
            lines.extend(["SUCCESSFUL REQUESTS:", "-" * 60])
            for req_id, result in summary.results.items():
                if result.success:
                    lines.append(f"  ID:     {req_id}")
                    lines.append(f"  Status: {result.status_code}")
                    lines.append(f"  Duration: {result.duration_ms}ms")
                    lines.append("")

        return "\n".join(lines)
