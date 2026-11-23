# agy-message-timestamps

An Antigravity CLI (`agy`) plugin that uses `PreInvocation` and `PostInvocation` lifecycle hooks to display local timestamps below user messages (`Sent ...`) and Gemini replies (`Started ... · Finished ...`).

## Structure

- `plugin.json` — plugin manifest
- `hooks.json` — registers `PreInvocation` and `PostInvocation` command hooks
- `hooks/timestamps.py` — tracks per-conversation turn start times and emits injected timestamp steps

## Notes

- In `agy` v1.5.14:
  - `systemMessage` with `metadata.user_markdown` triggers an upstream panic in `utils.ScrubInternalFields` (`proto_utils.go:34`).
  - Plain `systemMessage` (without `metadata`) injects cleanly for the model, but is hidden in the `agy` CLI TUI.
  - By default this plugin uses `errorMessage` (without `terminationBehavior: "terminate"`), which displays directly to the user without sending extra tokens to the model. Caveat: it uses error styling and causes headless `agy -p` runs to exit non-zero.
- Set `AGY_TIMESTAMPS_MODE` to switch modes (`error_message`, `user_message`, `user_markdown`, or `system_message`).
- Set `AGY_TIMESTAMPS_DEBUG=1` to append hook invocation traces to `~/.gemini/config/message-timestamps-debug.log`.

## Local Installation

Copy or install into `~/.gemini/config/plugins/message-timestamps/`, then restart `agy`.

Toggle anytime:

```bash
agy plugin disable message-timestamps
agy plugin enable message-timestamps
```
