"""Gitの差分から実行計画を作り、単体テストの計測を合算する経路を検証する。"""

import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest

from packages.tools.ci import check_coverage, ci_coverage_parts, ci_scope


def git(repo, *args):
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path / "runner"))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "outputs"))
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/project")
    monkeypatch.setenv("BASE_BRANCH", "main")
    # この作業ツリーで合算する計測は、外側のパッケージ単体テストの記録先と分ける。
    monkeypatch.setenv("COVERAGE_FILE", str(tmp_path / ".coverage"))
    for inherited in (
        "COVERAGE_PROCESS_START",
        "COV_CORE_SOURCE",
        "COV_CORE_CONFIG",
        "COV_CORE_DATAFILE",
    ):
        monkeypatch.delenv(inherited, raising=False)
    (tmp_path / "runner").mkdir()
    suites = ["packages/frontend/tests", "packages/tools/tests"]
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n"
        f"testpaths = {json.dumps(suites)}\n"
        'pythonpath = ["."]\n'
        "[tool.coverage.run]\n"
        'branch = true\nrelative_files = true\nsource = ["packages/frontend", "packages/tools"]\n'
        'omit = ["*/tests/*"]\n'
    )
    for name in ["frontend", "tools"]:
        directory = tmp_path / "packages" / name
        (directory / "tests").mkdir(parents=True)
        (directory / "__init__.py").touch()
        (directory / "sample.py").write_text("def number():\n    return 7\n")
        (directory / "tests" / f"test_{name}.py").write_text(
            f"from packages.{name}.sample import number\n\ndef test_number():\n    assert number() == 7\n"
        )
    for support in [
        "packages/tools/packaging/build_frontend.py",
        "tests/e2e/browser/conftest.py",
        "tests/support/pyodide_trace.py",
    ]:
        stub = tmp_path / support
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.touch()
    git(tmp_path, "init", "-qb", "feat/plan")
    git(tmp_path, "config", "user.name", "開発者")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        pytest.param(
            ".github/pull_request_template.md",
            [],
            id="template",
            marks=pytest.mark.case_detail("PRテンプレートのみでは単体テストを起動しない"),
        ),
        pytest.param(
            "packages/frontend/tests/test_screen.py",
            ["packages/frontend/tests"],
            id="unit",
            marks=pytest.mark.case_detail("画面の単体テストの追加ではフロントのスイートだけを選択する"),
        ),
    ],
)
def test_plan_records_changed_suites_and_baseline_gaps(project, monkeypatch, document, expected):
    """PR用の実行計画と比較元で補完する計測を分けてGitHubの出力に記録する。"""
    base = git(project, "rev-parse", "HEAD")
    path = project / document
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# 新しい条件\n")
    git(project, "add", ".")
    git(project, "commit", "-qm", "feature")
    monkeypatch.setattr(ci_scope, "download_merged_coverage", lambda *args: False)
    ci_scope.inspect_base(base)
    ci_scope.plan(base)
    plan = json.loads((project / "artifacts/ci-plan.json").read_text())
    outputs = dict(line.split("=", 1) for line in (project / "outputs").read_text().splitlines())
    assert plan["suites"] == json.loads(outputs["suites"]) == expected
    assert plan["coverage"] == bool(expected)
    assert plan["setup"] == bool(expected)
    assert json.loads(outputs["missing"]) == (["packages/tools/tests"] if expected else [])


