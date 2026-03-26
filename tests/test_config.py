from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from email_categorizer.config import AccountConfig, ConfigError, resolve_password


class ConfigTests(unittest.TestCase):
    def test_resolve_password_from_env(self) -> None:
        account = AccountConfig(
            host="imap.example.com",
            username="user@example.com",
            password_source="env",
            password_env="EMAIL_CATEGORIZER_PASSWORD_TEST",
        )

        with patch.dict(os.environ, {"EMAIL_CATEGORIZER_PASSWORD_TEST": "secret"}, clear=False):
            self.assertEqual(resolve_password(account), "secret")

    def test_resolve_password_from_keychain(self) -> None:
        account = AccountConfig(
            host="imap.example.com",
            username="user@example.com",
            password_source="keychain",
            keychain_service="email-categorizer-imap",
            keychain_account="user@example.com",
        )

        with patch("email_categorizer.config.subprocess.run") as run_mock:
            run_mock.return_value.stdout = "secret\n"
            self.assertEqual(resolve_password(account), "secret")

    def test_missing_env_password_raises(self) -> None:
        account = AccountConfig(
            host="imap.example.com",
            username="user@example.com",
            password_source="env",
            password_env="EMAIL_CATEGORIZER_PASSWORD_MISSING",
        )

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigError):
                resolve_password(account)


if __name__ == "__main__":
    unittest.main()
