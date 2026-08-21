from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import DecisionEngine, Ticket


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    "happy": (ROOT / "examples" / "happy.json", True),
    "risky": (ROOT / "examples" / "risky.json", True),
    "llm_down": (ROOT / "examples" / "llm_down.json", False),
}


def run_scenario(name: str, audit_log_path: Path | None) -> dict[str, object]:
    fixture_path, generator_available = SCENARIOS[name]
    ticket = Ticket.from_dict(json.loads(fixture_path.read_text(encoding="utf-8")))
    decision = DecisionEngine(
        generator_available=generator_available,
        audit_log_path=audit_log_path,
    ).process(ticket)
    return {"scenario": name, "decision": decision.to_dict()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe support-ticket automation PoC")
    parser.add_argument(
        "--scenario",
        choices=["all", *SCENARIOS],
        default="all",
        help="demo scenario to run",
    )
    parser.add_argument(
        "--audit-log",
        type=Path,
        default=Path("artifacts/decisions.jsonl"),
        help="JSONL decision-log destination",
    )
    args = parser.parse_args()

    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    for name in names:
        print(json.dumps(run_scenario(name, args.audit_log), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