def test_selected_suites_retain_separate_measurements_and_combined_result(project):
    """パッケージ別ジョブと集約ジョブのJUnitを残し、合算したXMLに両方の実行行を反映する。"""
    suites = ["packages/frontend/tests", "packages/tools/tests"]
    artifacts = project / "artifacts"
    artifacts.mkdir()
    (artifacts / "ci-plan.json").write_text(json.dumps({"suites": suites, "packages": ["frontend"]}))
    ci_coverage_parts.run_parts([suites[0]])
    package_junit = artifacts / "packages-frontend-tests.xml"
    recorded = package_junit.read_bytes()
    ci_scope.run_suites()
    assert package_junit.read_bytes() == recorded
    combined = ElementTree.parse(artifacts / "junit.xml").findall(".//testcase")
    assert {case.get("classname") for case in combined} == {
        "packages.frontend.tests.test_frontend",
        "packages.tools.tests.test_tools",
    }
    root = ElementTree.parse(artifacts / "coverage.xml").getroot()
    assert int(root.attrib["lines-covered"]) == int(root.attrib["lines-valid"]) == 4
    for suite in suites:
        assert (artifacts / "coverage-parts" / ci_coverage_parts.part_name(suite)).stat().st_size > 0
        junit = artifacts / f"{suite.replace('/', '-')}.xml"
        cases = ElementTree.parse(junit).findall(".//testcase")
        assert len(cases) == 1 and cases[0].get("name") == "test_number"


def test_suite_failure_reports_which_run_failed(project):
    """テストが失敗したスイート名を示して不合格にし、そのJUnitを保存する。"""
    suite = "packages/tools/tests"
    (project / suite / "test_tools.py").write_text("def test_failure():\n    assert False\n")
    with pytest.raises(SystemExit, match=suite):
        ci_coverage_parts.run_parts([suite])
    junit = project / "artifacts/packages-tools-tests.xml"
    assert ElementTree.parse(junit).find(".//testcase/failure") is not None


@pytest.mark.parametrize(
    "per_suite",
    [
        pytest.param(
            False,
            id="whole-baseline",
            marks=pytest.mark.case_detail("全体の比較元には分岐点のテストの行数を使う"),
        ),
        pytest.param(
            True,
            id="missing-suite",
            marks=pytest.mark.case_detail("欠けたスイートだけを比較元で補完する"),
        ),
    ],
)
def test_baseline_measurement_uses_clean_checkout(project, monkeypatch, per_suite):
    """比較元の計測は分岐点のクリーンな作業ツリーで行い、PR側の編集を保持する。"""
    suite = "packages/tools/tests"
    tracked = Path("packages/tools/sample.py")
    (project / tracked).write_text("def number():\n    return 8\n")
    base = git(project, "rev-parse", "HEAD")
    real_run = subprocess.run
    executions = []

    def run(command, *args, **kwargs):
        if command[0] == "git":
            return real_run(command, *args, **kwargs)
        directory = Path(kwargs["cwd"])
        assert "return 7" in (directory / tracked).read_text()
        if "pytest" in command:
            executions.append(directory)
            out = directory / "artifacts"
            out.mkdir(exist_ok=True)
            (out / "coverage.xml").write_text('<coverage lines-covered="91" lines-valid="100"/>')
        elif any(str(arg).endswith("ci_coverage_parts.py") for arg in command):
            assert command[-1] == suite
            executions.append(directory)
            parts = directory / "artifacts/coverage-parts"
            parts.mkdir(parents=True, exist_ok=True)
            (parts / ci_coverage_parts.part_name(suite)).write_bytes(b"isolated measurement")
            (parts / "packages-tools-tests.json").write_text("[]")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", run)
    if per_suite:
        ci_scope.measure_missing_base_parts(base, [suite])
        cache_files = list((project / "runner").rglob("packages-tools-tests.sqlite"))
        assert len(cache_files) == 1 and cache_files[0].read_bytes() == b"isolated measurement"
    else:
        assert check_coverage.measure_base_coverage(base) == 91
    assert len(executions) == 1 and not executions[0].exists()
    assert "return 8" in (project / tracked).read_text()


