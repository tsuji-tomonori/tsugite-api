# 代表的な回帰を注入し、ローカルの単体テストが検出するか確かめる。
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

ROOT = Path(__file__).resolve().parents[3]


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
        "quint-diff",
        "他の形式モデルの差分を業務ルールの更新として認める",
        "packages/tools/design/formal_changes.py",
        'if f"{FORMAL}/{domain}.qnt" not in changed:\n            return False',
        'if f"{FORMAL}/{domain}.qnt" not in changed:\n            return True',
        "packages/tools/tests/test_formal_changes.py::test_business_policy_requires_its_quint_domain",
    ),
    Mutation(
        "deployed-e2e",
        "実環境でログインした利用者の識別子を照合しない",
        "tests/e2e/deployed/account.py",
        'and profile.get("subject") == subject',
        "and True",
        "packages/tools/tests/test_deployed_account.py::test_only_expected_consumer",
    ),
    Mutation(
        "admin-role",
        "最後の管理者の権限を剥奪できてしまう",
        "packages/backend/src/app/apis/governance/admin_roles.py",
        "if admins == {subject}:",
        "if not admins:",
        "packages/backend/tests/test_quint_administrators.py::test_admin_role_handover",
    ),
    Mutation(
        "formal",
        "利用者別の禁止操作を許可する",
        "packages/backend/src/app/core/credential_policy.py",
        'if allowed is not None and operation not in allowed:\n        raise HTTPException(403, "この利用者',
        'if False:\n        raise HTTPException(403, "この利用者',
        "packages/backend/tests/test_quint_policy.py::test_operation_policy",
    ),
    Mutation(
        "formal",
        "本人限定の利用権を共有キーにも認める",
        "packages/backend/src/app/apis/gateway.py",
        "not actor.machine and not actor.key_shared:",
        "not actor.machine:",
        "packages/backend/tests/test_quint_policy.py::test_entitlement_policy",
    ),
    Mutation(
        "formal",
        "取消を実行しても利用権を承認済みに残す",
        "packages/backend/src/app/core/catalog.py",
        '"revoke": ("approved", "revoked")',
        '"revoke": ("approved", "approved")',
        "packages/backend/tests/test_quint_grants.py::test_grant_history",
    ),
    Mutation(
        "http-contract",
        "サーバー内部エラーの本文から必須のエラーコードを取り除く",
        "packages/backend/src/app/core/request_logs.py",
        '"error_code": "INTERNAL_ERROR", ',
        "",
        "packages/backend/tests/test_http_contract.py::test_catalog_search_failure",
    ),
    Mutation(
        "frontend",
        "認証情報の初期更新時刻を有効期間の5分前に固定する",
        "packages/frontend/src/web_app/components/credential_views.py",
        "default_ttl * 3 // 4",
        "default_ttl - 5",
        "packages/frontend/tests/test_required_people_credentials.py::test_credential_modes_and_validity",
    ),
    Mutation(
        "backend",
        "解除済みの所属を移管の競合に含める",
        "packages/backend/src/app/apis/governance/unit_lifecycle.py",
        "elif row.active and destination.active:",
        "elif row.active:",
        "packages/backend/tests/test_required_workspace.py::test_conflicting_transfer_keeps_both_projects",
    ),
    Mutation(
        "backend",
        "名簿の一時障害を予期しない障害として返す",
        "packages/backend/src/app/apis/governance/members.py",
        '503, "利用者を確認できませんでした。',
        '500, "利用者を確認できませんでした。',
        "packages/backend/tests/test_required_member_directory.py::test_directory_temporarily_unavailable",
    ),
    Mutation(
        "architecture",
        "分岐が未達でも行の合格だけで通す",
        "packages/tools/ci/unit_coverage.py",
        "passed &= meets",
        'passed &= meets or label == "branch"',
        "packages/tools/tests/test_unit_coverage.py::test_coverage_compares_exact_line_and_branch_counts",
    ),
    Mutation(
        "origin-boundary",
        "画面操作APIが入口の検証を省く",
        "packages/backend/src/app/core/request_logs.py",
        'if os.getenv("AWS_LAMBDA_FUNCTION_NAME") and not secrets.compare_digest(',
        "if False and not secrets.compare_digest(",
        "packages/backend/tests/test_auth.py::test_portal_origin_with_valid_access_token",
    ),
    Mutation(
        "origin-boundary",
        "商品APIが入口の検証を省く",
        "packages/backend/src/app/authorizer.py",
        'if not secrets.compare_digest(headers.get("x-tsugite-origin", ""), os.environ["ORIGIN_SECRET"]):',
        "if False:",
        "packages/backend/tests/test_gateway_event.py::test_gateway_authorizer_rechecks_each_invocation",
    ),
    Mutation(
        "origin-boundary",
        "配信元に送るヘッダーの名前を変更する",
        "packages/infra/src/components/delivery.py",
        'custom_headers={"X-Tsugite-Origin":',
        'custom_headers={"X-Other-Origin":',
        "packages/infra/tests/test_stack.py::test_access_boundaries",
    ),
    Mutation(
        "requirements",
        "変更した要件の古い履歴を新しい変更理由として認める",
        "packages/tools/design/requirements.py",
        "line in added and re.fullmatch",
        "re.fullmatch",
        "tests/architecture/core/test_requirement_maintenance.py::test_changed_item_requires_new_reason",
    ),
    Mutation(
        "metadata",
        "任意属性の役職を既存の自動承認条件に含める",
        "packages/backend/src/app/core/workspace.py",
        "if kind not in BUILTIN_FIELDS:\n            continue",
        "if kind not in BUILTIN_FIELDS:\n            titles.add(m.title)\n            continue",
        "packages/backend/tests/test_user_metadata.py::test_metadata_groups_and_visibility",
    ),
    Mutation(
        "database",
        "公開履歴テーブルのモデル登録を外す",
        "packages/database/src/tsugite_db/models/__init__.py",
        "from .spec_releases import SpecRelease as SpecRelease",
        "",
        "tests/architecture/database/test_persistence.py::test_model_files_match_registered_tables",
    ),
    Mutation(
        "generated-docs",
        "API一覧のリンクが操作別の設計書に届かない",
        "packages/tools/design/generate.py",
        'f"[{operation_label}]({filename})"',
        'f"[{operation_label}]({dest})"',
        "packages/tools/tests/test_design.py::test_all_routes_inputs_outputs_and_cleanup",
    ),
    Mutation(
        "frontend",
        "ページからPuePyを直接使う変更を見逃す",
        "tests/architecture/frontend/frontend_screens.py",
        'parts[0] in {"puepy", "js"}',
        'parts[0] in {"js"}',
        "tests/architecture/frontend/test_frontend_screens.py::test_components_cannot_import_pages_and_pages_cannot_define_widgets",
    ),
    Mutation(
        "frontend",
        "集計区間数に応じたグラフの最小幅を無効にする",
        "packages/frontend/src/web_app/components/activity_filters.py",
        'style=f"--buckets:{len(pts)}"',
        'style="--buckets:0"',
        "packages/frontend/tests/test_dashboard.py::test_dashboard_recovers_from_metrics_failure",
    ),
    Mutation(
        "member-profile",
        "氏名と表示名の更新で監査イベントを書き込まない",
        "packages/backend/src/app/apis/governance/profiles.py",
        'member_event(db, request, actor, action, subject, ", ".join(changes))',
        "pass",
        "packages/backend/tests/test_member_profiles.py::test_profile_edits_filter_directory_and_audit",
    ),
    Mutation(
        "member-profile",
        "所属一覧で名前と独立したメールアドレスを無視する",
        "packages/frontend/src/web_app/components/workspace_members.py",
        'email = person.get("email")',
        "email = None",
        "packages/frontend/tests/test_workspace_screens.py::test_direct_members_have_aligned_table_columns",
    ),
    Mutation(
        "audit-scope",
        "本人のアクセスログに同じプロジェクトの別人の呼び出しを含める",
        "packages/backend/src/app/apis/governance/observability.py",
        "return AccessLog.actor == actor.subject",
        "return AccessLog.project.in_(actor.projects)",
        "packages/backend/tests/test_org_access.py::test_access_log_scopes",
    ),
    Mutation(
        "backend",
        "移管元の識別子が組織一覧に復活する",
        "packages/backend/src/app/core/workspace.py",
        "return {k: v for k, v in base.items() if k not in retired_units(db)}",
        "return base",
        "packages/backend/tests/test_unit_lifecycle.py::test_project_transfer",
    ),
    Mutation(
        "frontend",
        "API Docsで同じ商品の個人認証情報を毎回発行する",
        "packages/frontend/src/web_app/components/api_docs.py",
        "if project not in keys:",
        "if True:",
        "packages/frontend/tests/test_api_client.py::"
        "test_trial_uses_approved_environments_and_reuses_personal_credential",
    ),
    Mutation(
        "frontend",
        "公開履歴の表で操作の変更を表示しない",
        "packages/frontend/src/web_app/components/product_views.py",
        "if row[key]",
        'if row[key] and key != "changed"',
        "packages/frontend/tests/test_components.py::test_publication_history_shows_release_changes",
    ),
    Mutation(
        "frontend",
        "利用状況に業務メニューを表示する",
        "packages/frontend/src/web_app/components/dashboard.py",
        '        btn("利用状況を再読み込み", load)',
        '        btn("利用状況を再読み込み", load)\n'
        '    with t.div(classes="box"):\n'
        '        t.h2("業務メニュー")\n'
        '        btn("APIを探す", go, "catalog", primary=True)',
        "packages/frontend/tests/test_dashboard.py::test_dashboard_recovers_from_metrics_failure",
    ),
    Mutation(
        "frontend",
        "同じ問い合わせを再送するときに受付番号を振り直す",
        "packages/frontend/src/web_app/apis/messages.py",
        'if state.get("draft") != question:',
        "if True:",
        "packages/frontend/tests/test_inquiry_form.py::test_retry_reuses_pending_inquiry_id",
    ),
    Mutation(
        "frontend",
        "管理者の通知先にプロジェクト名を表示しない",
        "packages/frontend/src/web_app/components/notifications.py",
        '[(p, names.get(p, p)) for p in me["known_projects"]]',
        '[(p, p) for p in me["known_projects"]]',
        "packages/frontend/tests/test_notification_recipients.py::"
        "test_notification_recipient_dropdown_uses_display_names",
    ),
    Mutation(
        "frontend",
        "提供者の通知先にプロジェクト名を表示しない",
        "packages/frontend/src/web_app/actions/management_targets.py",
        "r.get('project_label', r['project'])",
        "r['project']",
        "packages/frontend/tests/test_notification_recipients.py::"
        "test_notification_recipient_dropdown_uses_display_names",
    ),
    Mutation(
        "frontend",
        "ガイドの画面例を操作可能にする",
        "packages/frontend/src/web_app/components/guide_views.py",
        'classes="guide-preview", inert=True',
        'classes="guide-preview", inert=False',
        "packages/frontend/tests/test_components.py::test_each_guide_renders_inert_example",
    ),
    Mutation(
        "access-log",
        "次ページ確認用の1件を一覧にも表示する",
        "packages/frontend/src/web_app/components/logs.py",
        "for row in rows[:PAGE_SIZE]:",
        "for row in rows:",
        "packages/frontend/tests/test_access_log_detail.py::test_log_page_shows_only_requested_rows",
    ),
    Mutation(
        "api-slug",
        "DBでAPI識別名の重複を許す",
        "packages/database/migrations/versions/v010_asset_routes.py",
        'sa.Column("slug", sa.String(63), nullable=False, unique=True)',
        'sa.Column("slug", sa.String(63), nullable=False)',
        "packages/database/tests/test_migrations.py::test_schema_matches_models_and_replays",
    ),
    Mutation(
        "api-slug",
        "呼び出し先のAPI識別名をUUIDに解決しない",
        "packages/backend/src/app/apis/gateway.py",
        "return record(db, asset_id or key)",
        "return record(db, key)",
        "packages/backend/tests/test_catalog.py::test_existing_api_keeps_grants_when_named",
    ),
    Mutation(
        "api-slug",
        "画面の呼び出しURLにAPI識別名を使わない",
        "packages/frontend/src/web_app/apis/client.py",
        '(asset.get("slug") or asset["id"], environment, project)',
        '(asset["id"], environment, project)',
        "packages/frontend/tests/test_components.py::test_invocation_path_uses_product_slug",
    ),
    Mutation(
        "completion",
        "ワークフローの実行条件をすべてのPRとして掲載する",
        "packages/tools/design/completion.py",
        'conditions = [node["if"].value for node in (mapping(job), fields) if "if" in node]',
        "conditions = []",
        "packages/tools/tests/test_completion.py::test_workflow_comments_follow_steps",
    ),
    Mutation(
        "frontend",
        "直接指定したURLにブラウザーの認証情報を送る",
        "packages/frontend/src/web_app/apis/manual.py",
        '"credentials": "omit"',
        '"credentials": "include"',
        "packages/frontend/tests/test_api_client.py::test_manual_request_uses_only_entered_headers",
    ),
    Mutation(
        "backend",
        "利用者のワークスペースに未所属のプロジェクトを含める",
        "packages/backend/src/app/apis/governance/directory.py",
        '"units": visible_units,',
        '"units": list(tree.values()),',
        "packages/backend/tests/test_org_access.py::test_workspace_project_visibility",
    ),
    Mutation(
        "frontend",
        "curlコマンドから本文を除く",
        "packages/frontend/src/web_app/components/api_docs.py",
        'if "body" in options:',
        "if False:",
        "packages/frontend/tests/test_components.py::test_curl_reuses_request_without_exposing_token",
    ),
    Mutation(
        "backend",
        "ポータルのログインだけで転送を許可する",
        "packages/backend/src/app/apis/gateway.py",
        "if not actor.key_id and not actor.machine:",
        "if False:",
        "packages/backend/tests/test_catalog.py::test_lifecycle",
    ),
    Mutation(
        "infra",
        "モデル関数のメモリを配備先の上限より大きくする",
        "packages/infra/src/components/chat.py",
        "memory_size=3008,",
        "memory_size=3072,",
        "packages/infra/tests/test_cost.py::test_chat_uses_separate_on_demand_python_functions",
    ),
    Mutation(
        "infra",
        "モデル関数の配備を待たずにDB移行を開始する",
        "packages/infra/src/stack.py",
        "schema.node.add_dependency(chat)",
        "pass",
        "packages/infra/tests/test_cdk_regression.py::test_schema_waits_for_chat_models",
    ),
    Mutation(
        "infra",
        "チャットのワーカー関数に同時実行枠を予約する",
        "packages/infra/src/components/chat.py",
        "timeout=Duration.seconds(145),",
        "timeout=Duration.seconds(145), reserved_concurrent_executions=4,",
        "packages/infra/tests/test_cost.py::test_chat_uses_separate_on_demand_python_functions",
    ),
    Mutation(
        "infra",
        "チャットのモデル関数に同時実行枠を予約する",
        "packages/infra/src/components/chat.py",
        "timeout=Duration.seconds(timeout),",
        "timeout=Duration.seconds(timeout), reserved_concurrent_executions=4,",
        "packages/infra/tests/test_cost.py::test_chat_uses_separate_on_demand_python_functions",
    ),
    Mutation(
        "ci-scope",
        "データベース変更時にAPIのテストを外す",
        "packages/tools/ci/ci_scope.py",
        'return {DATABASE, AGENT, BACKEND, BROWSER, TOOLS, "types", "design", "aws"}',
        'return {DATABASE, AGENT, BROWSER, TOOLS, "types", "design", "aws"}',
        "tests/architecture/core/test_ci_scope.py::test_workspace_dependency_changes_verify_consumers",
    ),
    Mutation(
        "ci-scope",
        "共有ガイド変更時に利用側のテストを外す",
        "packages/tools/ci/ci_scope.py",
        'return {AGENT, FRONTEND, BROWSER, BACKEND, "types"}',
        'return {FRONTEND, BROWSER, "types"}',
        "tests/architecture/core/test_ci_scope.py::test_imported_modules_verify_their_actual_consumers",
    ),
    Mutation(
        "ci-scope",
        "PRテンプレートを全検証の対象に戻す",
        "packages/tools/ci/ci_scope.py",
        '"deploy/", ".agents/", ".github/"',
        '"deploy/", ".agents/"',
        "tests/architecture/core/test_ci_scope.py::test_verify_skips_unrelated_packages_even_without_coverage",
    ),
    Mutation(
        "evidence",
        "実行結果のない要件を合格にする",
        "packages/tools/testing/requirement_evidence.py",
        'statuses.append("未実行")',
        'statuses.append("成功")',
        "packages/tools/tests/test_requirement_evidence.py::test_unexecuted_requirement_fails",
    ),
    Mutation(
        "evidence",
        "スキップを成功にする",
        "packages/tools/testing/requirement_evidence.py",
        '("skipped", "スキップ")',
        '("skipped", "成功")',
        "packages/tools/tests/test_requirement_evidence.py::test_skipped_requirement_fails",
    ),
    Mutation(
        "infra-docs",
        "パラメーターシートから配列の添字を落とす",
        "packages/tools/design/infrastructure.py",
        'settings(f"{path}[{index}]", item)',
        "settings(path, item)",
        "packages/tools/tests/test_infrastructure_docs.py::test_component_parameter_sheet",
    ),
    Mutation(
        "stock-lambda",
        "存在しない商品を成功として返す",
        "packages/sample_api/src/sample_api/database.py",
        "raise HTTPException(404,",
        "raise HTTPException(200,",
        "packages/sample_api/tests/test_stock_lambda.py::test_stock_response[missing]",
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
        "packages/frontend/src/web_app/apis/client.py",
        "failed=not user_error",
        "failed=True",
        "packages/frontend/tests/test_screen_logs.py::test_screen_error_context",
    ),
    Mutation(
        "frontend",
        "ログ取得の失敗を記録済みと扱い、画面側の障害ログを失う",
        "packages/frontend/src/web_app/actions/logs.py",
        'raise ValueError("ログを取得できませんでした")',
        'raise client.ResponseError("ログを取得できませんでした")',
        "packages/frontend/tests/test_access_log_download.py::test_failed_log_download_reports_error",
    ),
    Mutation(
        "architecture",
        "公開画面の空の登録を許可する",
        "tests/architecture/frontend/frontend_screens.py",
        " or len(value.elts) != 1",
        "",
        "tests/architecture/frontend/test_frontend_screens.py::test_feature_requires_local_screen_declaration",
    ),
    Mutation(
        "architecture",
        "画面間の直接参照を許可する",
        "tests/architecture/frontend/frontend_screens.py",
        'if parts[0] == "pages":',
        'if parts[0] == "_unused":',
        "tests/architecture/frontend/test_frontend_screens.py::test_feature_cannot_depend_on_another_screen_or_the_shell",
    ),
    Mutation(
        "architecture",
        "共通レイアウトの画面分岐を見逃す",
        "tests/architecture/frontend/frontend_screens.py",
        'module in {"app", "runtime.portal_shell"}',
        'module == "app"',
        "tests/architecture/frontend/test_frontend_screens.py::test_shared_layout_delegates_route_dispatch",
    ),
    Mutation(
        "frontend",
        "モニタリングの所属メンバーを表として表示しない",
        "packages/frontend/src/web_app/components/workspace_monitor.py",
        'with t.table(aria_label="所属メンバー一覧"):',
        'with t.div(aria_label="所属メンバー一覧"):',
        "packages/frontend/tests/test_workspace_screens.py::test_project_monitor_shows_members_as_a_table",
    ),
    Mutation(
        "frontend",
        "部署一覧の次ページにも先頭の部署を表示する",
        "packages/frontend/src/web_app/components/workspace_views.py",
        "start = (number - 1) * PAGE_SIZE",
        "start = 0",
        "packages/frontend/tests/test_workspace_screens.py::test_directory_pages_filter_before_paginating",
    ),
    Mutation(
        "frontend",
        "直接所属のメールアドレス欄を空にする",
        "packages/frontend/src/web_app/components/workspace_members.py",
        't.td(email or "—")',
        't.td("—")',
        "packages/frontend/tests/test_workspace_screens.py::test_direct_members_have_aligned_table_columns",
    ),
    Mutation(
        "frontend",
        "画面を配布するときにサブディレクトリを省く",
        "packages/tools/packaging/build_frontend.py",
        'source.rglob("*.py")',
        'source.glob("*.py")',
        "packages/frontend/tests/test_screen_registry.py::test_new_screen_is_packaged_loaded_and_rendered",
    ),
    Mutation(
        "frontend",
        "同じルートを登録した画面で先に登録した画面を上書きする",
        "packages/frontend/src/web_app/routing/screen_registry.py",
        "if screen.path in by_path:",
        "if False:",
        "packages/frontend/tests/test_screen_registry.py::test_duplicate_screen_path_is_rejected",
    ),
    Mutation(
        "infra",
        "サンプルAPIを以前のPythonランタイムに戻す",
        "packages/infra/src/components/bindings.py",
        "runtime=EVENT_PYTHON,",
        "runtime=fn.Runtime.PYTHON_3_14,",
        "packages/infra/tests/test_cdk_regression.py::test_sample_functions_use_python_315",
    ),
    Mutation(
        "model-layer",
        "判定モデルを専用Layerと異なるパスから読む",
        "packages/model/src/decision.py",
        'Path("/opt/models/decision")',
        'Path("/tmp/models/decision")',
        "packages/model/tests/test_model_workers.py::test_embedding_load_reuses_cpu_model_and_tokenizer",
    ),
    Mutation(
        "model-layer",
        "判定モデルの依存群をSDKだけに置き換える",
        "packages/tools/packaging/build_backend.py",
        '["--project", "packages/model/decision-model", "--no-dev"]',
        '["--package", "tsugite-model", "--no-dev"]',
        "packages/tools/tests/test_lambda_layer.py::test_each_lambda_layer_exports_its_locked_dependencies",
    ),
    Mutation(
        "architecture",
        "判定モデルが欠けた配布物を許可する",
        "tests/architecture/model/model_artifacts.py",
        '{"decision", "tool", "generate"} - manifest.keys()',
        '{"tool", "generate"} - manifest.keys()',
        "tests/architecture/core/test_rule_checks.py::test_model_distribution_requires_all_three_roles",
    ),
    Mutation(
        "architecture",
        "英語だけのテスト説明を許可する",
        "tests/architecture/core/case_text.py",
        " and bool(KANA.search(text))",
        "",
        "tests/architecture/core/test_rule_checks.py::test_case_explanation_requires_one_japanese_sentence",
    ),
    Mutation(
        "architecture",
        "層を越える依存をすべて許可する",
        "tests/architecture/core/dependencies.py",
        "target in ALLOWED[owner]",
        "owner in ALLOWED",
        "tests/architecture/core/test_rule_checks.py::test_boundary_checker_rejects_cross_layer_imports",
    ),
    Mutation(
        "architecture",
        "相対インポートの検査を飛ばす",
        "tests/architecture/core/dependencies.py",
        "elif isinstance(node, ast.ImportFrom):",
        "elif isinstance(node, ast.ImportFrom) and not node.level:",
        "tests/architecture/core/test_rule_checks.py::test_relative_imports_resolve_with_original_line_numbers",
    ),
    Mutation(
        "architecture",
        "共有ガイドの利用も拒否する",
        "tests/architecture/core/dependencies.py",
        'module == "agent.chat_retrieval" and',
        'module == "agent.unused" and',
        "tests/architecture/core/test_rule_checks.py::test_boundary_checker_accepts_supported_collaboration",
    ),
    Mutation(
        "architecture",
        "新規パッケージを無条件にバックエンドとして扱う",
        "tests/architecture/core/dependencies.py",
        'raise ValueError(f"{path}: 新しいパッケージの依存規則を定義してください")',
        'return "app"',
        "tests/architecture/core/test_rule_checks.py::test_new_package_requires_layer_rules",
    ),
    Mutation(
        "architecture",
        "コード例の見出しを文書の表題として採用する",
        "tests/architecture/core/test_documents.py",
        'if not fence and line.startswith("# "):',
        'if line.startswith("# "):',
        "tests/architecture/core/test_rule_checks.py::test_document_checker_uses_title_outside_code_examples",
    ),
    Mutation(
        "architecture",
        "生成設計書を検査対象から外す",
        "tests/architecture/core/project.py",
        "if name not in EXCLUDED",
        'if name != "generated" and name not in EXCLUDED',
        "tests/architecture/core/test_rule_checks.py::test_project_discovery_includes_new_components",
    ),
    Mutation(
        "architecture",
        "長さだけで重みのハッシュを受け付ける",
        "tests/architecture/model/model_artifacts.py",
        ' or any(ch not in "0123456789abcdef" for ch in digest)',
        "",
        "tests/architecture/core/test_rule_checks.py::test_model_checker_rejects_unpinned_weight",
    ),
    Mutation(
        "architecture",
        "非同期テストを日本語説明の検査対象から外す",
        "tests/architecture/core/test_case_descriptions.py",
        "(ast.FunctionDef, ast.AsyncFunctionDef)",
        "ast.FunctionDef",
        "tests/architecture/core/test_rule_checks.py::test_case_discovery_includes_async_class_methods",
    ),
    Mutation(
        "architecture",
        "設計解析に正規表現を許可する",
        "tests/architecture/tools/test_design_sources.py",
        'if imported.split(".")[0] in REGEX:',
        "if False:",
        "tests/architecture/tools/test_design_sources.py::test_analysis_policy_follows_renamed_helpers_and_relative_imports",
    ),
    Mutation(
        "lambda-layer",
        "Layerに依存を配置するディレクトリを誤る",
        "packages/tools/packaging/build_backend.py",
        'ZipInfo("python/"',
        'ZipInfo("wrong/"',
        "packages/tools/tests/test_lambda_layer.py::test_layer_rebuild_is_reproducible",
    ),
    Mutation(
        "coverage",
        "エージェントとモデルの未実行ファイルを分母から除外する",
        "pyproject.toml",
        '    "packages/agent/src",\n',
        "",
        "packages/tools/tests/test_ci_scope.py::test_coverage_includes_all_runtime_layers_and_unexecuted_files",
    ),
    Mutation(
        "model",
        "取得したモデルのチェックサムを検証しない",
        "packages/model/src/model_runtime.py",
        'if "sha256" in item:',
        "if False:",
        "packages/model/tests/test_model_workers.py::test_model_download_verifies_digest_before_reuse",
    ),
    Mutation(
        "backend",
        "チャットの参照ロールに商品の更新権限を加える",
        "packages/backend/src/app/migrate.py",
        "GRANT SELECT ON assets, asset_routes TO tsugite_chat",
        "GRANT SELECT, UPDATE ON assets, asset_routes TO tsugite_chat",
        "packages/backend/tests/test_migrate.py::test_grants_public_tables_without_altering_the_schema[chat]",
    ),
    Mutation(
        "frontend",
        "未取得のメトリクスを描画時に直接参照する",
        "packages/frontend/src/web_app/components/dashboard.py",
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
        "packages/frontend/src/web_app/apis/portal_auth.py",
        'self.session = verified["Session"]',
        "self.session = self.session",
        "packages/frontend/tests/test_portal_login.py::test_invitation_and_totp_setup",
    ),
    Mutation(
        "ci",
        "ファイル移動時に移動元の変更を見落とす",
        "packages/tools/ci/ci_scope.py",
        '"--no-renames"',
        '"--find-renames"',
        "packages/tools/tests/test_ci_scope.py::test_git_diff_includes_deleted_and_both_renamed_paths",
    ),
    Mutation(
        "ci",
        "以前の実行行を含むテスト層の再計測を省く",
        "packages/tools/ci/ci_scope.py",
        "measured_changes\n                and part.is_file()",
        "False",
        "packages/tools/tests/test_ci_scope.py::test_measured_source_invalidates_suites_that_executed_it",
    ),
    Mutation(
        "tools",
        "既存要件の編集だけでfeatブランチを許可する",
        "packages/tools/design/requirements.py",
        '"--diff-filter=A"',
        '"--diff-filter=AM"',
        "packages/tools/tests/test_requirements.py::test_feature_requires_added_requirement",
    ),
    Mutation(
        "tools",
        "未定義の用語を要件の見出しで許可する",
        "packages/tools/design/requirements.py",
        "if unknown:",
        "if False:",
        "packages/tools/tests/test_requirements.py::test_undefined_term_in_condition_or_result_fails",
    ),
    Mutation(
        "agent",
        "生成クエリだけに一致する商品も候補に含める",
        "packages/agent/src/chat_retrieval.py",
        " and (index == 0 or similarities[0] >= 0.39)",
        "",
        "packages/agent/tests/test_agent_retrieval.py::test_rewritten_similarity_needs_support_from_original_question",
    ),
    Mutation(
        "frontend",
        "候補の商品リンクがカタログのトップを指す",
        "packages/frontend/src/web_app/components/chat_views.py",
        'href="#/api/" + quote(product["id"], safe="")',
        'href="#/catalog"',
        "packages/frontend/tests/test_components.py::test_chat_product_and_guide_are_linked",
    ),
    Mutation(
        "infra",
        "モデルの予備領域を増やす",
        "packages/infra/src/components/chat.py",
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
        "tests/architecture/tools/test_design_sources.py::"
        "test_schema_field_uses_only_the_comment_on_its_declaration",
    ),
    Mutation(
        "backend",
        "設計解析に別名で正規表現を取り込む",
        "packages/backend/src/app/design_names.py",
        "import inspect",
        "import inspect\nimport re as parser",
        "tests/architecture/tools/test_design_sources.py::"
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
        "packages/frontend/src/web_app/content/openapi_fields.py",
        "for source in (item, operation):",
        "for source in (operation, item):",
        "packages/frontend/tests/test_openapi_fields.py::"
        "test_operation_overrides_path_parameter_and_resolves_pointer",
    ),
    Mutation(
        "frontend",
        "一覧の検索条件を常に展開する",
        "packages/frontend/src/web_app/components/list_layout.py",
        'with t.details(classes="list-disclosure", open=expanded):',
        'with t.details(classes="list-disclosure", open=True):',
        "packages/frontend/tests/test_components.py::test_log_search_starts_collapsed_and_shows_active_conditions",
    ),
    Mutation(
        "frontend",
        "ガイドの条件をクリアした後にフォーカスを戻さない",
        "packages/frontend/src/web_app/components/guide_views.py",
        '        document.getElementById("guide-query").focus()\n',
        "",
        "packages/frontend/tests/test_components.py::test_guide_reset_restores_role_and_keyboard_focus",
    ),
    Mutation(
        "infra",
        "Lambdaの割当メモリーを増やす",
        "packages/infra/src/components/functions.py",
        "memory_size=768,",
        "memory_size=1024,",
        "packages/infra/tests/test_cost.py::test_cost_drivers_are_bounded",
    ),
    Mutation(
        "infra",
        "リソースの管理者タグの値を誤る",
        "packages/infra/src/components/ownership.py",
        '"ManagedBy": "AWS-CDK"',
        '"ManagedBy": "Other"',
        "packages/infra/tests/test_stack.py::test_every_resource_has_ownership",
    ),
    Mutation(
        "infra",
        "ポータルURLのスタック出力名を変更する",
        "packages/infra/src/stack.py",
        'CfnOutput(self, "PortalUrl",',
        'CfnOutput(self, "ChangedPortalUrl",',
        "packages/infra/tests/test_cdk_regression.py::test_cloudformation_structure_matches_snapshot",
    ),
    Mutation(
        "bootstrap",
        "招待したユーザーと異なる識別子でも管理者にする",
        "packages/tools/operations/bootstrap_admin.py",
        'if not any(attr == {"Name": "sub", "Value": subject} for attr in user["UserAttributes"]):',
        "if False:",
        "packages/tools/tests/test_bootstrap_admin.py::test_replaced_user_cannot_be_promoted",
    ),
)


def copy_sources(workspace):
    ignore = shutil.ignore_patterns(
        "dist", "cdk.out", "node_modules", ".venv", "__pycache__", "*.egg-info"
    )
    for folder in ("packages", "deploy/config", "docs/examples", "tests"):
        shutil.copytree(ROOT / folder, workspace / folder, ignore=ignore)
    shutil.copyfile(ROOT / "pyproject.toml", workspace / "pyproject.toml")


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
