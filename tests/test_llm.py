from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import llm
from llm import _build_exec_prompt, _extract_exec_error, _parse_exec_output, _resolve_model


class BuildExecPromptTest(unittest.TestCase):
    def test_build_exec_prompt_without_instructions(self) -> None:
        self.assertEqual(_build_exec_prompt("hello"), "hello")

    def test_build_exec_prompt_with_instructions(self) -> None:
        prompt = _build_exec_prompt("Do the task.", instructions="Be precise.")
        self.assertIn("Be precise.", prompt)
        self.assertIn("## Task", prompt)
        self.assertIn("Do the task.", prompt)


class ParseExecOutputTest(unittest.TestCase):
    def test_extracts_last_agent_message_usage_and_thread(self) -> None:
        stdout = "\n".join(
            [
                json.dumps(
                    {
                        "type": "thread.started",
                        "thread_id": "thread-123",
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "agent_message",
                            "text": "first",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "agent_message",
                            "text": "final message",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 11,
                            "cached_input_tokens": 3,
                            "output_tokens": 7,
                        },
                    }
                ),
            ]
        )

        text, usage, thread_id = _parse_exec_output(stdout)

        self.assertEqual(text, "final message")
        self.assertEqual(thread_id, "thread-123")
        self.assertEqual(usage.input_tokens, 11)
        self.assertEqual(usage.cached_input_tokens, 3)
        self.assertEqual(usage.output_tokens, 7)
        self.assertEqual(usage.total_tokens, 18)

    def test_extracts_assistant_message_from_response_item_shape(self) -> None:
        stdout = "\n".join(
            [
                json.dumps(
                    {
                        "type": "thread.started",
                        "thread_id": "thread-456",
                    }
                ),
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "new shape"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 5,
                            "output_tokens": 2,
                        },
                    }
                ),
            ]
        )

        text, usage, thread_id = _parse_exec_output(stdout)

        self.assertEqual(text, "new shape")
        self.assertEqual(thread_id, "thread-456")
        self.assertEqual(usage.total_tokens, 7)


class ExtractExecErrorTest(unittest.TestCase):
    def test_prefers_structured_error_message(self) -> None:
        stdout = "\n".join(
            [
                json.dumps({"type": "thread.started", "thread_id": "t"}),
                json.dumps(
                    {
                        "type": "error",
                        "message": "You've hit your usage limit.",
                    }
                ),
            ]
        )

        self.assertEqual(
            _extract_exec_error(stdout, ""),
            "You've hit your usage limit.",
        )


class ResolveModelTest(unittest.TestCase):
    def test_ignores_stale_repo_default_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text('model = "gpt-5.4"\n', encoding="utf-8")

            with mock.patch.object(llm, "CODEX_CONFIG_FILE", config_path), mock.patch.dict(
                "os.environ",
                {},
                clear=True,
            ):
                self.assertEqual(_resolve_model(), "gpt-5.5")

    def test_honors_explicit_env_model(self) -> None:
        with mock.patch.dict("os.environ", {"CODEX_MODEL": "gpt-5.4"}, clear=True):
            self.assertEqual(_resolve_model(), "gpt-5.4")


if __name__ == "__main__":
    unittest.main()
