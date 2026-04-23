"""Install repo-local Codex hook files that point back to this compiler repo."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import tomllib
from pathlib import Path

COMPILER_ROOT = Path(__file__).resolve().parent.parent
COMPILER_CONFIG = COMPILER_ROOT / ".codex" / "config.toml"
SESSION_START_SCRIPT = COMPILER_ROOT / "hooks" / "session-start.py"
STOP_SCRIPT = COMPILER_ROOT / "hooks" / "stop.py"


def load_default_model_settings() -> tuple[str, str]:
    """Reuse the compiler repo's default Codex model settings."""
    model = "gpt-5.4"
    reasoning = "medium"

    if not COMPILER_CONFIG.exists():
        return model, reasoning

    config = tomllib.loads(COMPILER_CONFIG.read_text(encoding="utf-8"))
    loaded_model = config.get("model")
    loaded_reasoning = config.get("model_reasoning_effort")
    if isinstance(loaded_model, str) and loaded_model.strip():
        model = loaded_model.strip()
    if isinstance(loaded_reasoning, str) and loaded_reasoning.strip():
        reasoning = loaded_reasoning.strip()
    return model, reasoning


def git_root(path: Path) -> Path | None:
    """Return the git root if the path belongs to a repository."""
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    stdout = result.stdout.strip()
    if not stdout:
        return None
    return Path(stdout).resolve()


def discover_git_repos(parent: Path) -> list[Path]:
    """Find immediate child directories that are git roots."""
    repos: list[Path] = []
    if not parent.is_dir():
        raise FileNotFoundError(f"Parent directory not found: {parent}")

    for child in sorted(parent.iterdir()):
        if not child.is_dir():
            continue
        root = git_root(child)
        if root and root == child.resolve():
            repos.append(root)
    return repos


def ensure_codex_dir(repo: Path) -> Path:
    """Create `.codex/`, replacing an old empty placeholder file if needed."""
    codex_path = repo / ".codex"
    if codex_path.exists() and codex_path.is_file():
        if codex_path.stat().st_size != 0:
            raise RuntimeError(
                f"Refusing to replace non-empty file: {codex_path}. "
                "Move it away manually and run the installer again."
            )
        codex_path.unlink()

    codex_path.mkdir(parents=True, exist_ok=True)
    return codex_path


def build_config_text(model: str, reasoning: str) -> str:
    return (
        f'model = "{model}"\n'
        f'model_reasoning_effort = "{reasoning}"\n\n'
        "[features]\n"
        "codex_hooks = true\n"
    )


def build_hooks_json(repo: Path) -> str:
    project_root = shlex.quote(str(repo))
    session_start = (
        f"env KB_PROJECT_ROOT={project_root} python3 "
        f"{shlex.quote(str(SESSION_START_SCRIPT))}"
    )
    stop = (
        f"env KB_PROJECT_ROOT={project_root} python3 "
        f"{shlex.quote(str(STOP_SCRIPT))}"
    )

    payload = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup|resume",
                    "hooks": [
                        {
                            "type": "command",
                            "command": session_start,
                            "timeout": 15,
                            "statusMessage": "Loading knowledge base context",
                        }
                    ],
                }
            ],
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": stop,
                            "timeout": 15,
                            "statusMessage": "Extracting durable memory",
                        }
                    ],
                }
            ],
        }
    }
    return json.dumps(payload, indent=2, ensure_ascii=True) + "\n"


def write_if_changed(path: Path, content: str) -> bool:
    """Write UTF-8 text only when the file content actually changes."""
    existing = None
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return False

    path.write_text(content, encoding="utf-8")
    return True


def install_repo(
    repo: Path,
    *,
    model: str,
    reasoning: str,
    vault_path: Path | None,
) -> dict[str, str]:
    """Install `.codex` files for one repo."""
    if not repo.is_dir():
        raise FileNotFoundError(f"Repo path not found: {repo}")

    codex_dir = ensure_codex_dir(repo)

    changes: dict[str, str] = {}
    config_path = codex_dir / "config.toml"
    if write_if_changed(config_path, build_config_text(model, reasoning)):
        changes[str(config_path)] = "updated"

    hooks_path = codex_dir / "hooks.json"
    if write_if_changed(hooks_path, build_hooks_json(repo)):
        changes[str(hooks_path)] = "updated"

    if vault_path is not None:
        vault_file = codex_dir / "vault.local"
        if write_if_changed(vault_file, f"{vault_path}\n"):
            changes[str(vault_file)] = "updated"

    return changes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Install repo-local Codex hook config that points back to this memory "
            "compiler repository."
        )
    )
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        help="Repository root to configure. May be passed multiple times.",
    )
    parser.add_argument(
        "--scan-dir",
        action="append",
        default=[],
        help="Scan immediate child directories and configure every git repo found.",
    )
    parser.add_argument(
        "--vault",
        help=(
            "Shared vault path to write into each repo's .codex/vault.local. "
            "If omitted, repos keep their default local knowledge/ directory."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    repo_paths: set[Path] = set()
    for raw in args.repo:
        path = Path(raw).expanduser().resolve()
        root = git_root(path)
        repo_paths.add(root or path)

    for raw in args.scan_dir:
        path = Path(raw).expanduser().resolve()
        repo_paths.update(discover_git_repos(path))

    repos = sorted(repo_paths)
    if not repos:
        raise SystemExit("No repositories selected. Use --repo and/or --scan-dir.")

    vault_path = Path(args.vault).expanduser().resolve() if args.vault else None
    model, reasoning = load_default_model_settings()

    print(f"Compiler root: {COMPILER_ROOT}")
    print(f"Installing hook config into {len(repos)} repos")
    if vault_path:
        print(f"Shared vault: {vault_path}")
    print()

    changed_files = 0
    for repo in repos:
        changes = install_repo(
            repo,
            model=model,
            reasoning=reasoning,
            vault_path=vault_path,
        )
        print(repo)
        if changes:
            for path in sorted(changes):
                print(f"  - {changes[path]} {path}")
                changed_files += 1
        else:
            print("  - no changes")

    print()
    print(f"Done. Changed files: {changed_files}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
