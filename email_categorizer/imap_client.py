from __future__ import annotations

from email import message_from_bytes
from email.message import Message
from email.policy import default
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
import imaplib
import re

from email_categorizer.config import AccountConfig
from email_categorizer.engine import Decision, MessageData


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return " ".join(self.parts)


class ImapSession:
    def __init__(self, account: AccountConfig, password: str, *, apply: bool) -> None:
        self.account = account
        self.password = password
        self.apply = apply
        self.client: imaplib.IMAP4 | imaplib.IMAP4_SSL | None = None
        self._needs_expunge = False

    def __enter__(self) -> "ImapSession":
        if self.account.use_ssl:
            self.client = imaplib.IMAP4_SSL(self.account.host, self.account.port)
        else:
            self.client = imaplib.IMAP4(self.account.host, self.account.port)
        self.client.login(self.account.username, self.password)
        status, _ = self.client.select(self.account.mailbox, readonly=not self.apply)
        if status != "OK":
            raise RuntimeError(f"Unable to select mailbox {self.account.mailbox}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.client is None:
            return
        try:
            if self.apply and self._needs_expunge:
                self.client.expunge()
        finally:
            try:
                self.client.close()
            except imaplib.IMAP4.error:
                pass
            self.client.logout()

    @property
    def capabilities(self) -> set[str]:
        if self.client is None:
            return set()
        return {
            capability.decode("utf-8", errors="ignore").upper()
            if isinstance(capability, bytes)
            else str(capability).upper()
            for capability in self.client.capabilities
        }

    def search_uids(self, scope: str, order: str, limit: int | None) -> list[str]:
        if self.client is None:
            raise RuntimeError("Session is not open")
        if scope == "unread":
            query = "UNSEEN"
        elif scope == "read":
            query = "SEEN"
        else:
            query = "ALL"
        status, data = self.client.uid("SEARCH", None, query)
        if status != "OK":
            raise RuntimeError(f"Search failed for scope {scope}")
        raw = data[0].decode("utf-8", errors="ignore").strip() if data and data[0] else ""
        if not raw:
            return []
        uids = raw.split()
        if limit is None or limit <= 0:
            return list(reversed(uids)) if order == "newest" else uids
        if order == "newest":
            return list(reversed(uids[-limit:]))
        return uids[:limit]

    def list_mailboxes(self) -> list[str]:
        if self.client is None:
            raise RuntimeError("Session is not open")
        status, data = self.client.list()
        if status != "OK":
            raise RuntimeError("LIST failed while retrieving mailboxes")
        mailboxes: list[str] = []
        for item in data or []:
            if item is None:
                continue
            decoded = item.decode("utf-8", errors="replace") if isinstance(item, bytes) else str(item)
            name = _parse_list_mailbox_name(decoded)
            if name:
                mailboxes.append(name)
        return mailboxes

    def fetch_message(self, uid: str, *, max_body_chars: int) -> MessageData:
        if self.client is None:
            raise RuntimeError("Session is not open")
        status, data = self.client.uid("FETCH", uid, "(BODY.PEEK[])")
        if status != "OK":
            raise RuntimeError(f"FETCH failed for UID {uid}")

        payload = b""
        for part in data:
            if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], bytes):
                payload = part[1]
                break
        if not payload:
            raise RuntimeError(f"No message body returned for UID {uid}")

        parsed = message_from_bytes(payload, policy=default)
        sender_email = _first_email(parsed.get("From", ""))
        date_text = parsed.get("Date", "")
        try:
            date_value = parsedate_to_datetime(date_text).isoformat()
        except Exception:
            date_value = date_text

        return MessageData(
            uid=uid,
            subject=str(parsed.get("Subject", "")),
            sender=sender_email,
            from_domain=_domain_from_email(sender_email),
            to=", ".join(_email_list(parsed.get_all("To", []))),
            cc=", ".join(_email_list(parsed.get_all("Cc", []))),
            body=_extract_body(parsed, max_body_chars=max_body_chars),
            headers={key.lower(): str(value) for key, value in parsed.items()},
            date=date_value,
        )

    def apply_decision(self, uid: str, decision: Decision) -> None:
        if not self.apply:
            return
        if self.client is None:
            raise RuntimeError("Session is not open")
        if decision.action == "keep":
            return

        destination = decision.destination or self.account.trash_folder
        if "MOVE" in self.capabilities:
            status, _ = self.client.uid("MOVE", uid, destination)
            if status != "OK":
                raise RuntimeError(f"MOVE failed for UID {uid} -> {destination}")
            return

        status, _ = self.client.uid("COPY", uid, destination)
        if status != "OK":
            raise RuntimeError(f"COPY failed for UID {uid} -> {destination}")
        status, _ = self.client.uid("STORE", uid, "+FLAGS.SILENT", r"(\Deleted)")
        if status != "OK":
            raise RuntimeError(f"STORE \\Deleted failed for UID {uid}")
        self._needs_expunge = True


def _first_email(header_value: str) -> str:
    addresses = getaddresses([header_value])
    if not addresses:
        return ""
    return addresses[0][1].strip().lower()


def _email_list(header_values: list[str]) -> list[str]:
    addresses = getaddresses(header_values)
    return [email.strip().lower() for _, email in addresses if email]


def _domain_from_email(email_address: str) -> str:
    if "@" not in email_address:
        return ""
    return email_address.split("@", 1)[1].lower()


def _extract_body(message: Message, *, max_body_chars: int) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = str(part.get_content_disposition() or "").lower()
            if disposition == "attachment":
                continue
            extracted = _decode_part(part)
            if not extracted:
                continue
            if content_type == "text/plain":
                plain_parts.append(extracted)
            elif content_type == "text/html":
                html_parts.append(_strip_html(extracted))
    else:
        extracted = _decode_part(message)
        if message.get_content_type() == "text/html":
            html_parts.append(_strip_html(extracted))
        else:
            plain_parts.append(extracted)

    body = "\n".join(part for part in plain_parts if part).strip()
    if not body:
        body = "\n".join(part for part in html_parts if part).strip()
    return body[:max_body_chars]


def _decode_part(part: Message) -> str:
    try:
        payload = part.get_payload(decode=True)
    except Exception:
        payload = None
    if payload is None:
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def _strip_html(raw_html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(raw_html)
    return parser.text()


def _parse_list_mailbox_name(line: str) -> str:
    match = re.search(r' "[^"]*" (?P<name>".*"|[^"]\S*|INBOX)$', line)
    if not match:
        parts = line.rsplit(" ", 1)
        name = parts[-1] if parts else line
    else:
        name = match.group("name")

    if name.startswith('"') and name.endswith('"'):
        name = name[1:-1]
    return name.replace(r'\"', '"')
