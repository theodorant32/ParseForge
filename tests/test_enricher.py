"""tests/test_enricher.py — Unit tests for the enrichment layer."""
import pytest
from parseforge.layers import enricher
from parseforge.layers.schema import IntentEnum, ParsedRequest, UrgencyEnum


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


class TestMetadataEnrichment:
    def test_request_id_added(self):
        req = make_request()
        enriched = enricher.process(req)
        assert enriched.request_id != ""
        assert len(enriched.request_id) == 36  # UUID format

    def test_timestamp_added(self):
        req = make_request()
        enriched = enricher.process(req)
        assert enriched.timestamp != ""
        assert "T" in enriched.timestamp  # ISO 8601

    def test_pipeline_version_set(self):
        req = make_request()
        enriched = enricher.process(req)
        assert enriched.pipeline_version == "1.0.0"

    def test_unique_request_ids(self):
        req = make_request()
        r1 = enricher.process(req)
        r2 = enricher.process(req)
        assert r1.request_id != r2.request_id


class TestUrgencyInference:
    def test_asap_timeframe_makes_high_urgency(self):
        req = make_request(timeframe="ASAP", urgency=UrgencyEnum.medium)
        enriched = enricher.process(req)
        assert enriched.urgency == UrgencyEnum.high

    def test_today_timeframe_makes_high_urgency(self):
        req = make_request(timeframe="today", urgency=UrgencyEnum.medium)
        enriched = enricher.process(req)
        assert enriched.urgency == UrgencyEnum.high

    def test_next_month_makes_low_urgency(self):
        req = make_request(timeframe="next month", urgency=UrgencyEnum.medium)
        enriched = enricher.process(req)
        assert enriched.urgency == UrgencyEnum.low

    def test_next_week_stays_medium(self):
        req = make_request(timeframe="next week", urgency=UrgencyEnum.medium)
        enriched = enricher.process(req)
        assert enriched.urgency == UrgencyEnum.medium

    def test_urgent_keyword_in_raw_makes_high(self):
        req = make_request(raw_input="urgent need 2 devs for project", urgency=UrgencyEnum.medium)
        enriched = enricher.process(req)
        assert enriched.urgency == UrgencyEnum.high

    def test_no_rush_makes_low_urgency(self):
        req = make_request(raw_input="looking for designer no rush", urgency=UrgencyEnum.medium)
        enriched = enricher.process(req)
        assert enriched.urgency == UrgencyEnum.low


class TestTeamSizeInference:
    def test_solo_keyword_infers_team_size_1(self):
        req = make_request(team_size=1, raw_input="I want to work solo on this project")
        enriched = enricher.process(req)
        assert enriched.team_size == 1  # confirmed as 1

    def test_partner_keyword_infers_team_size_2(self):
        req = make_request(team_size=1, raw_input="Looking for a partner for this gig")
        enriched = enricher.process(req)
        assert enriched.team_size == 2

    def test_explicit_team_size_not_overwritten(self):
        req = make_request(team_size=5, raw_input="Find me a partner for my team of 5")
        enriched = enricher.process(req)
        assert enriched.team_size == 5  # explicit value preserved


class TestTimeframeNormalization:
    def test_asap_normalized(self):
        req = make_request(timeframe="asap")
        enriched = enricher.process(req)
        assert enriched.timeframe == "ASAP"

    def test_weekend_normalized(self):
        req = make_request(timeframe="weekend")
        enriched = enricher.process(req)
        assert enriched.timeframe == "this weekend"

    def test_tomorrow_normalized(self):
        req = make_request(timeframe="tomorrow")
        enriched = enricher.process(req)
        assert enriched.timeframe == "tomorrow"

    def test_unknown_timeframe_preserved(self):
        req = make_request(timeframe="some custom time phrase")
        enriched = enricher.process(req)
        assert enriched.timeframe == "some custom time phrase"


class TestEnrichmentNonFatal:
    def test_returns_request_even_if_enrichment_partial(self):
        """Enricher should never crash — always returns a ParsedRequest."""
        req = make_request()
        result = enricher.process(req)
        assert isinstance(result, ParsedRequest)
