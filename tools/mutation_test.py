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
        "evidence",
        "実行結果のない要件を合格にする",
        "tools/requirement_evidence.py",
        'statuses.append("未実行")',
        'statuses.append("成功")',
        "tools/tests/test_requirement_evidence.py::test_unexecuted_requirement_fails",
    ),
    Mutation(
        "evidence",
        "スキップを成功にする",
        "tools/requirement_evidence.py",
        '("skipped", "スキップ")',
        '("skipped", "成功")',
        "tools/tests/test_requirement_evidence.py::test_skipped_requirement_fails",
    ),
    Mutation(
        "infra-docs",
        "パラメーターシートから配列の添字を落とす",
        "tools/design/infrastructure.py",
        'settings(f"{path}[{index}]", item)',
        "settings(path, item)",
        "tools/tests/test_infrastructure_docs.py::test_component_parameter_sheet",
    ),
    Mutation(
        "backend",
        "データ修正を要する障害を通常のサーバーエラーと記録する",
        "packages/backend/src/app/core/log_record.py",
        'level = "CRITICAL"',
        'level = "ERROR"',
        "packages/backend/tests/test_request_logs.py::test_http_log",
    ),
    Mutation(
        "frontend",
        "画面内の入力不備をサーバー障害として記録する",
        "packages/frontend/src/web_app/client.py",
        "failed=not user_error",
        "failed=True",
        "packages/frontend/tests/test_screen_logs.py::test_screen_error_context",
    ),
    Mutation(
        "frontend",
        "ログ取得の失敗時に未定義のクライアント例外を参照する",
        "packages/frontend/src/web_app/portal_pages/logs.py",
        'raise ValueError("ログを取得できませんでした")',
        'raise client.ResponseError("ログを取得できませんでした")',
        "packages/frontend/tests/test_access_log_download.py::test_failed_log_download_reports_error",
    ),
    Mutation(
        "architecture",
        "公開画面の空の登録を許可する",
        "tests/architecture/frontend_screens.py",
        " or not value.elts",
        "",
        "tests/architecture/test_frontend_screens.py::test_feature_requires_local_screen_declaration",
    ),
    Mutation(
        "architecture",
        "画面間の直接参照を許可する",
        "tests/architecture/frontend_screens.py",
        'parts[0] == "portal_pages"',
        'parts[0] == "_unused"',
        "tests/architecture/test_frontend_screens.py::test_feature_cannot_depend_on_another_screen_or_the_shell",
    ),
    Mutation(
        "architecture",
        "共通レイアウトの画面分岐を見逃す",
        "tests/architecture/frontend_screens.py",
        'module in {"app", "portal_shell"}',
        'module == "app"',
        "tests/architecture/test_frontend_screens.py::test_shared_layout_delegates_route_dispatch",
    ),
    Mutation(
        "frontend",
        "画面を配布するときにサブディレクトリを省く",
        "tools/build_frontend.py",
        'source.rglob("*.py")',
        'source.glob("*.py")',
        "packages/frontend/tests/test_screen_registry.py::test_new_screen_is_packaged_loaded_and_rendered",
    ),
    Mutation(
        "frontend",
        "同じルートを登録した画面で先に登録した画面を上書きする",
        "packages/frontend/src/web_app/screen_registry.py",
        "if screen.path in by_path:",
        "if False:",
        "packages/frontend/tests/test_screen_registry.py::test_duplicate_screen_path_is_rejected",
    ),
    Mutation(
        "model-layer",
        "判定モデルの依存群をSDKだけに置き換える",
        "tools/build_backend.py",
        '["--only-group", "decision-model"]',
        '["--only-group", "model-sdk"]',
        "tools/tests/test_lambda_layer.py::test_each_lambda_layer_exports_its_locked_dependencies",
    ),
    Mutation(
        "architecture",
        "判定モデルが欠けた配布物を許可する",
        "tests/architecture/model_artifacts.py",
        '{"decision", "tool", "generate"} - manifest.keys()',
        '{"tool", "generate"} - manifest.keys()',
        "tests/architecture/test_rule_checks.py::test_model_distribution_requires_all_three_roles",
    ),
    Mutation(
        "architecture",
        "英語だけのテスト説明を許可する",
        "tests/architecture/case_text.py",
        " and bool(KANA.search(text))",
        "",
        "tests/architecture/test_rule_checks.py::test_case_explanation_requires_one_japanese_sentence",
    ),
    Mutation(
        "architecture",
        "層を越える依存をすべて許可する",
        "tests/architecture/dependencies.py",
        "target in ALLOWED[owner]",
        "owner in ALLOWED",
        "tests/architecture/test_rule_checks.py::test_boundary_checker_rejects_cross_layer_imports",
    ),
    Mutation(
        "architecture",
        "相対インポートの検査を飛ばす",
        "tests/architecture/dependencies.py",
        "elif isinstance(node, ast.ImportFrom):",
        "elif isinstance(node, ast.ImportFrom) and not node.level:",
        "tests/architecture/test_rule_checks.py::test_boundary_checker_rejects_cross_layer_imports",
    ),
    Mutation(
        "architecture",
        "共有ガイドの利用も拒否する",
        "tests/architecture/dependencies.py",
        'module == "agent.retrieval" and',
        'module == "agent.unused" and',
        "tests/architecture/test_rule_checks.py::test_boundary_checker_accepts_supported_collaboration",
    ),
    Mutation(
        "architecture",
        "新規パッケージを無条件にバックエンドとして扱う",
        "tests/architecture/dependencies.py",
        'raise ValueError(f"{path}: 新しいパッケージの依存規則を定義してください")',
        'return "app"',
        "tests/architecture/test_rule_checks.py::test_new_package_requires_layer_rules",
    ),
    Mutation(
        "architecture",
        "コード例の見出しを文書の表題として採用する",
        "tests/architecture/test_documents.py",
        'if not fence and line.startswith("# "):',
        'if line.startswith("# "):',
        "tests/architecture/test_rule_checks.py::test_document_checker_uses_title_outside_code_examples",
    ),
    Mutation(
        "architecture",
        "生成設計書を検査対象から外す",
        "tests/architecture/project.py",
        "if name not in EXCLUDED",
        'if name != "generated" and name not in EXCLUDED',
        "tests/architecture/test_rule_checks.py::test_project_discovery_includes_new_components",
    ),
    Mutation(
        "architecture",
        "長さだけで重みのハッシュを受け付ける",
        "tests/architecture/model_artifacts.py",
        ' or any(ch not in "0123456789abcdef" for ch in digest)',
        "",
        "tests/architecture/test_rule_checks.py::test_model_checker_rejects_unpinned_weight",
    ),
    Mutation(
        "architecture",
        "非同期テストを日本語説明の検査対象から外す",
        "tests/architecture/test_case_descriptions.py",
        "(ast.FunctionDef, ast.AsyncFunctionDef)",
        "ast.FunctionDef",
        "tests/architecture/test_rule_checks.py::test_case_discovery_includes_async_class_methods",
    ),
    Mutation(
        "architecture",
        "設計解析に正規表現を許可する",
        "tests/architecture/test_design_sources.py",
        'if imported.split(".")[0] in REGEX:',
        "if False:",
        "tests/architecture/test_design_sources.py::test_analysis_policy_follows_renamed_helpers_and_relative_imports",
    ),
    Mutation(
        "lambda-layer",
        "Layerに依存を配置するディレクトリを誤る",
        "tools/build_backend.py",
        'ZipInfo("python/"',
        'ZipInfo("wrong/"',
        "tools/tests/test_lambda_layer.py::test_layer_rebuild_is_reproducible",
    ),
    Mutation(
        "coverage",
        "エージェントとモデルの未実行ファイルを分母から除外する",
        "pyproject.toml",
        '    "packages/agent/src/agent",\n',
        "",
        "tools/tests/test_ci_scope.py::test_coverage_includes_all_runtime_layers_and_unexecuted_files",
    ),
    Mutation(
        "models",
        "取得したモデルのチェックサムを検証しない",
        "packages/agent/src/agent/models/runtime.py",
        'if "sha256" in item:',
        "if False:",
        "packages/agent/tests/test_model_workers.py::test_model_download_verifies_digest_before_reuse",
    ),
    Mutation(
        "backend",
        "チャットの参照ロールに商品の更新権限を加える",
        "packages/backend/src/app/migrate.py",
        "GRANT SELECT ON assets TO tsugite_chat",
        "GRANT SELECT, UPDATE ON assets TO tsugite_chat",
        "packages/backend/tests/test_migrate.py::test_grants_public_tables_without_altering_the_schema[chat]",
    ),
    Mutation(
        "frontend",
        "未取得のメトリクスを描画時に直接参照する",
        "packages/frontend/src/web_app/portal_pages/dashboard.py",
        'data = ctx.get("home_metrics")',
        'data = ctx["home_metrics"]',
        "packages/frontend/tests/test_dashboard.py::test_dashboard_recovers_from_metrics_failure",
    ),
    Mutation(
        "backend",
        "集計の次ページを取得せずに打ち切る",
        "packages/backend/src/app/apis/governance/observability.py",
        "if len(rows) < page_size:",
        "if len(rows) <= page_size:",
        "packages/backend/tests/test_governance.py::test_admin_metrics_across_pages",
    ),
    Mutation(
        "frontend",
        "認証アプリの検証後に古いセッションを再利用する",
        "packages/frontend/src/web_app/portal_auth.py",
        'self.session = verified["Session"]',
        "self.session = self.session",
        "packages/frontend/tests/test_portal_login.py::test_invitation_and_totp_setup",
    ),
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
        "measured_changes\n                and part.stat().st_size",
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
        "agent",
        "生成クエリだけに一致する商品も候補に含める",
        "packages/agent/src/agent/retrieval.py",
        " and (index == 0 or similarities[0] >= 0.39)",
        "",
        "packages/agent/tests/test_agent_retrieval.py::test_rewritten_similarity_needs_support_from_original_question",
    ),
    Mutation(
        "frontend",
        "候補の商品リンクがカタログのトップを指す",
        "packages/frontend/src/web_app/chat_views.py",
        'href="#/api/" + quote(product["id"], safe="")',
        'href="#/catalog"',
        "packages/frontend/tests/test_components.py::test_chat_product_and_guide_are_linked",
    ),
    Mutation(
        "infra",
        "モデルの予備領域を増やす",
        "packages/infra/src/infra_app/chat.py",
        "ephemeral_storage_size=Size.mebibytes(512)",
        "ephemeral_storage_size=Size.mebibytes(1024)",
        "packages/infra/tests/test_cost.py::test_chat_uses_separate_on_demand_python_functions",
    ),
    Mutation(
        "backend",
        "設計項目の直前の和名コメントを読み飛ばす",
        "packages/database/src/tsugite_db/source_docs.py",
        "self.comments.get(node.lineno - 1",
        "self.comments.get(node.lineno - 2",
        "tests/architecture/test_design_sources.py::"
        "test_schema_field_uses_only_the_comment_on_its_declaration",
    ),
    Mutation(
        "backend",
        "設計解析に別名で正規表現を取り込む",
        "packages/backend/src/app/design_names.py",
        "import inspect",
        "import inspect\nimport re as parser",
        "tests/architecture/test_design_sources.py::"
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
        "backend",
        "Aurora DSQLのマイグレーションで方言のカラム取得に戻す",
        "packages/database/src/tsugite_db/migration_columns.py",
        'connection.dialect.name != "auroradsql"',
        'connection.dialect.name == "auroradsql"',
        "packages/database/tests/test_migration_columns.py::"
        "test_dsql_column_names_use_the_system_catalog",
    ),
    Mutation(
        "backend",
        "Aurora DSQLに public スキーマへの直接付与を発行する",
        "packages/backend/src/app/migrate.py",
        "        # DSQL protects the public schema, and its USAGE is inherited through PUBLIC.",
        '        conn.exec_driver_sql("GRANT USAGE ON SCHEMA public TO tsugite_app")',
        "packages/backend/tests/test_migrate.py::test_grants_public_tables_without_altering_the_schema",
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
    Mutation(
        "bootstrap",
        "招待したユーザーと異なる識別子でも管理者にする",
        "tools/bootstrap_admin.py",
        'if not any(attr == {"Name": "sub", "Value": subject} for attr in user["UserAttributes"]):',
        "if False:",
        "tools/tests/test_bootstrap_admin.py::test_replaced_user_cannot_be_promoted",
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


def detected(returncode: int, cases: list[ElementTree.Element]) -> bool:
    return (
        returncode == 1
        and any(case.find("failure") is not None for case in cases)
        and not any(case.find("error") is not None for case in cases)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layer", choices=sorted({entry.layer for entry in MUTATIONS}), action="append")
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
            if detected(result.returncode, cases):
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
