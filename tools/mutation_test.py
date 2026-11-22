"""代表的な回帰を注入し、ローカルの単体テストが検出するか確かめる。"""

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Mutation:
    layer: str
    name: str
    source: str
    before: str
    after: str
    test: str


MUTATIONS = (
    Mutation(
        "ci",
        "ファイル移動時に移動元の変更を見落とす",
        "tools/ci_scope.py",
        '"--no-renames"',
        '"--find-renames"',
        "tools/tests/test_ci_scope.py::test_git_diff_includes_deleted_and_both_renamed_paths",
    ),
    Mutation(
        "ci",
        "以前の実行行を含むテスト層の再計測を省く",
        "tools/ci_scope.py",
        '("coverage_source" in flags and part.stat().st_size)',
        "False",
        "tools/tests/test_ci_scope.py::test_measured_source_invalidates_suites_that_executed_it",
    ),
    Mutation(
        "tools",
        "既存要件の編集だけでfeatブランチを許可する",
        "tools/requirements.py",
        '"--diff-filter=A"',
        '"--diff-filter=AM"',
        "tools/tests/test_requirements.py::test_feature_requires_added_requirement",
    ),
    Mutation(
        "tools",
        "未定義の用語を要件の見出しで許可する",
        "tools/requirements.py",
        "if unknown:",
        "if False:",
        "tools/tests/test_requirements.py::test_undefined_term_in_condition_or_result_fails",
    ),
    Mutation(
        "backend",
        "設計項目の直前の和名コメントを読み飛ばす",
        "packages/database/src/tsugite_db/source_docs.py",
        "self.comments.get(node.lineno - 1",
        "self.comments.get(node.lineno - 2",
        "packages/backend/tests/architecture/test_design_sources.py::"
        "test_schema_field_uses_only_the_comment_on_its_declaration",
    ),
    Mutation(
        "backend",
        "設計解析に別名で正規表現を取り込む",
        "packages/backend/src/app/design_names.py",
        "import inspect",
        "import inspect\nimport re as parser",
        "packages/backend/tests/architecture/test_design_sources.py::"
        "test_design_analysis_uses_only_python_sources_and_syntax_trees",
    ),
    Mutation(
        "backend",
        "JSON Pointerのスラッシュ展開を壊す",
        "packages/backend/src/app/core/openapi.py",
        'part.replace("~1", "/")',
        'part.replace("~1", "-")',
        "packages/backend/tests/test_openapi.py::test_resolves_path_item_references_in_order",
    ),
    Mutation(
        "backend",
        "OpenAPIの拡張項目を通常パスとして扱う",
        "packages/backend/src/app/core/openapi.py",
        'if not path.startswith("/"):',
        'if path.startswith("x-disabled"):',
        "packages/backend/tests/test_openapi.py::test_skips_invalid_path_item_without_losing_valid_paths",
    ),
    Mutation(
        "backend",
        "Aurora DSQLの接続をシステムCA参照に戻す",
        "packages/database/src/tsugite_db/session.py",
        "sslrootcert=certifi.where(),",
        'sslrootcert="system",',
        "packages/database/tests/test_session.py::test_dsql_uses_a_bundled_ca_for_full_tls_verification",
    ),
    Mutation(
        "backend",
        "Aurora DSQLの接続でホスト名を検証しない",
        "packages/database/src/tsugite_db/session.py",
        'sslmode="verify-full",',
        'sslmode="require",',
        "packages/database/tests/test_session.py::test_dsql_uses_a_bundled_ca_for_full_tls_verification",
    ),
    Mutation(
        "frontend",
        "操作側のパラメーターをパス側の定義で上書きする",
        "packages/frontend/src/web_app/openapi_fields.py",
        "for source in (item, operation):",
        "for source in (operation, item):",
        "packages/frontend/tests/test_openapi_fields.py::"
        "test_operation_overrides_path_parameter_and_resolves_pointer",
    ),
    Mutation(
        "frontend",
        "ガイドの条件をクリアした後にフォーカスを戻さない",
        "packages/frontend/src/web_app/guide_views.py",
        '        document.getElementById("guide-query").focus()\n',
        "",
        "packages/frontend/tests/test_components.py::test_guide_reset_restores_role_and_keyboard_focus",
    ),
    Mutation(
        "infra",
        "Lambdaの割当メモリーを増やす",
        "packages/infra/src/infra_app/functions.py",
        "memory_size=768,",
        "memory_size=1024,",
        "packages/infra/tests/test_cost.py::test_cost_drivers_are_bounded",
    ),
    Mutation(
        "infra",
        "リソースの管理者タグの値を誤る",
        "packages/infra/src/infra_app/ownership.py",
        '"ManagedBy": "AWS-CDK"',
        '"ManagedBy": "Other"',
        "packages/infra/tests/test_stack.py::test_every_resource_has_ownership",
    ),
    Mutation(
        "infra",
        "ポータルURLのスタック出力名を変更する",
        "packages/infra/src/infra_app/stack.py",
        'CfnOutput(self, "PortalUrl",',
        'CfnOutput(self, "ChangedPortalUrl",',
        "packages/infra/tests/test_cdk_regression.py::test_cloudformation_structure_matches_snapshot",
    ),
)


def copy_sources(workspace):
    ignore = shutil.ignore_patterns("dist", "cdk.out", ".venv", "__pycache__", "*.egg-info")
    for folder in ("packages", "contracts", "tests", "tools"):
        shutil.copytree(ROOT / folder, workspace / folder, ignore=ignore)
    for file in ("conftest.py", "pyproject.toml"):
        shutil.copyfile(ROOT / file, workspace / file)


def run_test(workspace, target):
    report = workspace / "mutation-test.xml"
    report.unlink(missing_ok=True)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", f"--junitxml={report}", target],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    cases = list(ElementTree.parse(report).iter("testcase")) if report.exists() else []
    return result, cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layer", choices=("backend", "frontend", "infra", "tools"), action="append")
    args = parser.parse_args()
    selected = [entry for entry in MUTATIONS if not args.layer or entry.layer in args.layer]
    failed = []
    with TemporaryDirectory(prefix="tsugite-mutation-") as directory:
        workspace = Path(directory)
        copy_sources(workspace)
        for mutation in selected:
            baseline, cases = run_test(workspace, mutation.test)
            if (
                baseline.returncode
                or not cases
                or any(case.find("skipped") is not None for case in cases)
            ):
                print(baseline.stdout + baseline.stderr, file=sys.stderr)
                failed.append(f"{mutation.name}（基準テストが成功しなかった）")
                continue
            path = workspace / mutation.source
            source = path.read_text(encoding="utf-8")
            if source.count(mutation.before) != 1:
                failed.append(f"{mutation.name}（変更対象を特定できなかった）")
                continue
            path.write_text(source.replace(mutation.before, mutation.after, 1), encoding="utf-8")
            try:
                result, cases = run_test(workspace, mutation.test)
            finally:
                path.write_text(source, encoding="utf-8")
            errors = any(case.find("error") is not None for case in cases)
            failures = any(case.find("failure") is not None for case in cases)
            if result.returncode == 1 and failures and not errors:
                print(f"検出: {mutation.layer} / {mutation.name}", flush=True)
            else:
                print(result.stdout + result.stderr, file=sys.stderr)
                failed.append(f"{mutation.name}（対象テストの失敗で検出できなかった）")
    print(f"{len(selected) - len(failed)}/{len(selected)} 件の変更を検出")
    for failure in failed:
        print(failure, file=sys.stderr)
    return int(bool(failed))


if __name__ == "__main__":
    sys.exit(main())
