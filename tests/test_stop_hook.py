from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOP_HOOK_PATH = ROOT / "hooks" / "stop.py"


def load_stop_hook_module():
    spec = importlib.util.spec_from_file_location("stop_hook_test_module", STOP_HOOK_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load stop hook module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


stop_hook = load_stop_hook_module()


class ExtractConversationContextTest(unittest.TestCase):
    def write_jsonl(self, entries: list[dict]) -> Path:
        temp = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".jsonl",
            delete=False,
        )
        with temp:
            for entry in entries:
                temp.write(json.dumps(entry) + "\n")
        return Path(temp.name)

    def test_extracts_current_codex_response_item_messages(self) -> None:
        transcript = self.write_jsonl(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "developer",
                        "content": [{"type": "input_text", "text": "developer context"}],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "# AGENTS.md instructions for /repo\n"
                                    "<environment_context>...</environment_context>"
                                ),
                            }
                        ],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "actual user request"}],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "assistant answer"}],
                    },
                },
            ]
        )

        try:
            context, turn_count = stop_hook.extract_conversation_context(transcript)
        finally:
            transcript.unlink(missing_ok=True)

        self.assertEqual(turn_count, 2)
        self.assertIn("**User:** actual user request", context)
        self.assertIn("**Assistant:** assistant answer", context)
        self.assertNotIn("AGENTS.md instructions", context)
        self.assertNotIn("developer context", context)

    def test_keeps_legacy_message_shapes(self) -> None:
        transcript = self.write_jsonl(
            [
                {
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": "legacy user"}],
                    }
                },
                {"role": "assistant", "content": "legacy assistant"},
            ]
        )

        try:
            context, turn_count = stop_hook.extract_conversation_context(transcript)
        finally:
            transcript.unlink(missing_ok=True)

        self.assertEqual(turn_count, 2)
        self.assertIn("legacy user", context)
        self.assertIn("legacy assistant", context)

    def test_keeps_last_user_when_assistant_updates_fill_recent_window(self) -> None:
        entries = [
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "root request"}],
                },
            }
        ]
        for index in range(stop_hook.MAX_TURNS + 2):
            entries.append(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": f"update {index}"}],
                    },
                }
            )
        transcript = self.write_jsonl(entries)

        try:
            context, turn_count = stop_hook.extract_conversation_context(transcript)
        finally:
            transcript.unlink(missing_ok=True)

        self.assertEqual(turn_count, stop_hook.MAX_TURNS)
        self.assertIn("root request", context)
        self.assertIn("update 9", context)


class HookInputHelpersTest(unittest.TestCase):
    def test_resolves_alternate_transcript_path_keys(self) -> None:
        self.assertEqual(
            stop_hook._resolve_transcript_path({"transcriptPath": "/tmp/session.jsonl"}),
            "/tmp/session.jsonl",
        )

    def test_sanitizes_context_file_components(self) -> None:
        self.assertEqual(stop_hook._safe_filename_component("../session:1"), "session_1")


if __name__ == "__main__":
    unittest.main()
