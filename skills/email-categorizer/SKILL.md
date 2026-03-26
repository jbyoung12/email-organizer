---
name: email-categorizer
description: Run the local IMAP email categorizer when the user wants to sort email into folders or trash using prewritten rules. Use it for explicit inbox triage, dry-run previews, and apply runs that move messages. Do not use it automatically.
user-invocable: true
---

# Email Categorizer

Use this skill only when the user explicitly asks to triage, sort, or clean up email. This skill is manual-only. Default to dry-run and only apply mailbox changes after the user explicitly asks for them.

## Workflow

1. Check whether the project config files `config/account.toml` and `config/rules.toml` are configured.
2. If the user wants a preview, run:

```bash
{baseDir}/scripts/run_email_categorizer.sh --scope read --order oldest
```

3. If the user explicitly wants the mailbox changed, rerun with `--apply`.
4. Report the matched folders, trash decisions, and summary counts.

## Guardrails

- Never run this skill on a schedule or in the background.
- Never apply changes unless the user explicitly asks.
- Default to already-read mail with `--scope read`, process oldest-first with `--order oldest`, and scan the full selected mailbox unless the user explicitly adds `--limit`.
- Use the configured TOML rules; do not invent categorization logic ad hoc.
- If the account file still has placeholder values, or the configured env var / Keychain entry is missing, stop and say what needs to be configured.

## Resources

- Read [references/configuration.md](./references/configuration.md) only when you need to edit the account or rule files.
- Use [scripts/run_email_categorizer.sh](./scripts/run_email_categorizer.sh) for execution instead of rebuilding the command by hand.
