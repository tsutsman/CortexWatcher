"""Простий рушій правил на основі YAML."""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Sequence

import yaml


@dataclass
class Rule:
    """Опис однієї сигнатури."""

    id: str
    title: str
    description: str
    severity: int
    patterns: Sequence[str] = field(default_factory=list)
    tags: Sequence[str] = field(default_factory=list)
    filters: dict[str, Sequence[str]] = field(default_factory=dict)


class RuleEngine:
    """Рушій, що застосовує правила до нормалізованих логів."""

    def __init__(self, rules_path: str | Path) -> None:
        self.rules_path = Path(rules_path)
        self.rules: List[Rule] = []
        self._load_rules()

    def _load_rules(self) -> None:
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Файл правил не знайдено: {self.rules_path}")
        with self.rules_path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or []
        self.rules = [Rule(**item) for item in raw]

    def reload(self) -> None:
        """Перечитує файл правил."""

        self._load_rules()

    def match(self, record: dict) -> List[Rule]:
        """Повертає правила, що спрацювали для запису."""

        message = str(record.get("msg") or record.get("message") or "")
        host = record.get("host")
        app = record.get("app")
        severity = record.get("severity")
        matched: List[Rule] = []
        for rule in self.rules:
            if not self._check_filters(rule, host=host, app=app, severity=severity):
                continue
            if rule.patterns:
                if not any(self._pattern_matches(pattern, message) for pattern in rule.patterns if pattern):
                    continue
            matched.append(rule)
        return matched

    def _pattern_matches(self, pattern: str, message: str) -> bool:
        if pattern.startswith("/") and pattern.endswith("/"):
            try:
                regex = re.compile(pattern.strip("/"), re.IGNORECASE)
                return bool(regex.search(message))
            except re.error:
                return False
        if any(char in pattern for char in "*?[]"):
            return fnmatch.fnmatch(message.lower(), pattern.lower())
        return pattern.lower() in message.lower()

    def _check_filters(self, rule: Rule, **values: object) -> bool:
        for key, allowed in rule.filters.items():
            if not allowed:
                continue
            value = values.get(key)
            if value is None:
                return False
            str_value = str(value)
            if not any(fnmatch.fnmatch(str_value, pattern) for pattern in allowed):
                return False
        return True

    def iter_rules(self) -> Iterable[Rule]:
        """Повертає всі правила."""

        return iter(self.rules)


__all__ = ["RuleEngine", "Rule"]
