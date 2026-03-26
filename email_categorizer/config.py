from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import subprocess
import tomllib


VALID_ACTIONS = {"keep", "move", "trash"}
VALID_FIELDS = {"from", "from_domain", "to", "cc", "subject", "body", "header"}
VALID_OPERATORS = {
    "contains",
    "equals",
    "regex",
    "starts_with",
    "ends_with",
    "not_contains",
    "not_equals",
    "not_regex",
    "not_starts_with",
    "not_ends_with",
}


@dataclass(slots=True)
class Condition:
    field: str
    operator: str
    value: str
    header: str | None = None
    case_sensitive: bool = False


@dataclass(slots=True)
class Rule:
    name: str
    action: str
    destination: str | None = None
    all_conditions: list[Condition] = field(default_factory=list)
    any_conditions: list[Condition] = field(default_factory=list)


@dataclass(slots=True)
class RulesConfig:
    default_action: str = "keep"
    max_body_chars: int = 4000
    rules: list[Rule] = field(default_factory=list)


@dataclass(slots=True)
class AccountConfig:
    host: str
    port: int = 993
    username: str = ""
    password_env: str = "EMAIL_CATEGORIZER_PASSWORD"
    password_source: str = "env"
    keychain_service: str | None = None
    keychain_account: str | None = None
    mailbox: str = "INBOX"
    trash_folder: str = "Trash"
    use_ssl: bool = True


class ConfigError(ValueError):
    pass


def _load_toml(path: Path) -> dict:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"Missing config file: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {path}: {exc}") from exc


def _parse_condition(raw: dict) -> Condition:
    field_name = str(raw.get("field", "")).strip()
    operator = str(raw.get("operator", "")).strip()
    value = str(raw.get("value", ""))
    header = raw.get("header")

    if field_name not in VALID_FIELDS:
        raise ConfigError(f"Unsupported condition field: {field_name}")
    if operator not in VALID_OPERATORS:
        raise ConfigError(f"Unsupported condition operator: {operator}")
    if field_name == "header" and not header:
        raise ConfigError("Header conditions require a header name")

    return Condition(
        field=field_name,
        operator=operator,
        value=value,
        header=str(header).strip() if header else None,
        case_sensitive=bool(raw.get("case_sensitive", False)),
    )


def _parse_rule(raw: dict) -> Rule:
    name = str(raw.get("name", "")).strip()
    action = str(raw.get("action", "")).strip()
    destination = raw.get("destination")
    match_mode = str(raw.get("match", "all")).strip().lower()

    if not name:
        raise ConfigError("Every rule requires a name")
    if action not in VALID_ACTIONS:
        raise ConfigError(f"Unsupported rule action for {name}: {action}")
    if action == "move" and not destination:
        raise ConfigError(f"Move rule {name} requires a destination")

    all_conditions = [_parse_condition(item) for item in raw.get("all", [])]
    any_conditions = [_parse_condition(item) for item in raw.get("any", [])]

    if "conditions" in raw and not all_conditions and not any_conditions:
        parsed = [_parse_condition(item) for item in raw["conditions"]]
        if match_mode == "any":
            any_conditions = parsed
        else:
            all_conditions = parsed

    if not all_conditions and not any_conditions:
        raise ConfigError(f"Rule {name} requires at least one condition")

    return Rule(
        name=name,
        action=action,
        destination=str(destination).strip() if destination else None,
        all_conditions=all_conditions,
        any_conditions=any_conditions,
    )


def load_rules(path: Path) -> RulesConfig:
    raw = _load_toml(path)
    default_action = str(raw.get("default_action", "keep")).strip()
    if default_action not in VALID_ACTIONS:
        raise ConfigError(f"Unsupported default_action: {default_action}")

    rules = [_parse_rule(item) for item in raw.get("rules", [])]

    return RulesConfig(
        default_action=default_action,
        max_body_chars=int(raw.get("max_body_chars", 4000)),
        rules=rules,
    )


def load_account(path: Path) -> AccountConfig:
    raw = _load_toml(path)
    host = str(raw.get("host", "")).strip()
    username = str(raw.get("username", "")).strip()
    password_source = str(raw.get("password_source", "env")).strip()

    if not host:
        raise ConfigError("Account config requires host")
    if not username:
        raise ConfigError("Account config requires username")
    if password_source not in {"env", "keychain"}:
        raise ConfigError("password_source must be 'env' or 'keychain'")

    keychain_service = raw.get("keychain_service")
    keychain_account = raw.get("keychain_account")
    if password_source == "keychain" and not keychain_service:
        raise ConfigError("Keychain password_source requires keychain_service")

    return AccountConfig(
        host=host,
        port=int(raw.get("port", 993)),
        username=username,
        password_env=str(raw.get("password_env", "EMAIL_CATEGORIZER_PASSWORD")).strip(),
        password_source=password_source,
        keychain_service=str(keychain_service).strip() if keychain_service else None,
        keychain_account=str(keychain_account).strip() if keychain_account else username,
        mailbox=str(raw.get("mailbox", "INBOX")).strip(),
        trash_folder=str(raw.get("trash_folder", "Trash")).strip(),
        use_ssl=bool(raw.get("use_ssl", True)),
    )


def resolve_password(account: AccountConfig) -> str:
    if account.password_source == "keychain":
        return _resolve_keychain_password(account)

    password = os.environ.get(account.password_env)
    if not password:
        raise ConfigError(
            f"Environment variable {account.password_env} is not set; "
            "store the IMAP password or app password there."
        )
    return password


def _resolve_keychain_password(account: AccountConfig) -> str:
    service = account.keychain_service or ""
    keychain_account = account.keychain_account or account.username
    try:
        completed = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                service,
                "-a",
                keychain_account,
                "-w",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise ConfigError("macOS 'security' command not found for keychain lookup") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise ConfigError(
            f"Could not read password from Keychain for service={service!r} "
            f"account={keychain_account!r}{f': {stderr}' if stderr else ''}"
        ) from exc

    password = completed.stdout.strip()
    if not password:
        raise ConfigError(
            f"Keychain lookup returned an empty password for service={service!r} "
            f"account={keychain_account!r}"
        )
    return password
