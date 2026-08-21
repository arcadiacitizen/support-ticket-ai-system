from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


POLICY_VERSION = "policy-2026-08-21"
CLASSIFIER_VERSION = "rules-v1"
RETRIEVER_VERSION = "lexical-v1"


@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    channel: str
    text: str
    language: str = "ru"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Ticket":
        return cls(
            ticket_id=str(value["ticket_id"]),
            channel=str(value.get("channel", "web")),
            text=str(value["text"]),
            language=str(value.get("language", "ru")),
        )


@dataclass(frozen=True)
class Classification:
    topic: str
    confidence: float
    matched_signals: list[str]


@dataclass(frozen=True)
class RetrievedDocument:
    document_id: str
    title: str
    answer: str
    score: float


@dataclass(frozen=True)
class Decision:
    decision_id: str
    ticket_id: str
    topic: str
    topic_confidence: float
    risk: str
    risk_reasons: list[str]
    pii_types: dict[str, int]
    retrieved_document_id: str | None
    retrieval_score: float
    action: str
    route: str
    auto_send: bool
    draft: str | None
    fallback_reason: str | None
    versions: dict[str, str]
    decided_at: str
    latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"\s+", " ", normalized).strip()


class PiiRedactor:
    """Small demonstrator. Production uses a reviewed NER + DLP pipeline."""

    PATTERNS = {
        "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
        "phone": re.compile(r"(?<!\d)(?:\+7|8)[\s()\-]*\d{3}[\s()\-]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)"),
        "card": re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
    }

    def redact(self, text: str) -> tuple[str, dict[str, int]]:
        counts: Counter[str] = Counter()
        redacted = text
        for pii_type, pattern in self.PATTERNS.items():
            redacted, count = pattern.subn(f"<{pii_type.upper()}_REDACTED>", redacted)
            if count:
                counts[pii_type] += count
        return redacted, dict(sorted(counts.items()))


class RuleClassifier:
    RULES = {
        "security": ("взлом", "мошен", "украли", "подозрительн", "чужой вход"),
        "payment": ("списал", "списани", "оплат", "платеж", "карт", "возврат", "верните деньги", "чек"),
        "incident": ("не работает", "недоступ", "сбой", "ошибка 5", "лежит", "не открывается"),
        "access": ("парол", "не могу войти", "код входа", "аккаунт", "авторизац"),
        "general_faq": ("язык", "уведомлен", "темная тема", "настройк", "тарифы"),
    }

    def classify(self, text: str) -> Classification:
        value = normalize(text)
        scored: list[tuple[int, str, list[str]]] = []
        for topic, signals in self.RULES.items():
            matched = [signal for signal in signals if signal in value]
            scored.append((len(matched), topic, matched))
        scored.sort(reverse=True)
        top_count, topic, matches = scored[0]
        second_count = scored[1][0]
        if top_count == 0:
            return Classification(topic="unknown", confidence=0.35, matched_signals=[])
        margin = top_count - second_count
        confidence = min(0.98, 0.64 + 0.16 * top_count + 0.08 * margin)
        return Classification(topic=topic, confidence=round(confidence, 3), matched_signals=matches)


class RiskPolicy:
    RISKY_TOPICS = {"payment", "security"}
    RISK_SIGNALS = {
        "refund_or_money_movement": ("возврат", "верните деньги", "списали дважды", "двойное списание"),
        "account_compromise": ("взлом", "мошен", "украли", "чужой вход"),
        "legal_or_privacy_request": ("суд", "претенз", "удалите мои данные", "персональные данные"),
        "harm_or_threat": ("суицид", "убью", "угрож"),
    }

    def evaluate(
        self,
        text: str,
        classification: Classification,
        pii_types: dict[str, int],
    ) -> tuple[str, list[str]]:
        value = normalize(text)
        reasons: list[str] = []
        if classification.topic in self.RISKY_TOPICS:
            reasons.append(f"risky_topic:{classification.topic}")
        for reason, signals in self.RISK_SIGNALS.items():
            if any(signal in value for signal in signals):
                reasons.append(reason)
        if pii_types.get("card"):
            reasons.append("sensitive_pii:card")
        if classification.confidence < 0.72:
            reasons.append("low_classification_confidence")
        return ("high" if reasons else "low"), sorted(set(reasons))


