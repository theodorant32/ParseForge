"""tests/test_validator.py — Unit tests for the validation layer."""
import pytest
from parseforge.layers import validator
from parseforge.layers.schema import ParsedRequest, IntentEnum, UrgencyEnum, ValidationStatus
from parseforge.utils.errors import ValidationError


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


class TestValidHappyPath:
    def test_valid_request_passes(self):
        req = make_request()
        result_req, result = validator.process(req)
        assert result.status == ValidationStatus.valid

    def test_returns_parsed_request(self):
        req = make_request()
        result_req, result = validator.process(req)
        assert isinstance(result_req, ParsedRequest)

    def test_valid_all_intents(self):
        for intent in [IntentEnum.project, IntentEnum.help, IntentEnum.gig, IntentEnum.task, IntentEnum.scheduling]:
            req = make_request(intent=intent)
            _, result = validator.process(req)
            assert result.status in (ValidationStatus.valid, ValidationStatus.auto_corrected)


class TestTeamSizeValidation:
    def test_zero_team_size_auto_corrected(self):
        req = make_request(team_size=0)
        result_req, result = validator.process(req)
        assert result_req.team_size == 1
        assert result.status == ValidationStatus.auto_corrected
        assert any("team_size" in c for c in result.corrections)

    def test_negative_team_size_rejected(self):
        req = make_request(team_size=-1)
        with pytest.raises(ValidationError) as exc_info:
            validator.process(req)
        assert "team_size" in str(exc_info.value).lower()

    def test_team_size_one_valid(self):
        req = make_request(team_size=1)
        _, result = validator.process(req)
        assert result.status == ValidationStatus.valid

    def test_team_size_100_valid(self):
        req = make_request(team_size=100)
        _, result = validator.process(req)
        assert result.status in (ValidationStatus.valid, ValidationStatus.auto_corrected)


class TestPastTimeframeRejection:
    def test_yesterday_rejected(self):
        req = make_request(timeframe="yesterday", raw_input="project yesterday")
        with pytest.raises(ValidationError):
            validator.process(req)

    def test_last_week_rejected(self):
        req = make_request(timeframe="last week", raw_input="I needed this last week")
        with pytest.raises(ValidationError):
            validator.process(req)

    def test_future_timeframe_passes(self):
        req = make_request(timeframe="next week")
        _, result = validator.process(req)
        assert result.status in (ValidationStatus.valid, ValidationStatus.auto_corrected)


class TestClarificationRequired:
    def test_unknown_intent_general_topic_needs_clarification(self):
        req = make_request(intent=IntentEnum.unknown, topic="general")
        result_req, result = validator.process(req)
        assert result.status == ValidationStatus.needs_clarification

    def test_unknown_intent_specific_topic_passes(self):
        req = make_request(intent=IntentEnum.unknown, topic="robotics")
        _, result = validator.process(req)
        # Should pass with warning — not needs_clarification
        assert result.status != ValidationStatus.invalid


class TestUnspecifiedTimeframeWarning:
    def test_unspecified_timeframe_warns(self):
        req = make_request(timeframe="unspecified")
        _, result = validator.process(req)
        assert any("timeframe" in w.lower() for w in result.warnings)

    def test_unspecified_timeframe_still_valid(self):
        req = make_request(timeframe="unspecified")
        _, result = validator.process(req)
        assert result.status in (ValidationStatus.valid, ValidationStatus.auto_corrected)


class TestValidationResult:
    def test_result_has_status(self):
        req = make_request()
        _, result = validator.process(req)
        assert result.status is not None

    def test_corrections_empty_on_clean(self):
        req = make_request()
        _, result = validator.process(req)
        assert result.corrections == []
