# agy-message-timestamps

An Antigravity CLI (`agy`) plugin that uses `PreInvocation` and `PostInvocation` lifecycle hooks to display local timestamps below user messages (`Sent ...`) and Gemini replies (`Started ... · Finished ...`).

## Structure

- `plugin.json` — plugin manifest
- `hooks.json` — registers `PreInvocation` and `PostInvocation` command hooks
- `hooks/timestamps.py` — tracks per-conversation turn start times and emits injected timestamp steps

## Local Installation

Copy or install into `~/.gemini/config/plugins/message-timestamps/`, then restart `agy`.

Toggle anytime:

```bash
agy plugin disable message-timestamps
agy plugin enable message-timestamps
```
