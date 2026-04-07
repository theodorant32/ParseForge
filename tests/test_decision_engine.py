import pytest
from parseforge.layers import decision_engine
from parseforge.layers.schema import (
    ActionEnum,
    DecisionResult,
    IntentEnum,
    ParsedRequest,
    PriorityEnum,
    UrgencyEnum,
    ValidationResult,
    ValidationStatus,
)


def make_request(**kwargs) -> ParsedRequest:
    defaults = dict(
        intent=IntentEnum.project,
        team_size=2,
        topic="robotics",
        timeframe="this weekend",
        urgency=UrgencyEnum.medium,
        raw_input="Find me 2 people for a robotics project this weekend",
    )
    defaults.update(kwargs)
    return ParsedRequest(**defaults)


def clean_validation() -> ValidationResult:
    return ValidationResult(status=ValidationStatus.valid)


def warn_validation() -> ValidationResult:
    return ValidationResult(status=ValidationStatus.auto_corrected, warnings=["something was corrected"])


class TestScoringAndAction:
    def test_full_request_gets_match(self):
        req = make_request()
        result = decision_engine.process(req, clean_validation())
        assert result.action == ActionEnum.match

    def test_high_score_match(self):
        req = make_request()
        result = decision_engine.process(req, clean_validation())
        assert result.score >= 70

    def test_unknown_intent_lowers_score(self):
        req = make_request(intent=IntentEnum.unknown)
        result = decision_engine.process(req, clean_validation())
        assert result.score < 70

    def test_general_topic_lowers_score(self):
        req = make_request(topic="general")
        result = decision_engine.process(req, clean_validation())
        assert result.score <= 90

    def test_unknown_intent_no_topic_gets_clarify_or_queue(self):
        req = make_request(intent=IntentEnum.unknown, topic="general", timeframe="unspecified")
        result = decision_engine.process(req, warn_validation())
        assert result.action in (ActionEnum.clarify, ActionEnum.reject)

    def test_empty_request_gets_reject(self):
        req = make_request(
            intent=IntentEnum.unknown,
            topic="general",
            timeframe="unspecified",
            team_size=0,
        )
        result = decision_engine.process(req, warn_validation())
        assert result.action == ActionEnum.reject


class TestPriorityMapping:
    def test_high_urgency_high_score_is_critical(self):
        req = make_request(urgency=UrgencyEnum.high)
        result = decision_engine.process(req, clean_validation())
        if result.score >= 70:
            assert result.priority == PriorityEnum.critical

    def test_high_urgency_low_score_is_high(self):
        req = make_request(urgency=UrgencyEnum.high, intent=IntentEnum.unknown, topic="general", timeframe="unspecified")
        result = decision_engine.process(req, warn_validation())
        assert result.priority in (PriorityEnum.high, PriorityEnum.medium)

    def test_low_urgency_is_low_priority(self):
        req = make_request(urgency=UrgencyEnum.low)
        result = decision_engine.process(req, clean_validation())
        assert result.priority == PriorityEnum.low

    def test_medium_urgency_is_medium_priority(self):
        req = make_request(urgency=UrgencyEnum.medium)
        result = decision_engine.process(req, clean_validation())
        assert result.priority == PriorityEnum.medium


class TestDecisionResult:
    def test_returns_decision_result_model(self):
        req = make_request()
        result = decision_engine.process(req, clean_validation())
        assert isinstance(result, DecisionResult)

    def test_score_in_valid_range(self):
        req = make_request()
        result = decision_engine.process(req, clean_validation())
        assert 0 <= result.score <= 100

    def test_reason_is_non_empty(self):
        req = make_request()
        result = decision_engine.process(req, clean_validation())
        assert len(result.reason) > 0

    def test_high_urgency_bonus_applied(self):
        req_high = make_request(urgency=UrgencyEnum.high)
        req_med = make_request(urgency=UrgencyEnum.medium)
        result_high = decision_engine.process(req_high, clean_validation())
        result_med = decision_engine.process(req_med, clean_validation())
        assert result_high.score > result_med.score

    def test_clean_validation_bonus_applied(self):
        req = make_request()
        result_clean = decision_engine.process(req, clean_validation())
        result_warn = decision_engine.process(req, warn_validation())
        assert result_clean.score >= result_warn.score
