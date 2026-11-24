import subprocess
from pathlib import Path

from tools.ci import ci_scope as ci

SUITES = [ci.AGENT, ci.BACKEND, ci.DATABASE, ci.FRONTEND, ci.INFRA, ci.BROWSER, ci.TOOLS]


def cached_report(folder):
    parts = folder / "coverage-parts"
    parts.mkdir()
    for suite in SUITES:
        (parts / ci.part_name(suite)).touch()
    (folder / "coverage.xml").touch()


def test_docs_reuse_complete_report(tmp_path):
    """説明文のみの変更は既存の全体カバレッジを引き継ぎ、実行環境の準備を省ける。"""
    cached_report(tmp_path)
    plan = ci.select(["README.md", "docs/design/portal.md"], SUITES, tmp_path)
    assert plan["reuse_xml"]
    assert not any(value for key, value in plan.items() if key != "reuse_xml")


def test_component_tests_and_mixed_changes(tmp_path):
    """単体テストの変更は該当層に絞り、複数層の変更は両方を選ぶ。"""
    cached_report(tmp_path)
    files = [
        "packages/frontend/tests/test_components.py",
        "packages/infra/tests/cloudformation_snapshot.json",
    ]
    plan = ci.select(files, SUITES, tmp_path)
    assert plan["types"]
    assert plan["suites"] == [ci.FRONTEND, ci.INFRA]
    assert not any(plan[key] for key in ("chromium", "synth", "audit", "aws", "frontend_build"))


def test_css_and_authentication_have_different_consumers(tmp_path):
    """CSSは画面の検証を行い、認証クライアントの変更ではCognitoの画面操作も確認する。"""
    cached_report(tmp_path)
    css = ci.select(["packages/frontend/public/ui.css"], SUITES, tmp_path)
    assert css["suites"] == [ci.FRONTEND, ci.BROWSER]
    assert css["chromium"] and css["frontend_build"] and not css["aws"]
    auth = ci.select(["packages/frontend/src/web_app/apis/client.py"], SUITES, tmp_path)
    assert auth["aws_portal_only"] and auth["aws"] and auth["synth"]


def test_frontend_builder_runs_stylesheet_and_design_policy_tests(tmp_path):
    """画面のビルド処理を変えるとCSS解析とコード解析の規則も検査する。"""
    cached_report(tmp_path)
    suites = [*SUITES, ci.ARCHITECTURE]
    (tmp_path / "coverage-parts" / ci.part_name(ci.ARCHITECTURE)).touch()
    plan = ci.select(["tools/packaging/build_frontend.py"], suites, tmp_path)
    assert {ci.ARCHITECTURE, ci.FRONTEND, ci.BROWSER, ci.TOOLS} == set(plan["suites"])


def test_infra_and_aws_require_browser_and_assets(tmp_path):
    """インフラの実装変更ではCDK・監査・AWSの画面連携に必要な環境を用意する。"""
    cached_report(tmp_path)
    plan = ci.select(["packages/infra/src/stack.py"], SUITES, tmp_path)
    assert plan["suites"] == [ci.INFRA]
    assert all(plan[key] for key in ("synth", "aws", "audit", "chromium"))
    assert not plan["aws_portal_only"]


def test_measured_source_invalidates_suites_that_executed_it(tmp_path):
    """計測対象コードの変更時は以前に実行行を記録した層も再計測する。"""
    cached_report(tmp_path)
    (tmp_path / "coverage-parts" / ci.part_name(ci.INFRA)).write_bytes(b"measured")
    plan = ci.select(["packages/database/src/tsugite_db/models/assets.py"], SUITES, tmp_path)
    assert set(plan["suites"]) == {ci.AGENT, ci.BACKEND, ci.DATABASE, ci.INFRA, ci.BROWSER, ci.TOOLS}
    assert plan["design"] and plan["types"] and plan["aws"]


def test_missing_coverage_never_becomes_a_partial_baseline(tmp_path):
    """保存結果がない層は比較元での補完対象にし、PRの実行対象とは区別する。"""
    plan = ci.select(["packages/frontend/tests/test_components.py"], SUITES, tmp_path)
    assert plan["suites"] == [ci.FRONTEND]
    assert set(ci.missing_parts(plan, SUITES, tmp_path)) == set(SUITES) - {ci.FRONTEND}
    cached_report(tmp_path)
    (tmp_path / "coverage-parts" / ci.part_name(ci.DATABASE)).unlink()
    plan = ci.select(["packages/frontend/tests/test_components.py"], SUITES, tmp_path)
    assert plan["suites"] == [ci.FRONTEND]
    assert ci.missing_parts(plan, SUITES, tmp_path) == [ci.DATABASE]


