"""tests/test_orchestrator.py — Integration tests for the full pipeline."""
import json
from pathlib import Path

import pytest
from parseforge.pipeline.orchestrator import PipelineResult, run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
FIXTURES_PATH = Path(__file__).parent / "fixtures" / "inputs.json"


def load_fixtures():
    return json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Core pipeline structure tests
# ---------------------------------------------------------------------------
class TestPipelineStructure:
    def test_returns_pipeline_result(self):
        result = run("Find me 2 people for a robotics project this weekend")
        assert isinstance(result, PipelineResult)

    def test_trace_id_is_set(self):
        result = run("Need help with calculus tomorrow")
        assert result.trace_id != ""
        assert len(result.trace_id) == 12  # hex[:12]

    def test_custom_trace_id_respected(self):
        result = run("Need 2 devs", trace_id="myCustomId")
        assert result.trace_id == "myCustomId"

    def test_stage_list_present(self):
        result = run("Find me 3 engineers for AI project this weekend")
        assert len(result.stages) >= 4  # input, parser, validator, enricher, decision

    def test_stage_names_correct(self):
        result = run("Find me 3 engineers for AI project this weekend")
        names = [s.stage for s in result.stages]
        assert "input" in names
        assert "parser" in names
        assert "validator" in names
        assert "decision_engine" in names

    def test_total_duration_ms_positive(self):
        result = run("Find me 2 people for a robotics project")
        assert result.total_duration_ms > 0

    def test_successful_result_has_decision(self):
        result = run("Find me 2 people for a robotics project this weekend")
        assert result.decision is not None

    def test_successful_result_has_parsed_request(self):
        result = run("Find me 2 people for a robotics project this weekend")
        assert result.parsed_request is not None


# ---------------------------------------------------------------------------
# Happy-path end-to-end tests
# ---------------------------------------------------------------------------
class TestHappyPaths:
    def test_full_project_request(self):
        result = run("Find me 2 people for a robotics project this weekend")
        assert result.success is True
        assert result.decision["action"] in ("match", "queue")

    def test_help_request(self):
        result = run("I need help with calculus tomorrow")
        assert result.success is True

    def test_gig_request(self):
        result = run("Looking for a designer for a quick gig")
        assert result.success is True

    def test_scheduling_request(self):
        result = run("Schedule a team meeting next week")
        assert result.success is True

    def test_urgent_request_gets_high_priority(self):
        result = run("I need 3 developers for a fintech project ASAP")
        assert result.success is True
        assert result.decision["priority"] in ("high", "critical")


# ---------------------------------------------------------------------------
# Error path tests
# ---------------------------------------------------------------------------
class TestErrorPaths:
    def test_empty_input_fails_gracefully(self):
        result = run("")
        assert result.success is False
        assert result.error is not None

    def test_too_short_input_fails_gracefully(self):
        result = run("ab")
        assert result.success is False

    def test_past_timeframe_fails_gracefully(self):
        result = run("Need a developer for a project yesterday")
        assert result.success is False

    def test_none_like_empty_string(self):
        result = run("  ")  # whitespace only
        assert result.success is False


# ---------------------------------------------------------------------------
# Auto-correction tests
# ---------------------------------------------------------------------------
class TestAutoCorrections:
    def test_zero_team_size_auto_corrected(self):
        result = run("Find me 0 people for a project this weekend")
        assert result.success is True
        assert result.parsed_request["team_size"] >= 1

    def test_over_100_team_size_clamped(self):
        result = run("I need 500 people for a software project tomorrow")
        assert result.success is True
        assert result.parsed_request["team_size"] == 100


# ---------------------------------------------------------------------------
# Skip enrichment flag
# ---------------------------------------------------------------------------
class TestSkipEnrichment:
    def test_skip_enrichment_still_succeeds(self):
        result = run("Find me 2 developers for AI this weekend", skip_enrichment=True)
        assert result.success is True

    def test_skip_enrichment_stage_shows_skipped(self):
        result = run("Find me 2 developers for AI this weekend", skip_enrichment=True)
        enricher_stage = next((s for s in result.stages if s.stage == "enricher"), None)
        assert enricher_stage is not None
        assert enricher_stage.status == "skipped"

    def test_enrichment_enabled_adds_request_id(self):
        result = run("Find me 2 developers for AI this weekend", skip_enrichment=False)
        assert result.parsed_request.get("request_id", "") != ""


# ---------------------------------------------------------------------------
# Batch fixture integration test
# ---------------------------------------------------------------------------
class TestFixtureBatch:
    """Run all 25 fixture inputs and check expected outcomes."""

    def _run_fixture(self, case: dict) -> tuple[PipelineResult, str | None, str | None]:
        text = case.get("input", "")
        expected_action = case.get("expected_action")
        expected_status = case.get("expected_status")
        result = run(text)
        return result, expected_action, expected_status

    def test_all_fixtures_run_without_crash(self):
        """Every fixture must complete without raising an unhandled exception."""
        cases = load_fixtures()
        for case in cases:
            result, _, _ = self._run_fixture(case)
            assert isinstance(result, PipelineResult), f"Expected PipelineResult for: {case['input']!r}"

    def test_fixture_success_rate_above_threshold(self):
        """At least 70% of fixture inputs should succeed (decision made)."""
        cases = load_fixtures()
        # Exclude known-invalid inputs (empty, too short, past timeframe)
        runnable = [c for c in cases if len(c.get("input", "").strip()) >= 3]
        successes = sum(1 for c in runnable if run(c["input"]).success)
        rate = successes / len(runnable)
        assert rate >= 0.70, f"Success rate {rate:.0%} is below 70% threshold"

    def test_happy_path_fixtures_match(self):
        """All fixtures marked 'match' should produce action=match or queue."""
        cases = load_fixtures()
        match_cases = [c for c in cases if c.get("expected_action") == "match"]
        for case in match_cases:
            result = run(case["input"])
            action = result.decision["action"] if result.decision else "error"
            assert action in ("match", "queue"), (
                f"Expected match/queue for: {case['input']!r}\n"
                f"  Got: {action}\n"
                f"  Description: {case.get('description', '?')}"
            )

    def test_rejection_fixtures(self):
        """Fixtures marked 'reject' or 'invalid' should not succeed."""
        cases = load_fixtures()
        reject_cases = [c for c in cases if c.get("expected_action") == "reject"]
        for case in reject_cases:
            result = run(case["input"])
            assert not result.success, (
                f"Expected failure for: {case['input']!r}\n"
                f"  Description: {case.get('description', '?')}"
            )

    def test_print_batch_summary(self, capsys):
        """Print a human-readable summary of all fixture results (informational)."""
        cases = load_fixtures()
        passed = failed = 0
        lines = ["\n  === Fixture Batch Summary ==="]
        for i, case in enumerate(cases, 1):
            text = case.get("input", "")
            expected = case.get("expected_action", "?")
            result = run(text)
            action = result.decision["action"] if result.decision else "error"
            ok = "✅" if result.success else "❌"
            match = "✓" if action == expected else f"✗(exp:{expected})"
            lines.append(f"  [{i:02d}] {ok} {action.upper():8s} {match:12s} | {text[:50]}")
            if result.success:
                passed += 1
            else:
                failed += 1
        lines.append(f"\n  Total: {len(cases)} | Passed: {passed} | Failed: {failed}")
        lines.append(f"  Success rate: {passed / len(cases):.0%}")
        print("\n".join(lines))