@pytest.mark.parametrize(
    ("changed", "checks", "suites"),
    [
        pytest.param(
            "packages/frontend/src/web_app/content/guide_search.py",
            ["types"],
            [
                "packages/agent/tests",
                "packages/frontend/tests",
                "packages/backend/tests",
                "tests/e2e/browser",
            ],
            id="guide-search",
            marks=pytest.mark.case_detail("共有するガイド検索の変更は推論、画面、APIの検証に波及する"),
        ),
        pytest.param(
            "packages/frontend/src/web_app/content/guide_content.py",
            ["types"],
            ["packages/agent/tests", "packages/frontend/tests", "tests/e2e/browser"],
            id="guide-articles",
            marks=pytest.mark.case_detail("共通のガイド本文を変えたら画面と推論の両方を検証する"),
        ),
        pytest.param(
            "packages/frontend/typings/js.pyi",
            ["types"],
            ["packages/frontend/tests"],
            id="browser-stubs",
            marks=pytest.mark.case_detail("ブラウザー型スタブの変更は型検査とフロント単体を選ぶ"),
        ),
        pytest.param(
            "packages/infra/src/stack.py",
            ["synth", "audit"],
            ["packages/infra/tests"],
            id="stack",
            marks=pytest.mark.case_detail("スタック全体の変更はインフラ単体と合成・監査を選ぶ"),
        ),
        pytest.param(
            "packages/backend/src/app/core/log_record.py",
            ["types"],
            ["packages/agent/tests", "packages/backend/tests", "packages/tools/tests"],
            id="shared-logs",
            marks=pytest.mark.case_detail(
                "共通のログ形式を変えたらAPIと推論・開発ツールの利用箇所も検証する"
            ),
        ),
        pytest.param(
            ".githooks/pre-commit",
            ["hooks"],
            [],
            id="git-hooks",
            marks=pytest.mark.case_detail("フックの変更はフック検証を起動する"),
        ),
        pytest.param(
            "docs/requirements/items/追加.md",
            ["full"],
            [],
            id="requirement",
            marks=pytest.mark.case_detail("要件定義の追加は全層の受入テストを選ぶ"),
        ),
        pytest.param(
            "docs/generated/README.md",
            ["design"],
            ["packages/tools/tests"],
            id="generated",
            marks=pytest.mark.case_detail("生成設計書の変更では設計生成とツール検証を選ぶ"),
        ),
        pytest.param(
            "packages/sample_api/src/sample_api/core/database.py",
            ["synth", "design", "aws"],
            ["packages/sample_api/tests"],
            id="sample",
            marks=pytest.mark.case_detail("サンプルAPIの変更は専用テストと配備・契約の検証を選ぶ"),
        ),
        pytest.param(
            "packages/tools/packaging/build_backend.py",
            ["synth", "audit"],
            [],
            id="runtime",
            marks=pytest.mark.case_detail("実行Layerの変更時は合成と依存監査を実行する"),
        ),
        pytest.param(
            "packages/tools/packaging/build_chat.py",
            ["synth", "audit"],
            ["packages/model/tests"],
            id="model",
            marks=pytest.mark.case_detail("推論用配布物の変更時はモデル単体とリソースを検査する"),
        ),
        pytest.param(
            "packages/agent/src/chat_jobs.py",
            ["synth", "types", "aws"],
            ["packages/agent/tests", "packages/backend/tests"],
            id="agent-job",
            marks=pytest.mark.case_detail(
                "チャットジョブの変更時はエージェント単体とAPIの連携を検証する"
            ),
        ),
        pytest.param(
            "packages/model/src/decision.py",
            ["synth", "types", "aws"],
            ["packages/model/tests", "packages/infra/tests"],
            id="decision-handler",
            marks=pytest.mark.case_detail(
                "判定ハンドラーの変更時は独立したモデルと配備先のテストを選ぶ"
            ),
        ),
        pytest.param(
            "tests/e2e/aws/test_portal.py",
            ["aws", "chromium"],
            [],
            id="emulator",
            marks=pytest.mark.case_detail("AWSの画面操作テストにはエミュレーターとブラウザーを用意する"),
        ),
        pytest.param(
            "tests/e2e/browser/test_portal.py",
            ["chromium", "frontend_build"],
            ["tests/e2e/browser"],
            id="browser",
            marks=pytest.mark.case_detail("画面操作テストの変更時は画面とブラウザーを用意する"),
        ),
        pytest.param(
            "packages/tools/design/generate.py",
            ["design"],
            ["packages/tools/tests"],
            id="api-design",
            marks=pytest.mark.case_detail("API設計の生成変更は生成とツール単体を検証する"),
        ),
        pytest.param(
            "packages/tools/demo/seed_marketplace.py",
            ["aws"],
            ["tests/e2e/browser"],
            id="seed",
            marks=pytest.mark.case_detail("デモ商品の変更は実際の画面とAWSで確認する"),
        ),
        pytest.param(
            "tests/architecture/core/test_documents.py",
            ["lint"],
            ["tests/architecture"],
            id="architecture",
            marks=pytest.mark.case_detail("構造規則のテストを変更するとそのスイートを起動する"),
        ),
    ],
)
def test_changed_consumer_plan_keeps_each_required_check(tmp_path, changed, checks, suites):
    """変更した分野が必要とするテストと検査を差分計画に含める。"""
    configured = ci_scope.configured_suites()
    plan = ci_scope.select([changed], configured, tmp_path)
    assert all(plan[check] for check in checks)
    assert set(suites) <= set(plan["suites"])
    if plan["full"]:
        assert plan["suites"] == configured


