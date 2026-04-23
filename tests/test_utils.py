from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import utils


class ApplyWriteOperationsTest(unittest.TestCase):
    def test_rejects_writes_outside_allowed_prefixes(self) -> None:
        with self.assertRaises(ValueError):
            utils.apply_write_operations(
                [
                    {
                        "path": "scripts/hack.py",
                        "operation": "write",
                        "content": "x",
                    }
                ]
            )

    def test_writes_and_appends_inside_vault_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            log_file = temp_root / "knowledge" / "log.md"

            with mock.patch.object(utils, "VAULT_DIR", temp_root), mock.patch.object(
                utils, "LOG_FILE", log_file
            ):
                utils.apply_write_operations(
                    [
                        {
                            "path": "knowledge/index.md",
                            "operation": "write",
                            "content": "# Index\n",
                        },
                        {
                            "path": "knowledge/log.md",
                            "operation": "append",
                            "content": "## entry\n",
                        },
                    ]
                )

                self.assertEqual(
                    (temp_root / "knowledge" / "index.md").read_text(encoding="utf-8"),
                    "# Index\n",
                )
                self.assertEqual(
                    log_file.read_text(encoding="utf-8"),
                    "# Build Log\n\n## entry\n",
                )


class SaveStateTest(unittest.TestCase):
    def test_creates_state_directory_for_external_vault(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            state_file = temp_root / ".memory-compiler" / "state.json"

            with mock.patch.object(utils, "STATE_FILE", state_file):
                utils.save_state({"query_count": 1})

            self.assertTrue(state_file.exists())
            self.assertEqual(
                state_file.read_text(encoding="utf-8"),
                '{\n  "query_count": 1\n}',
            )


if __name__ == "__main__":
    unittest.main()
