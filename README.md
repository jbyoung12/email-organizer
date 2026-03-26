# Email Categorizer

Prompt-driven IMAP email categorizer with deterministic rules.

The tool connects directly to an IMAP mailbox, evaluates ordered rules, and then either:

- keeps the message in place
- moves it to another mailbox/folder
- moves it to trash

It is designed to be safe by default:

- dry-run by default
- oldest-first by default
- mailbox existence is validated before processing
- passwords stay out of the repo

## Setup

1. Copy the example config files:

```bash
cp config/account.example.toml config/account.toml
cp config/rules.example.toml config/rules.toml
```

2. Edit `config/account.toml` with your IMAP host, username, and mailbox names.

3. Edit `config/rules.toml` with your own rules.

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

## Rule behavior

- Rules run top to bottom.
- First matching rule wins.
- `move` rules require a destination mailbox.
- If a destination mailbox does not exist exactly as named on the server, the run fails before any mail is processed.

## OpenClaw

The repo also contains an optional OpenClaw skill in `skills/email-categorizer/`.

## Tests

```bash
python3 -m unittest discover -s tests -v
```
