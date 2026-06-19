import json

import pytest

from webhook_replay.summary_renderers import (
    JsonSummaryRenderer,
    MarkdownSummaryRenderer,
    SummaryFormat,
    SummaryGenerator,
    get_summary_renderer,
)
from webhook_replay.summary_renderers.base import SummaryRenderer


class TestGetSummaryRenderer:
    def test_json_format_returns_json_renderer(self):
        renderer = get_summary_renderer(SummaryFormat.JSON)
        assert isinstance(renderer, JsonSummaryRenderer)

    def test_markdown_format_returns_markdown_renderer(self):
        renderer = get_summary_renderer(SummaryFormat.MARKDOWN)
        assert isinstance(renderer, MarkdownSummaryRenderer)

    def test_string_format_json(self):
        renderer = get_summary_renderer("json")
        assert isinstance(renderer, JsonSummaryRenderer)

    def test_string_format_markdown(self):
        renderer = get_summary_renderer("markdown")
        assert isinstance(renderer, MarkdownSummaryRenderer)

    def test_unsupported_format_raises(self):
        with pytest.raises(ValueError):
            get_summary_renderer("xml")


class TestJsonRendererOutput:
    @pytest.fixture
    def renderer(self) -> JsonSummaryRenderer:
        return JsonSummaryRenderer()

    def test_renders_valid_json(self, renderer: JsonSummaryRenderer, sample_summary):
        output = renderer.render(sample_summary)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_json_top_level_keys(self, renderer: JsonSummaryRenderer, sample_summary):
        parsed = json.loads(renderer.render(sample_summary))
        expected_keys = {
            "total_requests",
            "success_count",
            "failed_count",
            "total_duration_ms",
            "average_duration_ms",
            "results",
            "start_time",
            "end_time",
        }
        assert set(parsed.keys()) == expected_keys

    def test_json_numerics(self, renderer: JsonSummaryRenderer, sample_summary):
        parsed = json.loads(renderer.render(sample_summary))
        assert parsed["total_requests"] == 3
        assert parsed["success_count"] == 2
        assert parsed["failed_count"] == 1
        assert parsed["total_duration_ms"] == 726.0
        assert parsed["average_duration_ms"] == 242.0

    def test_json_results_keys(self, renderer: JsonSummaryRenderer, sample_summary):
        parsed = json.loads(renderer.render(sample_summary))
        assert set(parsed["results"].keys()) == {"abc123", "def456", "ghi789"}

    def test_json_success_result_fields(self, renderer: JsonSummaryRenderer, sample_summary):
        parsed = json.loads(renderer.render(sample_summary))
        abc = parsed["results"]["abc123"]
        assert abc["success"] is True
        assert abc["status_code"] == 200
        assert abc["duration_ms"] == 150.5
        assert abc["error_message"] is None

    def test_json_failed_result_fields(self, renderer: JsonSummaryRenderer, sample_summary):
        parsed = json.loads(renderer.render(sample_summary))
        def_r = parsed["results"]["def456"]
        assert def_r["success"] is False
        assert def_r["status_code"] == 500
        assert def_r["error_message"] == "Internal Server Error"
        assert def_r["duration_ms"] == 500.2

    def test_json_empty_summary(self, renderer: JsonSummaryRenderer, empty_summary):
        parsed = json.loads(renderer.render(empty_summary))
        assert parsed["total_requests"] == 0
        assert parsed["success_count"] == 0
        assert parsed["failed_count"] == 0
        assert parsed["results"] == {}

    def test_json_all_failed(self, renderer: JsonSummaryRenderer, all_failed_summary):
        parsed = json.loads(renderer.render(all_failed_summary))
        assert parsed["success_count"] == 0
        assert parsed["failed_count"] == 2
        for _rid, result in parsed["results"].items():
            assert result["success"] is False

    def test_json_all_success(self, renderer: JsonSummaryRenderer, all_success_summary):
        parsed = json.loads(renderer.render(all_success_summary))
        assert parsed["failed_count"] == 0
        assert parsed["success_count"] == 1
        for _rid, result in parsed["results"].items():
            assert result["success"] is True

    def test_json_ensure_ascii_false(self, renderer: JsonSummaryRenderer, sample_summary):
        output = renderer.render(sample_summary)
        assert "Internal Server Error" in output
        assert "\\u" not in output or "Internal" in output

    def test_json_indent(self, renderer: JsonSummaryRenderer, sample_summary):
        output = renderer.render(sample_summary)
        assert "\n" in output
        assert "  " in output


