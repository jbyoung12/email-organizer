from __future__ import annotations

import unittest
from unittest.mock import Mock

from email_categorizer.config import AccountConfig
from email_categorizer.imap_client import ImapSession, _parse_list_mailbox_name


class ImapClientTests(unittest.TestCase):
    def test_parse_gmail_system_mailbox(self) -> None:
        line = '(\\HasNoChildren) "/" "[Gmail]/Trash"'
        self.assertEqual(_parse_list_mailbox_name(line), "[Gmail]/Trash")

    def test_parse_simple_mailbox(self) -> None:
        line = '(\\HasNoChildren) "/" "Work"'
        self.assertEqual(_parse_list_mailbox_name(line), "Work")

    def test_search_uids_oldest_first(self) -> None:
        session = ImapSession(
            AccountConfig(host="imap.example.com", username="user@example.com"),
            "secret",
            apply=False,
        )
        client = Mock()
        client.uid.return_value = ("OK", [b"10 11 12 13"])
        session.client = client

        self.assertEqual(session.search_uids(scope="read", order="oldest", limit=2), ["10", "11"])

    def test_search_uids_newest_first(self) -> None:
        session = ImapSession(
            AccountConfig(host="imap.example.com", username="user@example.com"),
            "secret",
            apply=False,
        )
        client = Mock()
        client.uid.return_value = ("OK", [b"10 11 12 13"])
        session.client = client

        self.assertEqual(session.search_uids(scope="read", order="newest", limit=2), ["13", "12"])

    def test_search_uids_without_limit_returns_all(self) -> None:
        session = ImapSession(
            AccountConfig(host="imap.example.com", username="user@example.com"),
            "secret",
            apply=False,
        )
        client = Mock()
        client.uid.return_value = ("OK", [b"10 11 12 13"])
        session.client = client

        self.assertEqual(session.search_uids(scope="read", order="oldest", limit=None), ["10", "11", "12", "13"])


if __name__ == "__main__":
    unittest.main()
