# agy-message-timestamps

An Antigravity CLI (`agy`) plugin that uses `PreInvocation` and `PostInvocation` lifecycle hooks to display local timestamps below user messages (`Sent ...`) and Gemini replies (`Started ... · Finished ...`).

## Structure

- `plugin.json` — plugin manifest
- `hooks.json` — registers `PreInvocation` and `PostInvocation` command hooks
- `hooks/timestamps.py` — tracks per-conversation turn start times and emits injected timestamp steps

## Notes

- In `agy` v1.5.14, setting `systemMessage.metadata.user_markdown` triggers an upstream panic in `utils.ScrubInternalFields` (`type mismatch: cannot convert string to message`). By default this plugin emits a plain `systemMessage` without `metadata` to avoid the crash.
- Set `AGY_TIMESTAMPS_USE_USER_MARKDOWN=1` to opt back into `metadata.user_markdown` once fixed upstream.
- Set `AGY_TIMESTAMPS_DEBUG=1` to append hook invocation traces to `~/.gemini/config/message-timestamps-debug.log`.

## Local Installation

Copy or install into `~/.gemini/config/plugins/message-timestamps/`, then restart `agy`.

Toggle anytime:

```bash
agy plugin disable message-timestamps
agy plugin enable message-timestamps
```
