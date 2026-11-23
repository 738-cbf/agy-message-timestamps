#!/usr/bin/env python3
"""Antigravity CLI custom status line: turn sent/started/finished timestamps."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

DIM = "\x1b[2m"
RESET = "\x1b[0m"
CYAN = "\x1b[36m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"


def parse_iso_local(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        dt = datetime.fromisoformat(normalized)
        return dt.astimezone()
    except ValueError:
        return None


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


def load_hook_state(conversation_id: str) -> dict[str, Any] | None:
    if not conversation_id:
        return None
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", conversation_id)[:128]
    candidates = []
    override_dir = os.environ.get("AGY_TIMESTAMPS_STATE_DIR")
    if override_dir:
        candidates.append(Path(override_dir) / f"{safe}.json")
    candidates.extend(
        [
            Path.home() / ".gemini" / "antigravity-cli" / "plugin_data" / "message-timestamps" / "state" / f"{safe}.json",
            Path(__file__).resolve().parent.parent / ".state" / f"{safe}.json",
            Path(tempfile.gettempdir()) / "agy-message-timestamps-state" / f"{safe}.json",
        ]
    )
    for path in candidates:
        try:
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return None


def read_transcript_times(transcript_path: str | None) -> tuple[datetime | None, datetime | None]:
    """Fallback: return (last_user_dt, last_planner_dt) from transcript.jsonl."""
    if not transcript_path:
        return None, None
    path = Path(transcript_path)
    if not path.is_file():
        return None, None

    last_user_dt: datetime | None = None
    last_planner_dt: datetime | None = None
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
                    dt = parse_iso_local(entry.get("created_at"))
                    if dt is not None:
                        last_user_dt = dt
                        last_planner_dt = None
                elif step_type == "PLANNER_RESPONSE":
                    dt = parse_iso_local(entry.get("created_at"))
                    if dt is not None:
                        last_planner_dt = dt
    except OSError:
        return None, None

    return last_user_dt, last_planner_dt


def render_status_line(payload: dict[str, Any], now: datetime, timestamps_only: bool = False) -> str:
    conv_id = str(payload.get("conversation_id") or payload.get("session_id") or "")
    transcript_path = payload.get("transcript_path")
    agent_state = str(payload.get("agent_state") or "idle")
    width = payload.get("terminal_width") or 120

    state = load_hook_state(conv_id) or {}
    sent_dt = parse_iso_local(state.get("sent_iso"))
    start_dt = parse_iso_local(state.get("turn_start_iso"))
    finish_dt = parse_iso_local(state.get("turn_finish_iso"))

    if sent_dt is None and start_dt is None:
        tr_user_dt, tr_planner_dt = read_transcript_times(transcript_path)
        sent_dt = tr_user_dt
        start_dt = tr_user_dt
        if agent_state == "idle":
            finish_dt = tr_planner_dt

    sep = f" {DIM}·{RESET} "
    time_parts = []

    if sent_dt is not None:
        include_date = sent_dt.date() != now.date()
        time_parts.append(f"{DIM}Sent{RESET} {CYAN}{format_time(sent_dt, include_date=include_date)}{RESET}")

    active_states = {"working", "tool_use", "reviewing", "initializing"}
    if start_dt is not None:
        if agent_state in active_states or finish_dt is None:
            elapsed = format_duration(start_dt, now)
            time_parts.append(
                f"{DIM}Agent{RESET} {YELLOW}{format_time(start_dt)} … ({elapsed}){RESET}"
            )
        else:
            crossed_day = start_dt.date() != finish_dt.date()
            dur = format_duration(start_dt, finish_dt)
            time_parts.append(
                f"{DIM}Agent{RESET} {GREEN}{format_time(start_dt, include_date=crossed_day)} → "
                f"{format_time(finish_dt, include_date=crossed_day)}{RESET} {DIM}({dur}){RESET}"
            )

    if isinstance(width, int) and width > 0 and width < 80 and len(time_parts) == 2:
        if sent_dt is not None and start_dt is not None and abs((start_dt - sent_dt).total_seconds()) < 2:
            time_parts.pop(0)

    meta = []
    if not timestamps_only:
        cycle_mode = payload.get("cycle_mode")
        if cycle_mode:
            meta.append(f"{YELLOW}{cycle_mode}{RESET}")
        model = payload.get("model")
        if isinstance(model, dict):
            display_name = model.get("display_name") or model.get("id")
            if display_name:
                meta.append(f"{DIM}{display_name}{RESET}")
        ctx = payload.get("context_window")
        if isinstance(ctx, dict) and ctx.get("used_percentage") is not None:
            pct = float(ctx["used_percentage"])
            if pct > 0:
                meta.append(f"{DIM}{pct:.0f}% ctx{RESET}")

    left = sep.join(time_parts)
    right = sep.join(meta)
    if left and right:
        return f"{left} {DIM}│{RESET} {right}"
    return left or right


def main() -> int:
    timestamps_only = "--timestamps-only" in sys.argv[1:]
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    now = datetime.now().astimezone()
    sys.stdout.write(render_status_line(payload, now, timestamps_only=timestamps_only) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
