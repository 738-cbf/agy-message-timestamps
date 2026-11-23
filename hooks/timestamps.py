#!/usr/bin/env python3
"""Antigravity CLI hook: display local timestamps below user and Gemini messages."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


def get_state_dir() -> Path:
    candidates = []
    plugin_data = os.environ.get("PLUGIN_DATA")
    if plugin_data:
        candidates.append(Path(plugin_data) / "state")
    candidates.append(Path(__file__).resolve().parent.parent / ".state")
    candidates.append(Path(tempfile.gettempdir()) / "agy-message-timestamps-state")

    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_probe"
            probe.write_text("", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return path
        except OSError:
            continue
    return Path(tempfile.gettempdir())


def state_path_for(conversation_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", conversation_id or "default")[:128]
    return get_state_dir() / f"{safe}.json"


def load_state(conversation_id: str) -> dict[str, Any] | None:
    path = state_path_for(conversation_id)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_state(conversation_id: str, state: dict[str, Any]) -> None:
    path = state_path_for(conversation_id)
    try:
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def parse_iso_local(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.astimezone()
        return dt.astimezone()
    except ValueError:
        return None


def read_transcript_tail(transcript_path: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return (last_user_step, last_planner_step) from transcript.jsonl."""
    if not transcript_path:
        return None, None
    path = Path(transcript_path)
    if not path.is_file():
        return None, None

    last_user: dict[str, Any] | None = None
    last_planner: dict[str, Any] | None = None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                step_type = entry.get("type")
                if step_type == "USER_INPUT":
                    last_user = entry
                elif step_type == "PLANNER_RESPONSE":
                    last_planner = entry
    except OSError:
        return None, None

    return last_user, last_planner


def format_time(dt: datetime, include_date: bool = False) -> str:
    hour = dt.strftime("%I").lstrip("0") or "12"
    time_part = f"{hour}:{dt.strftime('%M:%S %p')}"
    if include_date:
        day = dt.strftime("%d").lstrip("0") or "0"
        return f"{dt.strftime('%b')} {day}, {time_part}"
    return time_part


def format_duration(start: datetime, end: datetime) -> str:
    total_seconds = max(0, int(round((end - start).total_seconds())))
    if total_seconds < 1:
        return "<1s"
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def make_timestamp_step(text: str) -> dict[str, Any]:
    # Modes:
    # - error_message (default workaround for agy v1.5.14): visibly renders in TUI
    #   without sending anything to the model, and avoids the proto_utils.go:34 panic
    #   on systemMessage.metadata. (Note: marks headless `agy -p` runs non-zero.)
    # - user_markdown: ideal inline markdown once agy fixes proto_utils.go:34.
    # - user_message: renders as a user message (also sent to the model).
    # - system_message: hidden in agy CLI TUI; visible to the model only.
    mode = os.environ.get("AGY_TIMESTAMPS_MODE", "").strip().lower()
    if not mode and os.environ.get("AGY_TIMESTAMPS_USE_USER_MARKDOWN") == "1":
        mode = "user_markdown"
    if not mode:
        mode = "error_message"

    if mode == "user_markdown":
        return {
            "injectSteps": [
                {
                    "systemMessage": {
                        "systemMessage": "",
                        "metadata": {
                            "user_markdown": f"*{text}*",
                        },
                    }
                }
            ]
        }
    if mode == "user_message":
        return {
            "injectSteps": [
                {
                    "userMessage": f"[{text}]",
                }
            ]
        }
    if mode == "system_message":
        return {
            "injectSteps": [
                {
                    "systemMessage": {
                        "systemMessage": text,
                    }
                }
            ]
        }
    return {
        "injectSteps": [
            {
                "errorMessage": {
                    "userMessage": text,
                }
            }
        ]
    }


