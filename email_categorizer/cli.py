from __future__ import annotations

from argparse import ArgumentParser
import json
from pathlib import Path

from email_categorizer.config import (
    AccountConfig,
    ConfigError,
    RulesConfig,
    load_account,
    load_rules,
    resolve_password,
)
from email_categorizer.engine import decide
from email_categorizer.imap_client import ImapSession


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACCOUNT_PATH = PROJECT_ROOT / "config" / "account.toml"
DEFAULT_RULES_PATH = PROJECT_ROOT / "config" / "rules.toml"


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Run the prompt-driven email categorizer.")
    parser.add_argument("--account", type=Path, default=DEFAULT_ACCOUNT_PATH)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES_PATH)
    parser.add_argument("--scope", choices=["read", "unread", "all"], default="read")
    parser.add_argument("--order", choices=["oldest", "newest"], default="oldest")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--mailbox", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        account = load_account(args.account)
        rules = load_rules(args.rules)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 2

    if args.mailbox:
        account.mailbox = args.mailbox

    try:
        results = run(
            account=account,
            rules=rules,
            scope=args.scope,
            order=args.order,
            limit=args.limit,
            apply=args.apply,
        )
    except Exception as exc:
        print(f"Run failed: {exc}")
        return 1

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    mode = "APPLY" if args.apply else "DRY-RUN"
    for item in results["messages"]:
        destination = f" -> {item['destination']}" if item["destination"] else ""
        rule_text = item["rule_name"] or "default"
        print(
            f"[{mode}] UID {item['uid']} {item['action']}{destination} via {rule_text} | "
            f"{item['sender']} | {item['subject']}"
        )

    summary = results["summary"]
    print(
        "Summary: "
        f"processed={summary['processed']} keep={summary['keep']} "
        f"move={summary['move']} trash={summary['trash']}"
    )
    return 0


def run(
    *,
    account: AccountConfig,
    rules: RulesConfig,
    scope: str,
    order: str,
    limit: int,
    apply: bool,
) -> dict:
    password = resolve_password(account)

    with ImapSession(account, password, apply=apply) as session:
        _validate_mailboxes(session, account, rules)

        messages: list[dict] = []
        counters = {"keep": 0, "move": 0, "trash": 0}
        uids = session.search_uids(scope=scope, order=order, limit=limit)
        for uid in uids:
            message = session.fetch_message(uid, max_body_chars=rules.max_body_chars)
            decision = decide(message, rules)
            if decision.action == "trash" and not decision.destination:
                decision.destination = account.trash_folder
            session.apply_decision(uid, decision)
            counters[decision.action] += 1
            messages.append(
                {
                    "uid": uid,
                    "sender": message.sender,
                    "subject": message.subject,
                    "action": decision.action,
                    "destination": decision.destination,
                    "rule_name": decision.rule_name,
                    "matched": decision.matched,
                    "date": message.date,
                }
            )

    return {
        "summary": {
            "processed": len(messages),
            "keep": counters["keep"],
            "move": counters["move"],
            "trash": counters["trash"],
            "scope": scope,
            "order": order,
            "apply": apply,
        },
        "messages": messages,
    }


def _validate_mailboxes(session: ImapSession, account: AccountConfig, rules: RulesConfig) -> None:
    known_mailboxes = set(session.list_mailboxes())
    required_mailboxes = {account.mailbox, account.trash_folder}
    for rule in rules.rules:
        if rule.action == "move" and rule.destination:
            required_mailboxes.add(rule.destination)

    missing = sorted(name for name in required_mailboxes if name not in known_mailboxes)
    if not missing:
        return

    available = ", ".join(sorted(known_mailboxes))
    raise RuntimeError(
        "Missing mailbox folders: "
        f"{', '.join(missing)}. "
        "Folder names are used exactly as provided by the server. "
        f"Available mailboxes: {available}"
    )
