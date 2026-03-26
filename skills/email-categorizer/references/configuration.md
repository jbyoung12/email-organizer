# Configuration

Edit only these two files for normal use:

- `config/account.toml`
- `config/rules.toml`

## Account file

Required fields:

- `host`: IMAP server hostname
- `username`: mailbox login
- `password_source`: `env` or `keychain`
- `password_env`: environment variable that stores the password or app password when `password_source = "env"`
- `keychain_service`: macOS Keychain service name when `password_source = "keychain"`
- `keychain_account`: Keychain account name, usually the IMAP username
- `mailbox`: source mailbox, usually `INBOX`
- `trash_folder`: destination folder for trash actions

The script does not store the password in the config file.

## macOS Keychain setup

Store the IMAP password or app password with:

```bash
security add-generic-password -U -s email-categorizer-imap -a you@example.com -w 'your-app-password'
```

Then set:

```toml
password_source = "keychain"
keychain_service = "email-categorizer-imap"
keychain_account = "you@example.com"
```

If you prefer environment variables instead:

```toml
password_source = "env"
password_env = "EMAIL_CATEGORIZER_PASSWORD"
```

## Rules file

Rules run top to bottom. First match wins.

Each rule must define:

- `name`
- `action`: `keep`, `move`, or `trash`
- `destination` for `move`

Conditions can inspect:

- `from`
- `from_domain`
- `to`
- `cc`
- `subject`
- `body`
- `header` with `header = "Header-Name"`

Supported operators:

- `contains`
- `equals`
- `regex`
- `starts_with`
- `ends_with`
- `not_contains`
- `not_equals`
- `not_regex`
- `not_starts_with`
- `not_ends_with`

Use `match = "any"` with `[[rules.conditions]]` when any condition should trigger the rule. Otherwise `all` semantics are used.
