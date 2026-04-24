from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import install_repo_hooks


class EnsureCodexDirTest(unittest.TestCase):
    def test_replaces_empty_placeholder_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            placeholder = repo / ".codex"
            placeholder.write_text("", encoding="utf-8")

            codex_dir = install_repo_hooks.ensure_codex_dir(repo)

            self.assertTrue(codex_dir.is_dir())
            self.assertEqual(codex_dir, placeholder)

    def test_rejects_non_empty_placeholder_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            placeholder = repo / ".codex"
            placeholder.write_text("legacy", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                install_repo_hooks.ensure_codex_dir(repo)


class BuildHooksJsonTest(unittest.TestCase):
    def test_embeds_project_root_env_and_absolute_hook_paths(self) -> None:
        repo = Path("/tmp/example-repo")

        payload = install_repo_hooks.build_hooks_json(repo)

        self.assertIn("KB_PROJECT_ROOT=/tmp/example-repo", payload)
        self.assertIn(str(install_repo_hooks.SESSION_START_SCRIPT), payload)
        self.assertIn(str(install_repo_hooks.STOP_SCRIPT), payload)


class LoadDefaultModelSettingsTest(unittest.TestCase):
    def test_ignores_stale_compiler_config_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                'model = "gpt-5.4"\nmodel_reasoning_effort = "xhigh"\n',
                encoding="utf-8",
            )

            with mock.patch.object(
                install_repo_hooks,
                "COMPILER_CONFIG",
                config_path,
            ), mock.patch.dict("os.environ", {}, clear=True):
                self.assertEqual(
                    install_repo_hooks.load_default_model_settings(),
                    ("gpt-5.5", "xhigh"),
                )


if __name__ == "__main__":
    unittest.main()
