"""Unit tests for hooks/timestamps.py."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "hooks" / "timestamps.py"
STATUSLINE_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "statusline.py"


class TimestampsHookTest(unittest.TestCase):
    def _run_hook(self, payload: dict, data_dir: Path, extra_env: dict | None = None) -> dict:
        env = {"PATH": "/usr/bin:/bin", "PLUGIN_DATA": str(data_dir)}
        if extra_env:
            env.update(extra_env)
        res = subprocess.run(
            ["python3", str(SCRIPT)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True,
            env=env,
        )
        return json.loads(res.stdout)

    def test_multi_step_turn_default_error_message(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            tr = td_path / "transcript.jsonl"
            data = td_path / "data"

            tr.write_text(
                json.dumps({"step_index": 0, "type": "USER_INPUT", "created_at": "2026-11-23T07:25:00Z"}) + "\n",
                encoding="utf-8",
            )
            out1 = self._run_hook(
                {
                    "hookEventName": "PreInvocation",
                    "conversationId": "c1",
                    "invocationNum": 0,
                    "initialNumSteps": 1,
                    "transcriptPath": str(tr),
                },
                data,
            )
            em1 = out1["injectSteps"][0]["errorMessage"]
            self.assertTrue(em1["userMessage"].startswith("Sent "))

            with tr.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"step_index": 1, "type": "PLANNER_RESPONSE", "tool_calls": [{"name": "read_file"}]}) + "\n")
            out2 = self._run_hook(
                {
                    "hookEventName": "PostInvocation",
                    "conversationId": "c1",
                    "invocationNum": 0,
                    "initialNumSteps": 1,
                    "transcriptPath": str(tr),
                },
                data,
            )
            self.assertEqual(out2, {})

            out3 = self._run_hook(
                {
                    "hookEventName": "PreInvocation",
                    "conversationId": "c1",
                    "invocationNum": 1,
                    "initialNumSteps": 1,
                    "transcriptPath": str(tr),
                },
                data,
            )
            self.assertEqual(out3, {})

            with tr.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"step_index": 3, "type": "PLANNER_RESPONSE", "content": "All done!"}) + "\n")
            out4 = self._run_hook(
                {
                    "hookEventName": "PostInvocation",
                    "conversationId": "c1",
                    "invocationNum": 1,
                    "initialNumSteps": 1,
                    "transcriptPath": str(tr),
                },
                data,
            )
            em4 = out4["injectSteps"][0]["errorMessage"]
            self.assertIn("Started ", em4["userMessage"])
            self.assertIn("Finished ", em4["userMessage"])

            with tr.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"step_index": 5, "type": "USER_INPUT", "created_at": "2026-11-23T07:26:00Z"}) + "\n")
            out5 = self._run_hook(
                {
                    "hookEventName": "PreInvocation",
                    "conversationId": "c1",
                    "invocationNum": 0,
                    "initialNumSteps": 6,
                    "transcriptPath": str(tr),
                },
                data,
            )
            self.assertTrue(out5["injectSteps"][0]["errorMessage"]["userMessage"].startswith("Sent "))

    def test_opt_in_modes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            tr = td_path / "transcript.jsonl"
            data = td_path / "data"
            tr.write_text(
                json.dumps({"step_index": 0, "type": "USER_INPUT", "created_at": "2026-11-23T07:25:00Z"}) + "\n",
                encoding="utf-8",
            )
            out_md = self._run_hook(
                {
                    "hookEventName": "PreInvocation",
                    "conversationId": "c2",
                    "invocationNum": 0,
                    "initialNumSteps": 1,
                    "transcriptPath": str(tr),
                },
                data,
                extra_env={"AGY_TIMESTAMPS_MODE": "user_markdown"},
            )
            sm = out_md["injectSteps"][0]["systemMessage"]
            self.assertEqual(sm["systemMessage"], "")
            self.assertIn("user_markdown", sm["metadata"])

            out_um = self._run_hook(
                {
                    "hookEventName": "PreInvocation",
                    "conversationId": "c3",
                    "invocationNum": 0,
                    "initialNumSteps": 1,
                    "transcriptPath": str(tr),
                },
                data,
                extra_env={"AGY_TIMESTAMPS_MODE": "user_message"},
            )
            self.assertTrue(out_um["injectSteps"][0]["userMessage"].startswith("[Sent "))

    def test_statusline_reads_hook_state_and_transcript_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            tr = td_path / "transcript.jsonl"
            data = td_path / "data"

            tr.write_text(
                json.dumps({"step_index": 0, "type": "USER_INPUT", "created_at": "2026-11-23T07:25:00Z"}) + "\n",
                encoding="utf-8",
            )
            self._run_hook(
                {
                    "hookEventName": "PreInvocation",
                    "conversationId": "c-status",
                    "invocationNum": 0,
                    "initialNumSteps": 1,
                    "transcriptPath": str(tr),
                },
                data,
            )

            env = {
                "PATH": "/usr/bin:/bin",
                "AGY_TIMESTAMPS_STATE_DIR": str(data / "state"),
            }
            working = subprocess.run(
                ["python3", str(STATUSLINE_SCRIPT)],
                input=json.dumps(
                    {
                        "conversation_id": "c-status",
                        "agent_state": "working",
                        "cycle_mode": "auto",
                        "model": {"display_name": "Gemini 4 Neon (High)"},
                        "context_window": {"used_percentage": 12.4},
                    }
                ),
                text=True,
                capture_output=True,
                check=True,
                env=env,
            ).stdout
            self.assertIn("Sent", working)
            self.assertIn("Agent", working)
            self.assertIn("…", working)
            self.assertIn("Gemini 4 Neon (High)", working)

            with tr.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"step_index": 1, "type": "PLANNER_RESPONSE", "content": "Done"}) + "\n")
            self._run_hook(
                {
                    "hookEventName": "PostInvocation",
                    "conversationId": "c-status",
                    "invocationNum": 0,
                    "initialNumSteps": 1,
                    "transcriptPath": str(tr),
                },
                data,
            )

            idle = subprocess.run(
                ["python3", str(STATUSLINE_SCRIPT), "--timestamps-only"],
                input=json.dumps({"conversation_id": "c-status", "agent_state": "idle"}),
                text=True,
                capture_output=True,
                check=True,
                env=env,
            ).stdout
            self.assertIn("→", idle)
            self.assertNotIn("Gemini 4 Neon", idle)
            self.assertTrue(idle.strip().startswith("\x1b[2mSent"))


if __name__ == "__main__":
    unittest.main()
