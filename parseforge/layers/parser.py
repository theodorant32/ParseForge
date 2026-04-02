"""
parseforge/layers/parser.py

Parsing Layer — converts raw text into structured fields.

Two strategies:
  1. RuleBasedParser  — regex + keyword matching (always available, no deps)
  2. LLMParser        — pluggable stub; activated when OPENAI_API_KEY is set

The top-level `process()` function tries the best available parser first
and falls back gracefully if it fails.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from parseforge.layers.schema import IntentEnum, ParsedRequest, UrgencyEnum
from parseforge.utils.errors import ParseError
from parseforge.utils.logger import get_logger, set_stage

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Keyword maps
# ---------------------------------------------------------------------------

INTENT_KEYWORDS: dict[str, list[str]] = {
    IntentEnum.gig: [
        "gig", "freelance", "contract", "quick job", "one-time",
        "short-term", "hired", "hire", "paid",
    ],
    IntentEnum.project: [
        "project", "build", "create", "develop", "team", "collaborate",
        "work on", "startup", "hackathon",
        # NOTE: domain subjects like "robotics" intentionally omitted here
        # so they survive topic extraction
    ],
    IntentEnum.help: [
        "help", "assist", "tutor", "learn", "study", "understand",
        "explain", "guide", "support", "homework",
        # NOTE: subject names (calculus, math, physics) intentionally omitted
        # so they survive topic extraction
    ],
    IntentEnum.task: [
        "task", "do", "complete", "finish", "assignment", "errand",
        "need someone", "need a person",
    ],
    IntentEnum.scheduling: [
        "schedule", "meeting", "appointment", "book", "calendar",
        "slot", "available", "availability", "plan",
    ],
}

# Subject-area keywords used ONLY for intent classification (not stripped from topics)
INTENT_SUBJECT_HINTS: dict[str, list[str]] = {
    IntentEnum.project:  ["robotics", "blockchain", "hackathon", "startup", "app", "web"],
    IntentEnum.help:     ["calculus", "math", "physics", "chemistry", "biology", "algebra",
                          "statistics", "economics", "history", "literature", "coding"],
}

TIMEFRAME_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\btoday\b", re.I), "today"),
    (re.compile(r"\btonight\b", re.I), "tonight"),
    (re.compile(r"\btomorrow\b", re.I), "tomorrow"),
    (re.compile(r"\bthis\s+week(?:end)?\b", re.I), "this weekend"),
    (re.compile(r"\bweekend\b", re.I), "this weekend"),
    (re.compile(r"\bnext\s+week\b", re.I), "next week"),
    (re.compile(r"\bnext\s+month\b", re.I), "next month"),
    (re.compile(r"\basap\b|as soon as possible", re.I), "ASAP"),
    (re.compile(r"\burgent(?:ly)?\b", re.I), "ASAP"),
    (re.compile(r"\bright\s+now\b", re.I), "ASAP"),
    (re.compile(r"\bthis\s+month\b", re.I), "this month"),
    (re.compile(r"\bin\s+(\d+)\s+days?\b", re.I), "in {1} days"),
    (re.compile(r"\bin\s+(\d+)\s+hours?\b", re.I), "in {1} hours"),
    (re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I), "{1}"),
]

TEAM_SIZE_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(\d+)\s+(?:people|persons?|members?|devs?|designers?|engineers?|guys?|teammates?)\b", re.I),
    re.compile(r"\ba\s+team\s+of\s+(\d+)\b", re.I),
    re.compile(r"\bteam\s+of\s+(\d+)\b", re.I),
    re.compile(r"\b(\d+)\s+(?:co-?founders?|partners?|collaborators?)\b", re.I),
    re.compile(r"\bfind\s+(?:me\s+)?(\d+)\b", re.I),
    re.compile(r"\bneed\s+(\d+)\b", re.I),
    re.compile(r"\b(\d+)\s+(?:more\s+)?(?:people|person)\b", re.I),
]

WORD_TEAM_SIZE: dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "a partner": 1, "partner": 1, "solo": 1, "alone": 1,
}

# Common words to strip when extracting topics
STOPWORDS = {
    "i", "me", "my", "we", "our", "the", "a", "an", "for", "to", "find",
    "need", "help", "want", "get", "with", "someone", "people", "person",
    "looking", "quick", "gig", "project", "task", "this", "next", "weekend",
    "today", "tomorrow", "asap", "urgent", "urgently", "team", "member",
    "am", "is", "can", "could", "would", "please", "now", "just", "very",
    "some", "any", "do", "have", "has", "be", "been", "it", "in", "on",
    "at", "of", "and", "or", "but", "so", "if", "as", "up",
    # Conversational / junk input filters
    "hi", "hello", "hey", "what", "whats", "how", "who", "why", "where",
    "when", "name", "thanks", "thank", "you", "your", "yours",
}


# ---------------------------------------------------------------------------
# Parsed raw result (before schema)
# ---------------------------------------------------------------------------
@dataclass
class RawParsed:
    intent: str = IntentEnum.unknown
    team_size: int = 0
    topic: str = "general"
    timeframe: str = "unspecified"
    urgency: str = UrgencyEnum.medium
    confidence: float = 0.0
    method: str = "rule_based"
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rule-based parser
# ---------------------------------------------------------------------------
class RuleBasedParser:
    """Pure regex + keyword parser — zero external dependencies."""

    def parse(self, text: str) -> RawParsed:
        result = RawParsed()
        score = 0

        # 1. Intent
        intent, intent_score = self._extract_intent(text)
        result.intent = intent
        score += intent_score

        # 2. Team size
        team_size, size_score = self._extract_team_size(text)
        result.team_size = team_size
        score += size_score

        # 3. Timeframe
        timeframe, time_score = self._extract_timeframe(text)
        result.timeframe = timeframe
        score += time_score

        # 4. Topic
        topic, topic_score = self._extract_topic(text, intent)
        result.topic = topic
        score += topic_score

        # 5. Urgency (pre-enrichment rough cut)
        result.urgency = self._extract_urgency(text, timeframe)

        # Normalise confidence to [0, 1]
        result.confidence = min(score / 100.0, 1.0)
        result.method = "rule_based"
        return result

    # ------------------------------------------------------------------
    def _extract_intent(self, text: str) -> tuple[str, int]:
        text_lower = text.lower()
        scores: dict[str, int] = {}
        for intent, keywords in INTENT_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in text_lower)
            # Also count subject hints (lower weight)
            subject_hints = INTENT_SUBJECT_HINTS.get(intent, [])
            hint_hits = sum(1 for kw in subject_hints if kw in text_lower)
            total_hits = hits + hint_hits
            if total_hits:
                scores[intent] = total_hits

        if not scores:
            return IntentEnum.unknown, 0

        best = max(scores, key=lambda k: scores[k])
        return best, min(scores[best] * 15, 40)

    def _extract_team_size(self, text: str) -> tuple[int, int]:
        # Numeric patterns
        for pattern in TEAM_SIZE_PATTERNS:
            match = pattern.search(text)
            if match:
                try:
                    return int(match.group(1)), 20
                except (IndexError, ValueError):
                    pass

        # Word-based
        text_lower = text.lower()
        for word, size in WORD_TEAM_SIZE.items():
            if re.search(rf"\b{re.escape(word)}\b", text_lower):
                return size, 15

        return 0, 0  # 0 means unspecified

    def _extract_timeframe(self, text: str) -> tuple[str, int]:
        for pattern, label in TIMEFRAME_PATTERNS:
            match = pattern.search(text)
            if match:
                # Handle capture groups (e.g. "in 3 days")
                try:
                    resolved = label.format(*match.groups())
                except (IndexError, KeyError):
                    resolved = label
                return resolved, 20
        return "unspecified", 0

    def _extract_topic(self, text: str, intent: str) -> tuple[str, int]:
        """
        Topic extraction strategy:
        1. Check if any known subject-hint words appear in text → use as topic
        2. Fall back to frequency-filtered noun candidates after removing stopwords
        """
        text_lower = text.lower()

        # Priority 1: explicit subject-hint match (most reliable)
        for subject_words in INTENT_SUBJECT_HINTS.values():
            for word in subject_words:
                if re.search(rf"\b{re.escape(word)}\b", text_lower):
                    return word, 15

        # Priority 2: frequency-based noun extraction
        # Only strip generic intent trigger words, NOT subject nouns
        intent_trigger_words = set(
            w for kws in INTENT_KEYWORDS.values() for kw in kws for w in kw.split()
        )
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text_lower)
        candidates = [
            w for w in words
            if w not in STOPWORDS and w not in intent_trigger_words
        ]

        if not candidates:
            return "general", 0

        from collections import Counter
        freq = Counter(candidates)
        topic = freq.most_common(1)[0][0]
        return topic, 15

    def _extract_urgency(self, text: str, timeframe: str) -> str:
        text_lower = text.lower()
        high_signals = ["asap", "urgent", "right now", "immediately", "critical", "emergency"]
        low_signals = ["eventually", "whenever", "no rush", "someday", "leisure", "flexible"]

        if any(s in text_lower for s in high_signals) or timeframe.upper() == "ASAP":
            return UrgencyEnum.high
        if any(s in text_lower for s in low_signals):
            return UrgencyEnum.low
        return UrgencyEnum.medium


# ---------------------------------------------------------------------------
# LLM Parser stub (activated via OPENAI_API_KEY env var)
# ---------------------------------------------------------------------------
class LLMParser:
    """
    Pluggable LLM-based parser.
    Currently a stub — implement `_call_llm()` to connect to a real provider.
    Activated when OPENAI_API_KEY is set in the environment.
    """

    SYSTEM_PROMPT = (
        "You are a structured data extractor. Given a user's free-form text request, "
        "extract the following fields and return ONLY valid JSON:\n"
        '  "intent": one of [task, gig, help, project, scheduling, unknown]\n'
        '  "team_size": integer (0 if unspecified)\n'
        '  "topic": string (main subject)\n'
        '  "timeframe": string (when it\'s needed)\n'
        '  "urgency": one of [low, medium, high]\n'
        "Do NOT include any explanation or markdown — raw JSON only."
    )

    def parse(self, text: str) -> RawParsed:
        import json

        try:
            raw_json = self._call_llm(text)
            data = json.loads(raw_json)
            return RawParsed(
                intent=data.get("intent", IntentEnum.unknown),
                team_size=int(data.get("team_size", 0)),
                topic=data.get("topic", "general"),
                timeframe=data.get("timeframe", "unspecified"),
                urgency=data.get("urgency", UrgencyEnum.medium),
                confidence=0.9,
                method="llm",
            )
        except Exception as exc:
            logger.warning("llm_parse_failed", error=str(exc), fallback="rule_based")
            raise ParseError(f"LLM parsing failed: {exc}") from exc

    def _call_llm(self, text: str) -> str:  # noqa: ARG002
        """
        Override this method to connect to a real LLM provider.

        Example (OpenAI):
            import openai
            client = openai.OpenAI()
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
            )
            return resp.choices[0].message.content
        """
        raise NotImplementedError(
            "LLMParser._call_llm() is a stub. "
            "Set OPENAI_API_KEY and implement this method to enable LLM parsing."
        )


# ---------------------------------------------------------------------------
# ML Parser (Local Scikit-Learn Mode)
# ---------------------------------------------------------------------------
class MLParser(RuleBasedParser):
    """
    Local Machine Learning parser using Semantic Embeddings (SentenceTransformers)
    and Scikit-Learn.
    """
    def __init__(self):
        try:
            import joblib
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError("sentence-transformers not installed. Run: pip install sentence-transformers")
            
        from pathlib import Path
        model_path = Path("data/intent_model.pkl")
        if not model_path.exists():
            raise FileNotFoundError("ML model not trained. Run python train.py")
            
        self.classifier = joblib.load(model_path)
        # Load the embedder (caches automatically)
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")

    def parse(self, text: str) -> RawParsed:
        result = RawParsed()
        
        # 1. Embed text into semantic vector and predict Intent
        embedding = self.embedder.encode([text])
        probas = self.classifier.predict_proba(embedding)[0]
        classes = self.classifier.classes_
        best_idx = probas.argmax()
        
        result.intent = classes[best_idx]
        confidence = float(probas[best_idx])
        
        # 2. Extract specific entities using existing robust regex rules
        team_size, _ = self._extract_team_size(text)
        result.team_size = team_size

        timeframe, _ = self._extract_timeframe(text)
        result.timeframe = timeframe

        topic, _ = self._extract_topic(text, result.intent)
        result.topic = topic

        result.urgency = self._extract_urgency(text, timeframe)

        # Let's say ML intent governs the confidence level
        result.confidence = confidence
        result.method = "local_ml"
        
        return result


_ML_PARSER_INSTANCE: MLParser | None = None

def get_ml_parser() -> MLParser | None:
    global _ML_PARSER_INSTANCE
    from pathlib import Path
    if _ML_PARSER_INSTANCE is None and Path("data/intent_model.pkl").exists():
        try:
            _ML_PARSER_INSTANCE = MLParser()
        except Exception:
            return None
    return _ML_PARSER_INSTANCE

# ---------------------------------------------------------------------------
# Public process() function
# ---------------------------------------------------------------------------
def process(text: str) -> ParsedRequest:
    """
    Parse raw text into a ParsedRequest.
    Tries Local ML first, then LLM (if available), falls back to rule-based, then fallback defaults.
    """
    set_stage("parser")
    logger.info("parser_start", input_length=len(text))

    raw: RawParsed | None = None

    # Try Local ML first if model exists
    ml_parser = get_ml_parser()
    if ml_parser:
        try:
            logger.debug("attempting_ml_parse")
            raw = ml_parser.parse(text)
        except Exception as exc:
            logger.warning("ml_parse_failed", error=str(exc))

    # Try LLM if API key present and ML didn't fire
    if raw is None and os.getenv("OPENAI_API_KEY"):
        try:
            logger.debug("attempting_llm_parse")
            raw = LLMParser().parse(text)
        except (ParseError, NotImplementedError):
            logger.warning("llm_unavailable_falling_back_to_rule_based")

    # Fall back to rule-based
    if raw is None:
        try:
            raw = RuleBasedParser().parse(text)
        except Exception as exc:
            logger.error("rule_based_parse_failed", error=str(exc))
            raw = None

    # Ultimate fallback: zero-confidence defaults
    if raw is None or raw.confidence == 0.0:
        logger.warning(
            "parse_zero_confidence",
            reason="no fields extracted — using fallback defaults",
        )
        raw = RawParsed(
            intent=IntentEnum.unknown,
            confidence=0.0,
            method="fallback",
            warnings=["Parser could not extract any meaningful fields."],
        )

    logger.info(
        "parser_complete",
        intent=raw.intent,
        team_size=raw.team_size,
        topic=raw.topic,
        timeframe=raw.timeframe,
        confidence=raw.confidence,
        method=raw.method,
    )

    # Build Pydantic model (handles type coercion + defaults)
    return ParsedRequest(
        intent=raw.intent,
        team_size=raw.team_size,
        topic=raw.topic,
        timeframe=raw.timeframe,
        urgency=raw.urgency,
        raw_input=text,
        parse_confidence=raw.confidence,
        parse_method=raw.method,
    )
