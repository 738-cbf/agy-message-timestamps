"""Unit tests for hooks/timestamps.py."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "hooks" / "timestamps.py"


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

    def test_multi_step_turn_default_plain_system_message(self) -> None:
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
            sm1 = out1["injectSteps"][0]["systemMessage"]
            self.assertNotIn("metadata", sm1)
            self.assertTrue(sm1["systemMessage"].startswith("Sent "))

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
            sm4 = out4["injectSteps"][0]["systemMessage"]
            self.assertNotIn("metadata", sm4)
            self.assertIn("Started ", sm4["systemMessage"])
            self.assertIn("Finished ", sm4["systemMessage"])

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
            self.assertTrue(out5["injectSteps"][0]["systemMessage"]["systemMessage"].startswith("Sent "))

    def test_opt_in_user_markdown_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            tr = td_path / "transcript.jsonl"
            data = td_path / "data"
            tr.write_text(
                json.dumps({"step_index": 0, "type": "USER_INPUT", "created_at": "2026-11-23T07:25:00Z"}) + "\n",
                encoding="utf-8",
            )
            out = self._run_hook(
                {
                    "hookEventName": "PreInvocation",
                    "conversationId": "c2",
                    "invocationNum": 0,
                    "initialNumSteps": 1,
                    "transcriptPath": str(tr),
                },
                data,
                extra_env={"AGY_TIMESTAMPS_USE_USER_MARKDOWN": "1"},
            )
            sm = out["injectSteps"][0]["systemMessage"]
            self.assertEqual(sm["systemMessage"], "")
            self.assertIn("user_markdown", sm["metadata"])


if __name__ == "__main__":
    unittest.main()
