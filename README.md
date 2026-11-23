# agy-message-timestamps

An Antigravity CLI (`agy`) plugin that uses `PreInvocation` and `PostInvocation` lifecycle hooks to display local timestamps below user messages (`Sent ...`) and Gemini replies (`Started ... · Finished ...`).

## Structure

- `plugin.json` — plugin manifest
- `hooks.json` — registers `PreInvocation` and `PostInvocation` command hooks
- `hooks/timestamps.py` — tracks per-conversation turn start/finish times and emits injected timestamp steps
- `scripts/statusline.py` — optional custom `/statusline` script showing Sent/Started/Finished timing with subtle ANSI colors

## Custom Status Line

Enable inside `agy` with:

```text
/statusline python3 ~/.gemini/config/plugins/message-timestamps/scripts/statusline.py
```

To stack it below `agy`'s built-in status line instead of replacing it, pass `--timestamps-only` and set `"stack_with_default": true` under `"statusLine"` in `~/.gemini/antigravity-cli/settings.json`.

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