def test_unknown_or_shared_input_runs_all_checks(tmp_path):
    """未知の領域・依存ロック・CI定義を変更した場合は全検証を選ぶ。"""
    cached_report(tmp_path)
    for path in (
        "packages/new/code.py",
        "uv.lock",
        ".github/workflows/check.yml",
        "deploy/config/http.toml",
    ):
        plan = ci.select([path], SUITES, tmp_path)
        assert plan["full"] and plan["suites"] == SUITES
        assert plan["types"] and plan["audit"] and plan["aws"] and plan["design"]


def test_git_diff_includes_deleted_and_both_renamed_paths(tmp_path, monkeypatch):
    """日本語と空白を含むパスの移動と削除を移動元も含めて判定する。"""
    monkeypatch.chdir(tmp_path)

    def git(*args):
        subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], check=True)

    git("init", "-q")
    old = Path("古い 名前.md")
    new = Path("移動先.md")
    removed = Path("削除.md")
    for path in (old, removed):
        path.write_bytes(b"test\n")
    git("add", ".")
    git("-c", "user.name=CI", "-c", "user.email=ci@example.invalid", "commit", "-qm", "base")
    old.rename(new)
    removed.unlink()
    git("add", "-A")
    git("-c", "user.name=CI", "-c", "user.email=ci@example.invalid", "commit", "-qm", "head")
    assert set(ci.changed_paths("HEAD^")) == {str(old), str(new), str(removed)}


def test_coverage_includes_all_runtime_layers_and_unexecuted_files(tmp_path, monkeypatch):
    """全領域の実行行と未実行行を区別し、未読込のモデルとインフラの入口も分母に含める。"""
    import json
    import os
    import sys

    sources = [
        "packages/backend/src/app/api.py",
        "packages/database/src/tsugite_db/session.py",
        "packages/frontend/src/web_app/app.py",
        "packages/infra/src/stack.py",
        "packages/infra/app.py",
        "packages/agent/src/agent/worker.py",
        "packages/agent/src/agent/models/nested/inference.py",
    ]
    for name in [*sources, "packages/infra/tests/test_stack.py", "packages/infra/cdk.out/asset/copy.py"]:
        file = tmp_path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("def run():\n    return 123\n")
    config = Path(ci.__file__).resolve().parents[2] / "pyproject.toml"
    command = [sys.executable, "-m", "coverage"]
    env = {**os.environ, "COVERAGE_FILE": str(tmp_path / ".coverage")}
    subprocess.run(
        [*command, "run", f"--rcfile={config}", sources[2]], cwd=tmp_path, env=env, check=True
    )
    subprocess.run([*command, "json", f"--rcfile={config}"], cwd=tmp_path, env=env, check=True)
    files = json.loads((tmp_path / "coverage.json").read_text())["files"]
    files = {Path(name).as_posix(): data for name, data in files.items()}
    assert set(files) == set(sources)
    assert files[sources[2]]["executed_lines"] == [1]
    assert files[sources[2]]["missing_lines"] == [2]
    assert all(files[name]["missing_lines"] == [1, 2] for name in sources if name != sources[2])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COVERAGE_FILE", env["COVERAGE_FILE"])
    report = tmp_path / "coverage.xml"
    ci.write_coverage_report(report)
    assert {entry.attrib["filename"] for entry in ci.ElementTree.parse(report).iter("class")} == set(
        sources
    )


def test_changed_screen_invalidates_only_suites_that_executed_it(tmp_path):
    """画面変更時はその画面を実行した別の層を再計測し、無関係な層の結果を再利用する。"""
    import json

    cached_report(tmp_path)
    screen = "packages/frontend/src/web_app/components/guide_views.py"
    for suite, files in [(ci.DATABASE, [screen]), (ci.INFRA, ["packages/infra/app.py"])]:
        part = tmp_path / "coverage-parts" / ci.part_name(suite)
        part.write_bytes(b"measured")
        part.with_suffix(".json").write_text(json.dumps(files))
    plan = ci.select([screen], SUITES, tmp_path)
    assert set(plan["suites"]) == {ci.FRONTEND, ci.DATABASE, ci.BROWSER}


def test_cache_requires_same_coverage_policy(tmp_path):
    """旧形式または異なる計測条件の結果は再利用せず、同じ条件の結果だけを使う。"""
    marker = tmp_path / ci.POLICY_FILE
    marker.parent.mkdir()
    assert not ci.compatible_coverage(tmp_path)
    marker.write_text("legacy")
    assert not ci.compatible_coverage(tmp_path)
    marker.write_text(ci.coverage_policy())
    assert ci.compatible_coverage(tmp_path)


