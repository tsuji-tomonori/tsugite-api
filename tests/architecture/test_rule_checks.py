import json
from pathlib import Path

import pytest

from .case_text import is_japanese_case_text
from .dependencies import dependency_violations
from .model_artifacts import check_model_artifacts, manifest_errors
from .project import project_files
from .test_case_descriptions import case_functions
from .test_documents import japanese_title


def test_boundary_checker_rejects_cross_layer_imports():
    """各層の違反をインポートの別名・相対参照・完全修飾名でも行番号付きで報告する。"""
    cases = (
        ("packages/backend/src/app/main.py", "from agent import models as m", "モデル"),
        ("packages/database/migrations/env.py", "from app.main import app", "バックエンド"),
        (
            "packages/frontend/src/web_app/client.py",
            "from packages.database.src.tsugite_db import models",
            "データベース",
        ),
        ("packages/infra/app.py", "import agent.jobs as worker", "エージェント"),
        ("agent/jobs.py", "from .models import completion", "モデル"),
        ("agent/models/completion.py", "from .. import jobs", "エージェント"),
        ("agent/retrieval.py", "from web_app import chat_views", "フロント"),
        ("agent/retrieval.py", "import tools.build_chat", "開発ツール"),
        ("agent/models/runtime.py", "import aws_cdk", "インフラ"),
        ("tools/build_chat.py", "from packages.backend.tests import conftest", "テスト"),
    )
    for path, source, target in cases:
        errors = dependency_violations(Path(path), "\n" + source)
        assert len(errors) == 1, (path, source, errors)
        assert ":2:" in errors[0] and f"から{target}への依存" in errors[0]


def test_boundary_checker_accepts_supported_collaboration():
    """APIのジョブ受付、エージェントのガイド共有、モデル内の参照を許可する。"""
    for path, source in (
        ("packages/backend/src/app/main.py", "from agent import jobs"),
        ("agent/retrieval.py", "from packages.frontend.src.web_app.guide_content import GUIDES"),
        ("agent/models/completion.py", "from . import runtime"),
    ):
        assert dependency_violations(Path(path), source) == []


def test_new_package_requires_layer_rules():
    """所属する層を定義していない新規パッケージを検査対象から漏らさない。"""
    with pytest.raises(ValueError, match="新しいパッケージ"):
        dependency_violations(Path("packages/new/src/new/main.py"), "import os")


def test_document_checker_uses_title_outside_code_examples():
    """コード例の日本語を表題に数えず、例の後に続く日本語の表題を採用する。"""
    example = "````md\n# 見本の表題\n```\n# 見本の続き\n````\n"
    assert not japanese_title(example + "# API Reference\n")
    assert japanese_title(example + "# APIの使い方\n")


def test_project_discovery_includes_new_components(tmp_path):
    """新しい配下の文書と生成設計書を自動で検査し、ビルドの一時コピーを除外する。"""
    sources = ("agent/models/README.md", "docs/generated/apis/detail.md", "new/README.md")
    for name in (*sources, "build/vendor/README.md"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    assert {p.relative_to(tmp_path).as_posix() for p in project_files(tmp_path, ".md")} == set(sources)


def test_model_checker_rejects_unpinned_weight():
    """取得元が可変または重みのハッシュが不正なモデルについて両方の原因を報告する。"""
    weight = {"name": "model.onnx", "revision": "main", "sha256": "g" * 64}
    errors = manifest_errors({"decision": [weight]})
    assert len(errors) == 2
    assert all("decision/model.onnx" in message for message in errors)


def test_case_discovery_includes_async_class_methods(tmp_path):
    """クラス内の非同期テストも説明の検査対象に含め、補助関数を除く。"""
    path = tmp_path / "test_sample.py"
    path.write_text(
        "class TestExample:\n    async def test_case(self): pass\ndef helper(): pass\n", encoding="utf-8"
    )
    assert [node.name for node in case_functions(path)] == ["test_case"]


def test_case_explanation_requires_one_japanese_sentence():
    """正常な説明を受け付け、英語だけの説明・複数行・短すぎる説明を検出する。"""
    assert is_japanese_case_text("下書きを公開すると商品を一覧で確認できる。")
    for invalid in ("Only English text", "下書きを公開すると\n商品を一覧で確認できる。", "確認する"):
        assert not is_japanese_case_text(invalid), invalid


def test_model_distribution_requires_all_three_roles(tmp_path):
    """三つの役割がそろった配布物は通過し、一つでも定義が欠けると失敗する。"""
    item = {"name": "model.gguf", "revision": "abcd123", "sha256": "a" * 64}
    manifest = dict.fromkeys(("decision", "tool", "generate"), [item])
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    check_model_artifacts(tmp_path)
    del manifest["decision"]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(AssertionError, match="decision"):
        check_model_artifacts(tmp_path)
