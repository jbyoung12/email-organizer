from __future__ import annotations

import unittest

from email_categorizer.config import Condition, Rule, RulesConfig
from email_categorizer.engine import MessageData, decide


class EngineTests(unittest.TestCase):
    def test_first_matching_rule_wins(self) -> None:
        message = MessageData(
            uid="1",
            sender="alerts@example.com",
            from_domain="example.com",
            subject="Daily status",
            body="summary",
            headers={},
        )
        rules = RulesConfig(
            rules=[
                Rule(
                    name="alerts-folder",
                    action="move",
                    destination="Alerts",
                    all_conditions=[
                        Condition(field="from_domain", operator="equals", value="example.com")
                    ],
                ),
                Rule(
                    name="catch-all-trash",
                    action="trash",
                    all_conditions=[
                        Condition(field="subject", operator="contains", value="daily")
                    ],
                ),
            ]
        )

        decision = decide(message, rules)

        self.assertEqual(decision.action, "move")
        self.assertEqual(decision.destination, "Alerts")
        self.assertEqual(decision.rule_name, "alerts-folder")

    def test_any_conditions_match(self) -> None:
        message = MessageData(
            uid="2",
            sender="jobs@linkedin.com",
            from_domain="linkedin.com",
            subject="A recruiter viewed your profile",
            body="hello",
            headers={"list-id": "updates.linkedin.com"},
        )
        rules = RulesConfig(
            rules=[
                Rule(
                    name="career-mail",
                    action="move",
                    destination="Career",
                    any_conditions=[
                        Condition(field="subject", operator="contains", value="recruiter"),
                        Condition(field="header", header="List-Id", operator="contains", value="linkedin"),
                    ],
                )
            ]
        )

        decision = decide(message, rules)

        self.assertTrue(decision.matched)
        self.assertEqual(decision.destination, "Career")

    def test_default_action_is_used_when_no_rule_matches(self) -> None:
        message = MessageData(uid="3", sender="friend@example.org", from_domain="example.org")
        rules = RulesConfig(default_action="keep", rules=[])

        decision = decide(message, rules)

        self.assertEqual(decision.action, "keep")
        self.assertFalse(decision.matched)


if __name__ == "__main__":
    unittest.main()
