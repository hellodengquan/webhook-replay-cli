from ..models import ReplaySummary
from .base import SummaryRenderer


class MarkdownSummaryRenderer(SummaryRenderer):
    def render(self, summary: ReplaySummary) -> str:
        lines = [
            "# Webhook Replay Summary",
            "",
            "## Overview",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Requests | {summary.total_requests} |",
            f"| Successful | {summary.success_count} ✅ |",
            f"| Failed | {summary.failed_count} ❌ |",
            f"| Success Rate | **{summary.success_rate}%** |",
            f"| Total Duration | {summary.total_duration_ms}ms |",
            f"| Average Duration | {summary.average_duration_ms}ms |",
            f"| Start Time | {summary.start_time.strftime('%Y-%m-%d %H:%M:%S')} |",
            f"| End Time | {summary.end_time.strftime('%Y-%m-%d %H:%M:%S') if summary.end_time else 'N/A'} |",
            "",
        ]

        if summary.failed_count > 0:
            lines.extend([
                "## Failed Requests",
                "",
                "| Request ID | Status Code | Error Message | Duration |",
                "|------------|-------------|---------------|----------|",
            ])
            for req_id, result in summary.results.items():
                if not result.success:
                    status = result.status_code or "Error"
                    error = (result.error_message or "N/A").replace("|", "\\|")
                    lines.append(f"| `{req_id}` | {status} | {error} | {result.duration_ms}ms |")
            lines.append("")

        if summary.success_count > 0:
            lines.extend([
                "## Successful Requests",
                "",
                "| Request ID | Status Code | Duration |",
                "|------------|-------------|----------|",
            ])
            for req_id, result in summary.results.items():
                if result.success:
                    lines.append(f"| `{req_id}` | {result.status_code} | {result.duration_ms}ms |")
            lines.append("")

        return "\n".join(lines)