def test_document_only_plan_copies_verified_aggregate(project, monkeypatch):
    """文書だけを変更した場合、検証済みの全体計測を保存し、追加のテストを要求しない。"""
    base = git(project, "rev-parse", "HEAD")
    (project / "README.md").write_text("# 仕様\n")
    git(project, "add", "README.md")
    git(project, "commit", "-qm", "document")
    xml = '<coverage lines-covered="92" lines-valid="100"/>'
    cache = ci_scope.scope_inputs(base)[3]
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "coverage-parts").mkdir()
    (cache / "coverage-parts/policy.sha256").write_text(check_coverage.coverage_policy())
    (cache / "coverage.xml").write_text(xml)
    ci_scope.plan(base)
    out = project / "artifacts"
    plan = json.loads((out / "ci-plan.json").read_text())
    assert plan["reuse_xml"] and not plan["suites"]
    assert (out / "coverage.xml").read_text() == xml


def test_quality_document_links_selected_commit_and_live_policy(project, monkeypatch):
    """完了条件のCI成果物は適用ルールの値を示し、検証したコミットのソースにリンクする。"""
    from packages.tools.design import completion

    for package, label in (("agent", "エージェント"), ("model", "推論モデル")):
        directory = project / "packages" / package
        (directory / "tests").mkdir(parents=True)
        (directory / "pyproject.toml").write_text(f'[tool.tsugite.verify]\nlabel = "{label}"\n')
    rules = [{"type": "code_coverage", "parameters": {"minimum_coverage": 91, "max_coverage_drop": 2}}]
    path = project / "rules.json"
    path.write_text(json.dumps(rules))
    monkeypatch.setenv("GITHUB_SHA", "base-for-document")
    monkeypatch.setenv("PR_HEAD_SHA", "verified-commit")
    monkeypatch.setattr("sys.argv", ["completion", "--rules-file", str(path), "--artifact"])
    completion.main()
    doc = (project / "artifacts/definition-of-done.md").read_text()
    assert "エージェント" in doc and "推論モデル" in doc
    assert "91%以上" in doc and "2ポイント以内" in doc
    assert "verified-commit" in doc and "check.yml" in doc


