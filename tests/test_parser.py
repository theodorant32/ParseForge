"""tests/test_parser.py — Unit tests for the parsing layer."""
import pytest
from parseforge.layers import parser
from parseforge.layers.schema import IntentEnum, UrgencyEnum


def parse(text: str):
    return parser.process(text)


class TestIntentExtraction:
    def test_project_intent(self):
        r = parse("Find me 2 people for a robotics project this weekend")
        assert r.intent == IntentEnum.project

    def test_help_intent(self):
        r = parse("I need help with calculus tomorrow")
        assert r.intent == IntentEnum.help

    def test_gig_intent(self):
        r = parse("Looking for a designer for a quick gig")
        assert r.intent == IntentEnum.gig

    def test_scheduling_intent(self):
        r = parse("Schedule a meeting for Monday")
        assert r.intent == IntentEnum.scheduling

    def test_unknown_intent_fallback(self):
        r = parse("hello world random text")
        # No hard assert on unknown — just confirm it doesn't crash
        assert r.intent is not None

    def test_task_intent(self):
        r = parse("I need someone to complete this task today")
        assert r.intent in (IntentEnum.task, IntentEnum.help)


class TestTeamSizeExtraction:
    def test_numeric_team_size(self):
        r = parse("Find me 2 people for robotics")
        assert r.team_size == 2

    def test_word_team_size(self):
        r = parse("I need three developers")
        assert r.team_size == 3

    def test_team_of_pattern(self):
        r = parse("Build a team of 5 for the project")
        assert r.team_size == 5

    def test_no_team_size_defaults(self):
        r = parse("I need help with calculus")
        assert r.team_size >= 0  # 0 means unspecified, validator fixes it

    def test_need_n_pattern(self):
        r = parse("I need 4 engineers this weekend")
        assert r.team_size == 4

    def test_team_size_clamped_over_100(self):
        r = parse("Find me 500 people for a project")
        assert r.team_size == 100


class TestTimeframeExtraction:
    def test_this_weekend(self):
        r = parse("robotics project this weekend")
        assert "weekend" in r.timeframe.lower()

    def test_tomorrow(self):
        r = parse("I need help with math tomorrow")
        assert r.timeframe == "tomorrow"

    def test_asap(self):
        r = parse("I need a developer ASAP")
        assert r.timeframe == "ASAP"

    def test_next_week(self):
        r = parse("Available developers next week")
        assert r.timeframe == "next week"

    def test_today(self):
        r = parse("Need a designer today")
        assert r.timeframe == "today"

    def test_no_timeframe_defaults(self):
        r = parse("Looking for a gig designer")
        assert r.timeframe == "unspecified"


class TestTopicExtraction:
    def test_robotics_topic(self):
        r = parse("Find me 2 people for a robotics project")
        assert "robotics" in r.topic.lower()

    def test_calculus_topic(self):
        r = parse("I need help with calculus")
        assert "calculus" in r.topic.lower()

    def test_default_topic_when_vague(self):
        r = parse("I need some help please")
        # Should be general or a reasonable guess
        assert r.topic is not None


class TestUrgencyExtraction:
    def test_asap_urgency(self):
        r = parse("I need a developer ASAP")
        assert r.urgency == UrgencyEnum.high

    def test_urgent_keyword(self):
        r = parse("Urgent: need 2 developers now")
        assert r.urgency == UrgencyEnum.high

    def test_no_rush_urgency(self):
        r = parse("looking for a designer, no rush")
        assert r.urgency == UrgencyEnum.low

    def test_default_medium_urgency(self):
        r = parse("Looking for a designer this weekend")
        assert r.urgency == UrgencyEnum.medium


class TestParserMetadata:
    def test_parse_method_rule_based(self):
        r = parse("Need 2 devs for a project this weekend")
        assert r.parse_method == "rule_based"

    def test_confidence_nonzero_for_good_input(self):
        r = parse("Find me 3 engineers for a machine learning project ASAP")
        assert r.parse_confidence > 0.0

    def test_raw_input_preserved(self):
        text = "Find me 2 people for a robotics project"
        r = parse(text)
        assert r.raw_input == text
