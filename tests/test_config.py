from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "scripts" / "config.py"


def load_config_module(module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, CONFIG_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load config module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConfigProjectRootTest(unittest.TestCase):
    def test_project_root_env_changes_vault_local_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            codex_dir = project_root / ".codex"
            codex_dir.mkdir(parents=True)
            (codex_dir / "vault.local").write_text("shared-vault\n", encoding="utf-8")

            with mock.patch.dict(
                os.environ,
                {"KB_PROJECT_ROOT": str(project_root)},
                clear=False,
            ):
                module = load_config_module("config_test_project_root")

            self.assertEqual(module.PROJECT_ROOT, project_root)
            self.assertEqual(module.VAULT_OVERRIDE_FILE, codex_dir / "vault.local")
            self.assertEqual(module.VAULT_DIR, project_root / "shared-vault")


if __name__ == "__main__":
    unittest.main()
