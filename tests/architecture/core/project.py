"""リポジトリ内のソースと文書を配布物・キャッシュを除いて列挙する。"""

import ast
import os
from pathlib import Path

from .case_text import KANA

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


def has_japanese_module_docstring(source):
    """ファイルの冒頭に三重の二重引用符で日本語の説明を一つだけ記述したかを判定する。"""
    if source.startswith("#!"):
        source = source.partition("\n")[2]
    if not source.startswith('"""'):
        return False
    module = ast.parse(source)
    purpose = ast.get_docstring(module) or ""
    descriptions = [line for line in purpose.splitlines() if line.strip()]
    if not descriptions or not all(KANA.search(line) for line in descriptions):
        return False
    return not (
        len(module.body) > 1
        and isinstance(module.body[1], ast.Expr)
        and isinstance(module.body[1].value, ast.Constant)
        and isinstance(module.body[1].value.value, str)
    )
