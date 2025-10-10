"""Тести rules engine."""
from __future__ import annotations

from cortexwatcher.analyzer.rules_engine import RuleEngine


def test_rule_match(tmp_path) -> None:
    rules_file = tmp_path / "rules.yaml"
    rules_file.write_text(
        """
- id: test
  title: "Тест"
  description: ""
  severity: 5
  patterns:
    - "error"
  filters:
    app: ["app*"]
""",
        encoding="utf-8",
    )
    engine = RuleEngine(rules_file)
    matches = engine.match({"msg": "critical error", "app": "app1"})
    assert matches and matches[0].id == "test"

