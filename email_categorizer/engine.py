from __future__ import annotations

from dataclasses import dataclass, field
import re

from email_categorizer.config import Condition, Rule, RulesConfig


@dataclass(slots=True)
class MessageData:
    uid: str
    subject: str = ""
    sender: str = ""
    from_domain: str = ""
    to: str = ""
    cc: str = ""
    body: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    date: str = ""


@dataclass(slots=True)
class Decision:
    uid: str
    action: str
    destination: str | None = None
    rule_name: str | None = None
    matched: bool = False


def _value_for_condition(message: MessageData, condition: Condition) -> str:
    if condition.field == "header":
        if not condition.header:
            return ""
        return message.headers.get(condition.header.lower(), "")
    if condition.field == "from":
        return message.sender
    if condition.field == "from_domain":
        return message.from_domain
    if condition.field == "to":
        return message.to
    if condition.field == "cc":
        return message.cc
    if condition.field == "subject":
        return message.subject
    if condition.field == "body":
        return message.body
    return ""


def _normalize_pair(left: str, right: str, case_sensitive: bool) -> tuple[str, str]:
    if case_sensitive:
        return left, right
    return left.lower(), right.lower()


def condition_matches(message: MessageData, condition: Condition) -> bool:
    actual = _value_for_condition(message, condition)
    expected = condition.value

    normalized_actual, normalized_expected = _normalize_pair(
        actual,
        expected,
        condition.case_sensitive,
    )

    if condition.operator == "contains":
        return normalized_expected in normalized_actual
    if condition.operator == "equals":
        return normalized_actual == normalized_expected
    if condition.operator == "starts_with":
        return normalized_actual.startswith(normalized_expected)
    if condition.operator == "ends_with":
        return normalized_actual.endswith(normalized_expected)
    if condition.operator == "not_contains":
        return normalized_expected not in normalized_actual
    if condition.operator == "not_equals":
        return normalized_actual != normalized_expected
    if condition.operator == "not_starts_with":
        return not normalized_actual.startswith(normalized_expected)
    if condition.operator == "not_ends_with":
        return not normalized_actual.endswith(normalized_expected)

    flags = 0 if condition.case_sensitive else re.IGNORECASE
    matched = bool(re.search(condition.value, actual, flags=flags))
    if condition.operator == "regex":
        return matched
    if condition.operator == "not_regex":
        return not matched
    raise ValueError(f"Unhandled operator: {condition.operator}")


def rule_matches(message: MessageData, rule: Rule) -> bool:
    if rule.all_conditions and not all(
        condition_matches(message, condition) for condition in rule.all_conditions
    ):
        return False
    if rule.any_conditions and not any(
        condition_matches(message, condition) for condition in rule.any_conditions
    ):
        return False
    return True


def decide(message: MessageData, rules: RulesConfig) -> Decision:
    for rule in rules.rules:
        if not rule_matches(message, rule):
            continue
        destination = rule.destination
        return Decision(
            uid=message.uid,
            action=rule.action,
            destination=destination,
            rule_name=rule.name,
            matched=True,
        )

    return Decision(uid=message.uid, action=rules.default_action, matched=False)