@pytest.mark.parametrize(
    "exercise_both",
    [
        pytest.param(
            True,
            id="pass",
            marks=pytest.mark.case_detail("両方向を通る単体テストの計測で行と分岐の基準を満たす"),
        ),
        pytest.param(
            False,
            id="fail",
            marks=pytest.mark.case_detail("一方向しか通らない単体テストの計測を不合格にする"),
        ),
    ],
)
def test_package_gate_reads_own_suite_measurement(project, exercise_both):
    """各パッケージ自身のpytest計測ファイルを読み、実測した行と分岐の達成度で判定する。"""
    from packages.tools.ci import unit_coverage

    package = project / "packages/tools"
    (package / "pyproject.toml").write_text('[project]\nname = "tools"\n')
    with (project / "pyproject.toml").open("a") as config:
        config.write("[tool.tsugite.unit-coverage]\nline=90\nbranch=85\n")
    (package / "sample.py").write_text("def number(ok):\n    if ok:\n        return 7\n    return 3\n")
    test = (
        "from packages.tools.sample import number\n\ndef test_number():\n    assert number(True) == 7\n"
    )
    if exercise_both:
        test += "    assert number(False) == 3\n"
    (package / "tests/test_tools.py").write_text(test)
    ci_coverage_parts.run_parts(["packages/tools/tests"])
    if exercise_both:
        unit_coverage.main()
    else:
        with pytest.raises(SystemExit, match="tools"):
            unit_coverage.main()


def test_plan_preserves_untouched_suite_cache(project):
    """単体テストを片方だけ変更したとき、比較元の他方の計測を再利用し合算結果に含める。"""
    base = git(project, "rev-parse", "HEAD")
    frontend = "packages/frontend/tests"
    tools = "packages/tools/tests"
    ci_coverage_parts.run_parts([tools])
    cache = ci_scope.scope_inputs(base)[3]
    cache.mkdir(parents=True, exist_ok=True)
    original = project / "artifacts/coverage-parts"
    saved = cache / "coverage-parts"
    original.rename(saved)
    (saved / "policy.sha256").write_text(check_coverage.coverage_policy())
    path = project / frontend / "test_frontend.py"
    path.write_text(path.read_text() + "\n# 新しい検証\n")
    git(project, "add", frontend)
    git(project, "commit", "-qm", "frontend")
    ci_scope.plan(base)
    assert json.loads((project / "artifacts/ci-plan.json").read_text())["suites"] == [frontend]
    sqlite = ci_coverage_parts.part_name(tools)
    assert (original / sqlite).read_bytes() == (saved / sqlite).read_bytes()
    ci_scope.run_suites()
    coverage = ElementTree.parse(project / "artifacts/coverage.xml").getroot()
    assert coverage.get("lines-covered") == coverage.get("lines-valid") == "4"


@pytest.mark.parametrize(
    "chosen",
    [
        pytest.param(
            "agent",
            id="agent",
            marks=pytest.mark.case_detail(
                "エージェントの単体テスト変更はエージェントのジョブで検証する"
            ),
        ),
        pytest.param(
            "model",
            id="model",
            marks=pytest.mark.case_detail("モデルの単体テスト変更はモデルのジョブで検証する"),
        ),
    ],
)
def test_independent_lambda_package_job_matches_changed_suite(project, chosen):
    """一方のLambdaの単体テストだけを更新すると、そのパッケージをCIの行列と計画に含める。"""
    suites = ["packages/agent/tests", "packages/model/tests"]
    (project / "pyproject.toml").write_text(
        f"[tool.pytest.ini_options]\ntestpaths = {json.dumps(suites)}\n"
    )
    for package, label in (("agent", "エージェント"), ("model", "推論モデル")):
        directory = project / "packages" / package
        (directory / "tests").mkdir(parents=True)
        (directory / "pyproject.toml").write_text(
            f'[project]\nname = "tsugite-{package}"\n[tool.tsugite.verify]\nlabel = "{label}"\n'
        )
    git(project, "add", ".")
    git(project, "commit", "-qm", "independent packages")
    base = git(project, "rev-parse", "HEAD")
    suite = f"packages/{chosen}/tests"
    (project / suite / "test_handler.py").write_text("def test_handler():\n    assert True\n")
    git(project, "add", suite)
    git(project, "commit", "-qm", "change unit test")
    ci_scope.plan(base)
    plan = json.loads((project / "artifacts/ci-plan.json").read_text())
    outputs = dict(line.split("=", 1) for line in (project / "outputs").read_text().splitlines())
    assert plan["suites"] == [suite]
    assert plan["packages"] == json.loads(outputs["packages"]) == [chosen]