class LexicalRetriever:
    TOKEN_PATTERN = re.compile(r"[a-zа-яё0-9]+", re.I)

    def __init__(self, knowledge_base_path: Path | None = None) -> None:
        path = knowledge_base_path or Path(__file__).parent / "data" / "kb.json"
        self.documents: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))

    def _tokens(self, text: str) -> set[str]:
        return set(self.TOKEN_PATTERN.findall(normalize(text)))

    def retrieve(self, text: str, topic: str) -> RetrievedDocument | None:
        query_tokens = self._tokens(text)
        candidates = [doc for doc in self.documents if doc["topic"] == topic]
        best: tuple[float, dict[str, Any]] | None = None
        for document in candidates:
            corpus = " ".join((document["title"], document["answer"], *document["keywords"]))
            document_tokens = self._tokens(corpus)
            token_overlap = len(query_tokens & document_tokens) / math.sqrt(
                max(1, len(query_tokens) * len(document_tokens))
            )
            keyword_hits = sum(keyword in normalize(text) for keyword in document["keywords"])
            keyword_score = keyword_hits / max(1, len(document["keywords"]))
            score = round(0.65 * keyword_score + 0.35 * token_overlap, 3)
            if best is None or score > best[0]:
                best = (score, document)
        if best is None:
            return None
        score, document = best
        return RetrievedDocument(
            document_id=document["id"],
            title=document["title"],
            answer=document["answer"],
            score=score,
        )


class GeneratorUnavailable(RuntimeError):
    pass


class TemplateGenerator:
    """Deterministic stand-in for the asynchronous RAG/LLM generation stage."""

    def __init__(self, available: bool = True) -> None:
        self.available = available

    def generate(self, document: RetrievedDocument) -> str:
        if not self.available:
            raise GeneratorUnavailable("draft generator is unavailable")
        return f"{document.answer}\n\nИсточник: база знаний, {document.title}."


class JsonlAuditLogger:
    def __init__(self, path: Path | None) -> None:
        self.path = path

    def record(self, decision: Decision, redacted_text: str) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = decision.to_dict()
        # Raw and redacted ticket bodies are deliberately not persisted in the audit event.
        event["input_fingerprint"] = hashlib.sha256(redacted_text.encode("utf-8")).hexdigest()
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


class DecisionEngine:
    AUTO_REPLY_TOPICS = {"general_faq"}
    RETRIEVAL_THRESHOLD = 0.42

    def __init__(
        self,
        *,
        generator_available: bool = True,
        audit_log_path: Path | None = Path("artifacts/decisions.jsonl"),
    ) -> None:
        self.redactor = PiiRedactor()
        self.classifier = RuleClassifier()
        self.risk_policy = RiskPolicy()
        self.retriever = LexicalRetriever()
        self.generator = TemplateGenerator(available=generator_available)
        self.audit = JsonlAuditLogger(audit_log_path)

    def process(self, ticket: Ticket) -> Decision:
        started_at = datetime.now(timezone.utc)
        redacted_text, pii_types = self.redactor.redact(ticket.text)
        classification = self.classifier.classify(redacted_text)
        risk, risk_reasons = self.risk_policy.evaluate(
            redacted_text, classification, pii_types
        )
        retrieved = self.retriever.retrieve(redacted_text, classification.topic)

        action = "human_review"
        route = self._route(classification.topic)
        auto_send = False
        draft: str | None = None
        fallback_reason: str | None = None

        if risk == "high":
            fallback_reason = "risk_policy"
        elif retrieved is None or retrieved.score < self.RETRIEVAL_THRESHOLD:
            fallback_reason = "insufficient_knowledge_match"
        elif classification.topic not in self.AUTO_REPLY_TOPICS:
            fallback_reason = "topic_not_auto_reply_allowlisted"
        else:
            try:
                draft = self.generator.generate(retrieved)
                action = "auto_reply"
                route = "resolved_automatically"
                auto_send = True
            except GeneratorUnavailable:
                action = "queued_for_human"
                route = "generation_fallback_queue"
                fallback_reason = "generator_unavailable"

        ended_at = datetime.now(timezone.utc)
        decision = Decision(
            decision_id=str(uuid.uuid4()),
            ticket_id=ticket.ticket_id,
            topic=classification.topic,
            topic_confidence=classification.confidence,
            risk=risk,
            risk_reasons=risk_reasons,
            pii_types=pii_types,
            retrieved_document_id=retrieved.document_id if retrieved else None,
            retrieval_score=retrieved.score if retrieved else 0.0,
            action=action,
            route=route,
            auto_send=auto_send,
            draft=draft,
            fallback_reason=fallback_reason,
            versions={
                "policy": POLICY_VERSION,
                "classifier": CLASSIFIER_VERSION,
                "retriever": RETRIEVER_VERSION,
                "generator": "template-v1",
            },
            decided_at=ended_at.isoformat(),
            latency_ms=round((ended_at - started_at).total_seconds() * 1000, 3),
        )
        self.audit.record(decision, redacted_text)
        return decision

    @staticmethod
    def _route(topic: str) -> str:
        return {
            "payment": "payments_l2",
            "security": "trust_and_safety",
            "incident": "incident_queue",
            "access": "account_support",
            "general_faq": "general_support",
        }.get(topic, "manual_triage")

