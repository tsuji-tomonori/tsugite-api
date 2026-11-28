# リポジトリ内のソースと文書を配布物・キャッシュを除いて列挙する。
"""リポジトリ内のソースと文書を配布物・キャッシュを除いて列挙する。"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXCLUDED = {
    ".git",
    ".codex-fetch",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    "__pycache__",
    "node_modules",
    "dist",
    "cdk.out",
    "artifacts",
    "build",
}


def project_files(root, suffix):
    for directory, folders, names in os.walk(root):
        folders[:] = sorted(
            name for name in folders if name not in EXCLUDED and not name.endswith(".egg-info")
        )
        for name in sorted(names):
            if name.lower().endswith(suffix):
                yield Path(directory, name)
