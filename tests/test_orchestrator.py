import json
from pathlib import Path

import pytest
from parseforge.pipeline.orchestrator import PipelineResult, run


FIXTURES_PATH = Path(__file__).parent / "fixtures" / "inputs.json"


def load_fixtures():
    return json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))


class TestPipelineStructure:
    def test_returns_pipeline_result(self):
        result = run("Find me 2 people for a robotics project this weekend")
        assert isinstance(result, PipelineResult)

    def test_trace_id_is_set(self):
        result = run("Need help with calculus tomorrow")
        assert result.trace_id != ""
        assert len(result.trace_id) == 12

    def test_custom_trace_id_respected(self):
        result = run("Need 2 devs", trace_id="myCustomId")
        assert result.trace_id == "myCustomId"

    def test_stage_list_present(self):
        result = run("Find me 3 engineers for AI project this weekend")
        assert len(result.stages) >= 4

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
        result = run("  ")
        assert result.success is False


class TestAutoCorrections:
    def test_zero_team_size_auto_corrected(self):
        result = run("Find me 0 people for a project this weekend")
        assert result.success is True
        assert result.parsed_request["team_size"] >= 1

    def test_over_100_team_size_clamped(self):
        result = run("I need 500 people for a software project tomorrow")
        assert result.success is True
        assert result.parsed_request["team_size"] == 100


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


class TestFixtureBatch:
    def _run_fixture(self, case: dict) -> tuple[PipelineResult, str | None, str | None]:
        text = case.get("input", "")
        expected_action = case.get("expected_action")
        expected_status = case.get("expected_status")
        result = run(text)
        return result, expected_action, expected_status

    def test_all_fixtures_run_without_crash(self):
        cases = load_fixtures()
        for case in cases:
            result, _, _ = self._run_fixture(case)
            assert isinstance(result, PipelineResult)

    def test_fixture_success_rate_above_threshold(self):
        cases = load_fixtures()
        runnable = [c for c in cases if len(c.get("input", "").strip()) >= 3]
        successes = sum(1 for c in runnable if run(c["input"]).success)
        rate = successes / len(runnable)
        assert rate >= 0.70

    def test_happy_path_fixtures_match(self):
        cases = load_fixtures()
        match_cases = [c for c in cases if c.get("expected_action") == "match"]
        for case in match_cases:
            result = run(case["input"])
            action = result.decision["action"] if result.decision else "error"
            assert action in ("match", "queue")

    def test_rejection_fixtures(self):
        cases = load_fixtures()
        reject_cases = [c for c in cases if c.get("expected_action") == "reject"]
        for case in reject_cases:
            result = run(case["input"])
            assert not result.success

    def test_print_batch_summary(self, capsys):
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
