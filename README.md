# Email Organizer

Prompt-driven IMAP email categorizer with deterministic rules.

The repository is named `email-organizer`, while the current Python package and CLI module are still named `email_categorizer`. That is intentional for now to avoid a breaking rename.

The tool connects directly to an IMAP mailbox, evaluates ordered rules, and then either:

- keeps the message in place
- moves it to another mailbox/folder
- moves it to trash

It is designed to be safe by default:

- dry-run by default
- oldest-first by default
- mailbox existence is validated before processing
- passwords stay out of the repo
- full selected mailbox by default unless `--limit` is provided

## Setup

1. Copy the example config files:

```bash
cp config/account.example.toml config/account.toml
cp config/rules.example.toml config/rules.toml
```

2. Edit `config/account.toml` with your IMAP host, username, and mailbox names.

Example for Gmail:

```toml
host = "imap.gmail.com"
port = 993
username = "you@gmail.com"
password_source = "keychain"
keychain_service = "email-categorizer-imap"
keychain_account = "you@gmail.com"
mailbox = "INBOX"
trash_folder = "[Gmail]/Trash"
use_ssl = true
```

3. Edit `config/rules.toml` with your own rules.

Minimal example:

```toml
default_action = "keep"

[[rules]]
name = "Receipts"
action = "move"
destination = "Receipts"
match = "any"

[[rules.conditions]]
field = "subject"
operator = "regex"
value = '(?i)\b(receipt|delivered|delivery update)\b'

[[rules]]
name = "Newsletters"
action = "trash"

[[rules.conditions]]
field = "from"
operator = "equals"
value = "newsletter@example.com"
```

4. Store your IMAP password or app password in macOS Keychain:

```bash
security add-generic-password -U -s email-categorizer-imap -a you@example.com -w 'your-app-password'
```

## Run

Dry run on all read mail, oldest first:

```bash
python3 -m email_categorizer --scope read --order oldest
```

Live run on all read mail:

```bash
python3 -m email_categorizer --scope read --order oldest --apply
```

Full mailbox, including unread:

```bash
python3 -m email_categorizer --scope all --order oldest --apply
```

Limit a run explicitly:

```bash
python3 -m email_categorizer --scope read --order oldest --limit 100 --apply
```

Output machine-readable results:

```bash
python3 -m email_categorizer --scope read --order oldest --json
```

## Rule behavior

- Rules run top to bottom.
- First matching rule wins.
- `move` rules require a destination mailbox.
- If a destination mailbox does not exist exactly as named on the server, the run fails before any mail is processed.
- `--scope read` means seen mail only.
- `--scope all` means read and unread mail.
- If `--limit` is omitted, the full selected mailbox scope is processed.

## OpenClaw

The repo also contains an optional OpenClaw skill in `skills/email-categorizer/`.

## Publishable Layout

Files intended for local-only use are ignored:

- `config/account.toml`
- `config/rules.toml`

Files intended for the public repo:

- `config/account.example.toml`
- `config/rules.example.toml`

## Tests

```bash
python3 -m unittest discover -s tests -v
```