def test_baseline_retry_requires_only_browser_timeouts(tmp_path):
    """比較元でブラウザーのタイムアウトだけが起きた場合に限り再計測する。"""
    from tools.ci.check_coverage import only_browser_timeouts

    junit = tmp_path / "junit.xml"
    for elements, retry in [
        ("", False),
        ("<failure>playwright._impl._errors.TimeoutError</failure>", True),
        ("<failure>AssertionError</failure>", False),
        ("<failure>playwright._impl._errors.TimeoutError</failure><error/>", False),
    ]:
        junit.write_text(f"<testsuite><testcase>{elements}</testcase></testsuite>")
        assert only_browser_timeouts(junit) is retry


def test_agent_sources_select_agent_consumers_and_deployment_checks(tmp_path):
    """エージェントとモデルの変更で単体・API結合・構造・型・配布物の検査を選ぶ。"""
    cached_report(tmp_path)
    suites = [*SUITES, ci.ARCHITECTURE]
    (tmp_path / "coverage-parts" / ci.part_name(ci.ARCHITECTURE)).touch()
    for path in ("jobs.py", "models/decision.py", "models/manifest.json"):
        plan = ci.select(["packages/agent/src/agent/" + path], suites, tmp_path)
        assert set(plan["suites"]) == {ci.AGENT, ci.BACKEND, ci.ARCHITECTURE, ci.BROWSER, ci.INFRA}
        assert all(plan[key] for key in ("types", "aws", "synth", "audit"))
        assert not plan["full"]


def test_moved_agent_reuses_only_aggregate_baseline(monkeypatch):
    """移動前と同じ範囲の総カバレッジを比較に使い、古いパスのスイート別結果は再利用しない。"""
    from tools.ci import check_coverage

    def download(repository, branch, sha, folder):
        base = Path(folder)
        marker = base / ci.POLICY_FILE
        marker.parent.mkdir()
        marker.write_text(check_coverage.coverage_policy(legacy_agent=True))
        (base / "coverage.xml").write_text('<coverage lines-covered="9" lines-valid="10"/>')
        assert not ci.compatible_coverage(base)
        return True

    monkeypatch.setattr(check_coverage, "download_merged_coverage", download)
    assert check_coverage.merged_pr_coverage("owner/repo", "main", "sha") == 90


def test_lock_changes_follow_transitive_old_and_new_consumers():
    """間接依存の更新は利用パッケージに絞り、移動した依存は変更前と変更後の両方を検証する。"""
    from copy import deepcopy

    old = {
        "package": [
            {
                "name": "infra",
                "source": {"editable": "packages/infra"},
                "dependencies": [{"name": "cdk"}],
            },
            {"name": "frontend", "source": {"editable": "packages/frontend"}},
            {"name": "cdk", "source": {}, "dependencies": [{"name": "shared"}]},
            {"name": "shared", "source": {}, "version": "1"},
        ]
    }
    new = deepcopy(old)
    new["package"][3]["version"] = "2"
    assert ci.lock_projects(old, new) == {"packages/infra/pyproject.toml"}
    new["package"][2]["dependencies"] = []
    new["package"][1]["optional-dependencies"] = {"extra": [{"name": "shared"}]}
    assert ci.lock_projects(old, new) == {
        "packages/infra/pyproject.toml",
        "packages/frontend/pyproject.toml",
    }
    new["revision"] = 2
    assert ci.lock_projects(old, new) == {"uv.lock"}


def test_template_plan_never_bootstraps_coverage(tmp_path, monkeypatch):
    """PRテンプレートだけの差分はキャッシュがなくても準備やテストを起動せず、空の計測を公開しない。"""
    import json

    cached = tmp_path / "cache"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "outputs"))
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/project")
    monkeypatch.setenv("BASE_BRANCH", "main")
    monkeypatch.setattr(
        ci, "scope_inputs", lambda _: ("abc", [".github/pull_request_template.md"], SUITES, cached)
    )
    monkeypatch.setattr(ci, "download_merged_coverage", lambda *args: False)
    ci.inspect_base("abc")
    ci.plan("abc")
    result = json.loads((ci.ARTIFACTS / "ci-plan.json").read_text())
    assert result["documents"] and not result["suites"]
    assert not any(result[key] for key in ("setup", "coverage", "chromium", "aws", "synth"))
    lines = (tmp_path / "outputs").read_text().splitlines()
    assert "missing=[]" in lines and "coverage_base=abc" in lines
