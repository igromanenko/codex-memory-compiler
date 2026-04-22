from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from llm import _build_exec_prompt, _extract_exec_error, _parse_exec_output


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


if __name__ == "__main__":
    unittest.main()
