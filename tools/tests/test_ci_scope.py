import subprocess
from pathlib import Path

from tools import ci_scope as ci

SUITES = [ci.BACKEND, ci.DATABASE, ci.FRONTEND, ci.INFRA, ci.BROWSER, ci.TOOLS]


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
    assert plan["suites"] == [ci.FRONTEND, ci.INFRA]
    assert not any(plan[key] for key in ("chromium", "synth", "audit", "aws", "types", "frontend_build"))


def test_css_and_authentication_have_different_consumers(tmp_path):
    """CSSは画面の検証を行い、認証クライアントの変更ではCognitoの画面操作も確認する。"""
    cached_report(tmp_path)
    css = ci.select(["packages/frontend/public/ui.css"], SUITES, tmp_path)
    assert css["suites"] == [ci.FRONTEND, ci.BROWSER]
    assert css["chromium"] and css["frontend_build"] and not css["aws"]
    auth = ci.select(["packages/frontend/src/web_app/client.py"], SUITES, tmp_path)
    assert auth["aws_portal_only"] and auth["aws"] and auth["synth"]


def test_frontend_builder_runs_stylesheet_and_design_policy_tests(tmp_path, monkeypatch):
    """画面のビルド処理を変えるとCSS解析とコード解析の規則も検査する。"""
    cached_report(tmp_path)
    monkeypatch.chdir(tmp_path)
    policy = Path(ci.BACKEND, "architecture/test_design_sources.py")
    policy.parent.mkdir(parents=True)
    policy.touch()
    plan = ci.select(["tools/build_frontend.py"], SUITES, tmp_path)
    assert {ci.BACKEND, ci.FRONTEND, ci.BROWSER, ci.TOOLS} == set(plan["suites"])


def test_infra_and_aws_require_browser_and_assets(tmp_path):
    """インフラの実装変更ではCDK・監査・AWSの画面連携に必要な環境を用意する。"""
    cached_report(tmp_path)
    plan = ci.select(["packages/infra/src/infra_app/stack.py"], SUITES, tmp_path)
    assert plan["suites"] == [ci.INFRA]
    assert all(plan[key] for key in ("synth", "aws", "audit", "chromium"))
    assert not plan["aws_portal_only"]


def test_measured_source_invalidates_suites_that_executed_it(tmp_path):
    """計測対象コードの変更時は以前に実行行を記録した層も再計測する。"""
    cached_report(tmp_path)
    (tmp_path / "coverage-parts" / ci.part_name(ci.INFRA)).write_bytes(b"measured")
    plan = ci.select(["packages/database/src/tsugite_db/models.py"], SUITES, tmp_path)
    assert set(plan["suites"]) == {ci.BACKEND, ci.DATABASE, ci.INFRA, ci.BROWSER, ci.TOOLS}
    assert plan["design"] and plan["types"] and plan["aws"]


def test_missing_coverage_never_becomes_a_partial_baseline(tmp_path):
    """計測結果を復元できない層は再実行して全体カバレッジに含める。"""
    plan = ci.select(["packages/frontend/tests/test_components.py"], SUITES, tmp_path)
    assert plan["suites"] == SUITES
    cached_report(tmp_path)
    (tmp_path / "coverage-parts" / ci.part_name(ci.DATABASE)).unlink()
    plan = ci.select(["packages/frontend/tests/test_components.py"], SUITES, tmp_path)
    assert plan["suites"] == [ci.DATABASE, ci.FRONTEND]


def test_unknown_or_shared_input_runs_all_checks(tmp_path):
    """未知の領域・依存ロック・CI定義を変更した場合は全検証を選ぶ。"""
    cached_report(tmp_path)
    for path in (
        "packages/new/code.py",
        "uv.lock",
        ".github/workflows/check.yml",
        "contracts/http.toml",
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
        "packages/infra/src/infra_app/stack.py",
        "packages/infra/app.py",
        "agent/worker.py",
        "agent/models/nested/inference.py",
    ]
    for name in [*sources, "packages/infra/tests/test_stack.py", "packages/infra/cdk.out/asset/copy.py"]:
        file = tmp_path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("def run():\n    return 123\n")
    config = Path(ci.__file__).resolve().parents[1] / "pyproject.toml"
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
    screen = "packages/frontend/src/web_app/guide_views.py"
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