def handle_pre_invocation(payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    conv_id = str(payload.get("conversationId") or "default")
    transcript_path = payload.get("transcriptPath")
    invocation_num = payload.get("invocationNum")
    initial_num_steps = payload.get("initialNumSteps")

    state = load_state(conv_id)
    last_user, _ = read_transcript_tail(transcript_path)
    user_step_idx = last_user.get("step_index") if isinstance(last_user, dict) else None
    user_created_at = parse_iso_local(last_user.get("created_at")) if isinstance(last_user, dict) else None

    if state is None:
        is_new_turn = True
    elif (
        user_step_idx is not None
        and state.get("last_user_step_idx") is not None
        and user_step_idx > state["last_user_step_idx"]
    ):
        is_new_turn = True
    elif (
        invocation_num is not None
        and state.get("first_invocation_num") is not None
        and invocation_num <= state["first_invocation_num"]
        and (state.get("seen_post") or initial_num_steps != state.get("initial_num_steps"))
    ):
        is_new_turn = True
    else:
        is_new_turn = False

    first_inv_num = invocation_num
    if state is not None and state.get("first_invocation_num") is not None:
        if invocation_num is not None:
            first_inv_num = min(state["first_invocation_num"], invocation_num)
        else:
            first_inv_num = state["first_invocation_num"]

    if not is_new_turn:
        assert state is not None
        state["inv_start_iso"] = now.isoformat()
        state["first_invocation_num"] = first_inv_num
        if state.get("last_user_step_idx") is None and user_step_idx is not None:
            state["last_user_step_idx"] = user_step_idx
        save_state(conv_id, state)
        return {}

    prev_user_step_idx = state.get("last_user_step_idx") if state else None
    sent_dt = now
    if user_created_at is not None:
        is_fresh_transcript_user = (
            (prev_user_step_idx is not None and user_step_idx is not None and user_step_idx > prev_user_step_idx)
            or (prev_user_step_idx is None and abs((now - user_created_at).total_seconds()) < 3600)
        )
        if is_fresh_transcript_user:
            sent_dt = user_created_at

    new_state = {
        "last_user_step_idx": user_step_idx if user_step_idx is not None else prev_user_step_idx,
        "last_emitted_planner_step_idx": state.get("last_emitted_planner_step_idx") if state else None,
        "first_invocation_num": first_inv_num,
        "initial_num_steps": initial_num_steps,
        "turn_start_iso": now.isoformat(),
        "inv_start_iso": now.isoformat(),
        "seen_post": False,
    }
    save_state(conv_id, new_state)

    return make_timestamp_step(f"Sent {format_time(sent_dt, include_date=True)}")


def handle_post_invocation(payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    conv_id = str(payload.get("conversationId") or "default")
    transcript_path = payload.get("transcriptPath")

    state = load_state(conv_id) or {}
    state["seen_post"] = True

    last_user, last_planner = read_transcript_tail(transcript_path)
    if isinstance(last_user, dict) and last_user.get("step_index") is not None:
        state["last_user_step_idx"] = last_user["step_index"]

    if isinstance(last_planner, dict):
        planner_step_idx = last_planner.get("step_index")
        tool_calls = last_planner.get("tool_calls") or []
        if tool_calls:
            save_state(conv_id, state)
            return {}
        if planner_step_idx is not None and planner_step_idx == state.get("last_emitted_planner_step_idx"):
            save_state(conv_id, state)
            return {}
        if planner_step_idx is not None:
            state["last_emitted_planner_step_idx"] = planner_step_idx

    start_dt = parse_iso_local(state.get("turn_start_iso"))
    if start_dt is None and isinstance(last_planner, dict):
        start_dt = parse_iso_local(last_planner.get("created_at"))
    if start_dt is None:
        start_dt = now

    save_state(conv_id, state)

    crossed_day = start_dt.date() != now.date()
    start_str = format_time(start_dt, include_date=crossed_day)
    end_str = format_time(now, include_date=crossed_day)
    dur_str = format_duration(start_dt, now)

    return make_timestamp_step(f"Started {start_str} · Finished {end_str} ({dur_str})")


def _debug_log(entry: dict[str, Any]) -> None:
    if os.environ.get("AGY_TIMESTAMPS_DEBUG") != "1":
        return
    try:
        log_path = Path.home() / ".gemini" / "config" / "message-timestamps-debug.log"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        _debug_log({"error": "invalid_json", "raw": raw[:200]})
        sys.stdout.write("{}\n")
        return 0

    event = payload.get("hookEventName")
    now = datetime.now().astimezone()

    if event == "PreInvocation":
        result = handle_pre_invocation(payload, now)
    elif event == "PostInvocation":
        result = handle_post_invocation(payload, now)
    else:
        result = {}

    _debug_log(
        {
            "ts": now.isoformat(),
            "event": event,
            "conversationId": payload.get("conversationId"),
            "invocationNum": payload.get("invocationNum"),
            "initialNumSteps": payload.get("initialNumSteps"),
            "pluginData": os.environ.get("PLUGIN_DATA"),
            "stateDir": str(get_state_dir()),
            "result": result,
        }
    )

    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
