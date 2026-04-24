from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPILE_PATH = ROOT / "scripts" / "compile.py"
sys.path.insert(0, str(ROOT / "scripts"))


def load_compile_module():
    spec = importlib.util.spec_from_file_location("compile_test_module", COMPILE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load compile module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compile_module = load_compile_module()


class FlushErrorFilteringTest(unittest.TestCase):
    def test_filters_flush_error_entries(self) -> None:
        content = """# Daily Log: 2026-04-24

## Sessions

## Memory Maintenance

### Memory Flush (23:38)

FLUSH_ERROR: RuntimeError: usage limit

### Session (23:50)

**Context:** durable note
"""

        filtered = compile_module.strip_flush_error_entries(content)

        self.assertNotIn("FLUSH_ERROR", filtered)
        self.assertIn("durable note", filtered)
        self.assertTrue(compile_module.has_compilable_entries(content))

    def test_detects_log_with_only_flush_errors_as_not_compilable(self) -> None:
        content = """# Daily Log: 2026-04-24

## Sessions

## Memory Maintenance

### Memory Flush (23:38)

FLUSH_ERROR: RuntimeError: usage limit
"""

        self.assertFalse(compile_module.has_compilable_entries(content))


if __name__ == "__main__":
    unittest.main()
