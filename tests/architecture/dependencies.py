"""配布単位間のPython依存を構文木から検査する。"""

import ast
from importlib.util import resolve_name

# モデルはエージェントと別のLambdaとして配布するため、長い接頭辞から判定する。
MODULES = {
    "agent.models": "モデル",
    "agent": "エージェント",
    "app": "バックエンド",
    "tsugite_db": "データベース",
    "web_app": "フロント",
    "src": "インフラ",
    "sample_api": "サンプルAPI",
    "tools": "開発ツール",
    "tests": "テスト",
}
PACKAGE_MODULES = {
    "agent": "agent",
    "backend": "app",
    "database": "tsugite_db",
    "frontend": "web_app",
    "infra": "src",
    "sample_api": "sample_api",
}
# SDKの境界も検査し、画面でのDB接続や実行用コードへのCDKの混入を検出する。
LIBRARIES = {
    "sqlalchemy": "データベース",
    "alembic": "データベース",
    "fastapi": "HTTPフレームワーク",
    "aws_cdk": "インフラ",
    "constructs": "インフラ",
    "js": "フロント",
    "pyodide": "フロント",
    "puepy": "フロント",
    "onnxruntime": "モデル",
    "tokenizers": "モデル",
}
ALLOWED = {
    "バックエンド": {"データベース", "エージェント", "HTTPフレームワーク"},
    "サンプルAPI": {"HTTPフレームワーク"},
    "データベース": set(),
    "フロント": set(),
    "インフラ": set(),
    "モデル": set(),
    "エージェント": {"バックエンド", "データベース"},
    "開発ツール": {
        "サンプルAPI",
        "HTTPフレームワーク",
        "バックエンド",
        "データベース",
        "フロント",
        "インフラ",
        "エージェント",
        "モデル",
    },
}


def canonical(module):
    parts = module.split(".")
    if len(parts) >= 2 and parts[0] == "packages" and parts[1] in PACKAGE_MODULES:
        prefix = PACKAGE_MODULES[parts[1]]
        tail = parts[2:]
        if tail[:1] == ["tests"]:
            return ".".join(tail)
        if prefix == "src" and tail[:1] == ["src"]:
            return ".".join(tail)
        if tail[:2] == ["src", prefix]:
            tail = tail[2:]
        return ".".join((prefix, *tail))
    return module


def layer(module):
    for prefix, owner in MODULES.items():
        if module == prefix or module.startswith(prefix + "."):
            return owner
    return LIBRARIES.get(module.partition(".")[0])


def dependencies(tree, package):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, canonical(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = resolve_name("." * node.level + (node.module or ""), package)
            for alias in node.names:
                yield node.lineno, canonical(f"{base}.{alias.name}")


def source_module(path):
    parts = path.with_suffix("").parts
    if parts[0] == "packages":
        if len(parts) < 3 or parts[1] not in PACKAGE_MODULES:
            raise ValueError(f"{path}: 新しいパッケージの依存規則を定義してください")
        if parts[2] == "src":
            return canonical(".".join(parts))
        # CDKの起動スクリプトやAlembicの移行も所属パッケージの規則で検査する。
        return ".".join((PACKAGE_MODULES[parts[1]], *parts[2:]))
    return ".".join(parts)


def dependency_violations(path, source):
    module = source_module(path)
    owner = layer(module)
    if owner not in ALLOWED:
        raise ValueError(f"{path}: 実装の所属層を特定できません")
    errors = []
    for line, imported in dependencies(ast.parse(source, filename=str(path)), module.rpartition(".")[0]):
        target = layer(imported)
        if target is None or target == owner or target in ALLOWED[owner]:
            continue
        if module == "app.integrations.upstream" and imported in {
            "sample_api.main.app",
            "sample_api.main.PRODUCTS",
        }:
            continue  # ローカルでのみ同じFastAPIアプリを呼ぶ。
        # チャット検索だけがブラウザーに依存しないガイド本文と検索関数を共有する。
        if module == "agent.retrieval" and imported.split(".")[:2] in (
            ["web_app", "guide_content"],
            ["web_app", "guide_search"],
        ):
            continue
        errors.append(f"{path}:{line}: {owner}から{target}への依存 {imported}")
    return errors
