"""Tests for the shared domain-operation engine in cli/_processing.py."""

import json
import time
from typing import Any, Dict

import pytest

from mimeo.cli._processing import _categorize_error, exit_on_errors, map_items, render_results
from mimeo.exceptions import (
    EXIT_AUTH,
    EXIT_GENERAL,
    EXIT_PARTIAL,
    EXIT_RATE_LIMIT,
    EXIT_TRANSIENT,
    HostError,
    RegistrarError,
)


class TestCategorizeError:
    """Structured status codes decide; message keywords are fallback only."""

    def test_host_error_429_is_rate_limit(self) -> None:
        assert _categorize_error(HostError("gh: rate limit (HTTP 429)", status_code=429)) == (
            EXIT_RATE_LIMIT,
            "rate-limit",
        )

    def test_host_error_5xx_is_transient(self) -> None:
        assert _categorize_error(HostError("gh: Server Error (HTTP 502)", status_code=502)) == (
            EXIT_TRANSIENT,
            "transient",
        )

    def test_host_error_401_is_auth(self) -> None:
        assert _categorize_error(HostError("gh: Bad credentials (HTTP 401)", status_code=401)) == (
            EXIT_AUTH,
            "auth",
        )

    def test_host_error_400_is_general_provider(self) -> None:
        assert _categorize_error(HostError("gh: Invalid cname (HTTP 400)", status_code=400)) == (
            EXIT_GENERAL,
            "provider",
        )

    def test_host_error_without_code_uses_keywords(self) -> None:
        assert _categorize_error(HostError("connection refused")) == (EXIT_TRANSIENT, "transient")

    def test_host_error_without_code_unmatched_is_general(self) -> None:
        assert _categorize_error(HostError("GitHub CLI (gh) is not installed")) == (
            EXIT_GENERAL,
            "provider",
        )

    def test_registrar_error_keyword_fallback(self) -> None:
        assert _categorize_error(RegistrarError("Invalid API key")) == (EXIT_AUTH, "auth")

    def test_unexpected_exception_is_general_error(self) -> None:
        assert _categorize_error(KeyError("field")) == (EXIT_GENERAL, "error")


class TestMapItems:
    def test_preserves_input_order(self) -> None:
        """Results come back in input order even when completion order differs."""
        items = list(range(8))

        def fn(i: int) -> Dict[str, Any]:
            # Later items finish first
            time.sleep((8 - i) * 0.005)
            return {"item": i}

        results = map_items(items, fn, workers=8)
        assert [r["item"] for r in results] == items

    def test_sequential(self) -> None:
        results = map_items(["a", "b", "c"], lambda s: {"item": s}, sequential=True)
        assert [r["item"] for r in results] == ["a", "b", "c"]

    def test_single_item_runs_sequentially(self) -> None:
        results = map_items(["only"], lambda s: {"item": s})
        assert results == [{"item": "only"}]

    def test_empty_items(self) -> None:
        assert map_items([], lambda s: {"item": s}) == []

    def test_exception_becomes_error_row(self) -> None:
        def fn(i: int) -> Dict[str, Any]:
            if i == 1:
                raise ValueError("boom")
            return {"item": i, "error": None}

        results = map_items([0, 1, 2], fn, workers=3)
        assert results[0] == {"item": 0, "error": None}
        assert results[1]["error"] == "boom"
        assert "error_category" in results[1]
        assert results[2] == {"item": 2, "error": None}

    def test_on_error_builds_custom_row(self) -> None:
        def fn(s: str) -> Dict[str, Any]:
            raise RuntimeError("nope")

        results = map_items(
            ["x"],
            fn,
            on_error=lambda item, exc: {"item": item, "error": str(exc), "custom": True},
        )
        assert results == [{"item": "x", "error": "nope", "custom": True}]


class TestRenderResults:
    RESULTS = [
        {"domain": "a.com", "value": 1, "extra": "ignored"},
        {"domain": "b.com", "value": 2, "extra": "ignored"},
    ]

    def test_json(self, capsys: pytest.CaptureFixture) -> None:
        render_results(
            self.RESULTS, "json", csv_fields=["domain", "value"], text=lambda rows: None
        )
        data = json.loads(capsys.readouterr().out)
        assert data == self.RESULTS

    def test_csv_default_rows(self, capsys: pytest.CaptureFixture) -> None:
        render_results(
            self.RESULTS, "csv", csv_fields=["domain", "value"], text=lambda rows: None
        )
        lines = capsys.readouterr().out.strip().splitlines()
        assert lines == ["domain,value", "a.com,1", "b.com,2"]

    def test_csv_rows_expansion(self, capsys: pytest.CaptureFixture) -> None:
        def expand(result: Dict[str, Any]) -> list[Dict[str, Any]]:
            return [
                {"domain": result["domain"], "n": n} for n in range(result["value"])
            ]

        render_results(
            self.RESULTS,
            "csv",
            csv_fields=["domain", "n"],
            csv_rows=expand,
            text=lambda rows: None,
        )
        lines = capsys.readouterr().out.strip().splitlines()
        assert lines == ["domain,n", "a.com,0", "b.com,0", "b.com,1"]

    def test_csv_empty_results_writes_header(self, capsys: pytest.CaptureFixture) -> None:
        render_results([], "csv", csv_fields=["domain", "value"], text=lambda rows: None)
        assert capsys.readouterr().out.strip() == "domain,value"

    def test_text_uses_callback(self, capsys: pytest.CaptureFixture) -> None:
        seen: list = []
        render_results(
            self.RESULTS, "text", csv_fields=["domain"], text=lambda rows: seen.append(rows)
        )
        assert seen == [self.RESULTS]
        assert capsys.readouterr().out == ""


class TestExitOnErrors:
    def test_no_errors_is_noop(self) -> None:
        exit_on_errors([{"domain": "a.com", "error": None}])

    def test_partial_failure_exits_partial(self, capsys: pytest.CaptureFixture) -> None:
        results = [
            {"domain": "a.com", "error": None},
            {"domain": "b.com", "error": "boom", "error_category": "transient"},
        ]
        with pytest.raises(SystemExit) as exc_info:
            exit_on_errors(results)
        assert exc_info.value.code == EXIT_PARTIAL
        captured = capsys.readouterr()
        assert captured.err.strip() == "1 of 2 domains failed"
        assert "boom" not in captured.err

    def test_total_failure_exits_by_category(self, capsys: pytest.CaptureFixture) -> None:
        results = [
            {"domain": "a.com", "error": "boom", "error_category": "transient"},
            {"domain": "b.com", "error": "boom", "error_category": "provider"},
        ]
        with pytest.raises(SystemExit) as exc_info:
            exit_on_errors(results)
        # provider errors are EXIT_GENERAL (1), transient is EXIT_TRANSIENT (5);
        # min() picks the more definitive failure
        assert exc_info.value.code == EXIT_GENERAL
        captured = capsys.readouterr()
        assert captured.err.strip() == "2 of 2 domains failed"
        assert "boom" not in captured.err
