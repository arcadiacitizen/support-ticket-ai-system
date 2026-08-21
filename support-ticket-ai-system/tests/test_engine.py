import json
import tempfile
import unittest
from pathlib import Path

from support_ticket_ai import DecisionEngine, Ticket


ROOT = Path(__file__).resolve().parents[1]


def fixture(name: str) -> Ticket:
    value = json.loads((ROOT / "examples" / f"{name}.json").read_text(encoding="utf-8"))
    return Ticket.from_dict(value)


class DecisionEngineTest(unittest.TestCase):
    def test_safe_faq_is_auto_replied(self) -> None:
        decision = DecisionEngine(audit_log_path=None).process(fixture("happy"))

        self.assertEqual("general_faq", decision.topic)
        self.assertEqual("low", decision.risk)
        self.assertEqual("auto_reply", decision.action)
        self.assertTrue(decision.auto_send)
        self.assertIn("Настройки", decision.draft or "")

    def test_payment_and_pii_are_escalated(self) -> None:
        decision = DecisionEngine(audit_log_path=None).process(fixture("risky"))

        self.assertEqual("payment", decision.topic)
        self.assertEqual("high", decision.risk)
        self.assertEqual("human_review", decision.action)
        self.assertEqual("payments_l2", decision.route)
        self.assertFalse(decision.auto_send)
        self.assertEqual({"email": 1, "phone": 1}, decision.pii_types)

    def test_generator_outage_fails_closed(self) -> None:
        decision = DecisionEngine(
            generator_available=False,
            audit_log_path=None,
        ).process(fixture("llm_down"))

        self.assertEqual("queued_for_human", decision.action)
        self.assertFalse(decision.auto_send)
        self.assertEqual("generator_unavailable", decision.fallback_reason)

    def test_audit_log_contains_no_raw_pii(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "audit.jsonl"
            DecisionEngine(audit_log_path=log_path).process(fixture("risky"))
            event = log_path.read_text(encoding="utf-8")

        self.assertNotIn("ivan@example.com", event)
        self.assertNotIn("+7 999 123-45-67", event)
        self.assertIn("input_fingerprint", event)


if __name__ == "__main__":
    unittest.main()