class TestMarkdownRendererOutput:
    @pytest.fixture
    def renderer(self) -> MarkdownSummaryRenderer:
        return MarkdownSummaryRenderer()

    def test_has_main_heading(self, renderer: MarkdownSummaryRenderer, sample_summary):
        output = renderer.render(sample_summary)
        assert "# Webhook Replay Summary" in output

    def test_has_overview_section(self, renderer: MarkdownSummaryRenderer, sample_summary):
        output = renderer.render(sample_summary)
        assert "## Overview" in output

    def test_overview_table_has_all_metrics(self, renderer: MarkdownSummaryRenderer, sample_summary):
        output = renderer.render(sample_summary)
        assert "| Total Requests | 3 |" in output
        assert "| Successful | 2 ✅ |" in output
        assert "| Failed | 1 ❌ |" in output
        assert "| Success Rate | **66.67%** |" in output
        assert "| Total Duration | 726.0ms |" in output
        assert "| Average Duration | 242.0ms |" in output

    def test_overview_table_structure(self, renderer: MarkdownSummaryRenderer, sample_summary):
        output = renderer.render(sample_summary)
        lines = output.split("\n")
        table_header_idx = None
        for i, line in enumerate(lines):
            if line.startswith("| Metric |"):
                table_header_idx = i
                break
        assert table_header_idx is not None
        assert lines[table_header_idx + 1].startswith("|--------")

    def test_has_failed_section_when_failures(self, renderer: MarkdownSummaryRenderer, sample_summary):
        output = renderer.render(sample_summary)
        assert "## Failed Requests" in output
        assert "| Request ID | Status Code | Error Message | Duration |" in output
        assert "|------------|-------------|---------------|----------|" in output

    def test_failed_request_row_content(self, renderer: MarkdownSummaryRenderer, sample_summary):
        output = renderer.render(sample_summary)
        assert "| `def456` | 500 | Internal Server Error | 500.2ms |" in output

    def test_has_success_section(self, renderer: MarkdownSummaryRenderer, sample_summary):
        output = renderer.render(sample_summary)
        assert "## Successful Requests" in output
        assert "| Request ID | Status Code | Duration |" in output

    def test_success_request_rows(self, renderer: MarkdownSummaryRenderer, sample_summary):
        output = renderer.render(sample_summary)
        assert "| `abc123` | 200 | 150.5ms |" in output
        assert "| `ghi789` | 201 | 75.3ms |" in output

    def test_no_failed_section_when_all_success(self, renderer: MarkdownSummaryRenderer, all_success_summary):
        output = renderer.render(all_success_summary)
        assert "## Failed Requests" not in output
        assert "## Successful Requests" in output

    def test_no_success_section_when_all_failed(self, renderer: MarkdownSummaryRenderer, all_failed_summary):
        output = renderer.render(all_failed_summary)
        assert "## Failed Requests" in output
        assert "## Successful Requests" not in output

    def test_empty_summary_still_has_heading(self, renderer: MarkdownSummaryRenderer, empty_summary):
        output = renderer.render(empty_summary)
        assert "# Webhook Replay Summary" in output
        assert "| Total Requests | 0 |" in output
        assert "## Failed Requests" not in output
        assert "## Successful Requests" not in output

    def test_pipe_char_escaped_in_error_message(self, renderer: MarkdownSummaryRenderer):
        from datetime import datetime

        from webhook_replay.models import ReplayResult, ReplaySummary

        summary = ReplaySummary(
            total_requests=1,
            success_count=0,
            failed_count=1,
            total_duration_ms=100.0,
            average_duration_ms=100.0,
            results={
                "pipe001": ReplayResult(
                    request_id="pipe001",
                    success=False,
                    status_code=400,
                    error_message="bad | value | here",
                    duration_ms=100.0,
                ),
            },
            start_time=datetime(2026, 6, 19, 10, 0, 0),
            end_time=datetime(2026, 6, 19, 10, 0, 1),
        )
        output = renderer.render(summary)
        assert "bad \\| value \\| here" in output

    def test_error_shows_error_when_no_status_code(self, renderer: MarkdownSummaryRenderer, all_failed_summary):
        output = renderer.render(all_failed_summary)
        assert "| Error |" in output

    def test_overview_contains_timestamps(self, renderer: MarkdownSummaryRenderer, sample_summary):
        output = renderer.render(sample_summary)
        assert "2026-06-19" in output


class TestSummaryGeneratorIntegration:
    def test_generate_then_render_json(self, sample_summary):
        gen = SummaryGenerator()
        output = gen.render_summary(sample_summary, SummaryFormat.JSON)
        parsed = json.loads(output)
        assert parsed["total_requests"] == 3

    def test_generate_then_render_markdown(self, sample_summary):
        gen = SummaryGenerator()
        output = gen.render_summary(sample_summary, SummaryFormat.MARKDOWN)
        assert "# Webhook Replay Summary" in output
        assert "| Total Requests | 3 |" in output

    def test_format_json_summary_delegates(self, sample_summary):
        gen = SummaryGenerator()
        output = gen.format_json_summary(sample_summary)
        parsed = json.loads(output)
        assert parsed["success_count"] == 2

    def test_format_markdown_summary_delegates(self, sample_summary):
        gen = SummaryGenerator()
        output = gen.format_markdown_summary(sample_summary)
        assert "## Overview" in output

    def test_renderer_base_is_abstract(self):
        with pytest.raises(TypeError):
            SummaryRenderer()
