"""ワークスペースの依存宣言と実際のimportが、Verifyの選択条件に含まれることを確認する。"""

import ast
import tomllib

import yaml
from packaging.requirements import Requirement

from tools import ci_scope as ci

from .dependencies import dependencies, source_module
from .project import ROOT, project_files


def test_workspace_dependency_changes_verify_consumers():
    """各パッケージの依存宣言から逆依存をたどり、変更元と利用側の単体テストを選ぶ。"""
    projects = {}
    for file in (ROOT / "packages").glob("*/pyproject.toml"):
        with file.open("rb") as stream:
            project = tomllib.load(stream)["project"]
        deps = list(project["dependencies"])
        for optional in project.get("optional-dependencies", {}).values():
            deps.extend(optional)
        projects[project["name"]] = (
            file.parent.relative_to(ROOT),
            {Requirement(dep).name for dep in deps},
        )

    suites = ci.configured_suites()
    for name, (directory, _) in projects.items():
        consumers = {name}
        while True:
            found = {key for key, (_, deps) in projects.items() if consumers.intersection(deps)}
            if found <= consumers:
                break
            consumers.update(found)
        expected = {(projects[key][0] / "tests").as_posix() for key in consumers}
        assert expected <= set(suites), f"{name}: pytestの収集対象に未登録 {expected - set(suites)}"
        flags = ci.affected((directory / "pyproject.toml").as_posix(), suites)
        assert expected <= flags and "full" not in flags, (name, expected, flags)


def test_imported_modules_verify_their_actual_consumers():
    """実装が他の配布単位から読み込むモジュールを解析し、変更時に利用側のテストが選ばれる。"""
    files = {}
    suites = ci.configured_suites()
    for path in project_files(ROOT / "packages", ".py"):
        relative = path.relative_to(ROOT)
        if "tests" in relative.parts:
            continue
        module = source_module(relative).removesuffix(".__init__")
        files[module] = relative
    for module, path in files.items():
        suite = f"packages/{path.parts[1]}/tests"
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        for line, imported in dependencies(ast.parse((ROOT / path).read_bytes()), package):
            while imported and imported not in files:
                imported = imported.rpartition(".")[0]
            target = files.get(imported)
            if target is None or path.parts[:2] == target.parts[:2]:
                continue
            flags = ci.affected(target.as_posix(), suites)
            assert suite in flags, f"{path}:{line} が {target} を参照するため {suite} が必要"


def test_verify_skips_unrelated_packages_even_without_coverage(tmp_path):
    """PR説明・CSS・各層のテスト変更で、キャッシュがなくても無関係な層やCDKを起動しない。"""
    suites = ci.configured_suites()
    docs = [".github/pull_request_template.md", ".agents/skills/write-tsugite-pr/SKILL.md", "AGENTS.md"]
    plan = ci.select(docs, suites, tmp_path)
    assert not any(plan.values())
    assert ci.missing_parts(plan, suites, tmp_path) == []
    for suite in suites:
        plan = ci.select([suite + "/test_example.py"], suites, tmp_path)
        assert set(plan["suites"]) == {suite, ci.ARCHITECTURE}
        assert not any(plan[key] for key in ("full", "synth", "aws", "audit"))
    css = ci.select(["packages/frontend/public/ui.css"], suites, tmp_path)
    assert set(css["suites"]) == {ci.FRONTEND, ci.BROWSER, ci.ARCHITECTURE}
    assert not css["synth"] and not css["aws"]


def test_emulator_and_model_manifest_verify_deployment_inputs(tmp_path):
    """AWSエミュレーターは合成済みテンプレートを使い、モデル定義の変更はCDKの単体テストでも検証する。"""
    suites = ci.configured_suites()
    for path in (
        "packages/infra/cdk.json",
        "packages/agent/src/agent/models/manifest.json",
        "tests/e2e/aws/test_portal.py",
    ):
        plan = ci.select([path], suites, tmp_path)
        assert plan["aws"] and plan["synth"] and plan["chromium"], path
    assert ci.INFRA in ci.affected("packages/agent/src/agent/models/manifest.json", suites)


def test_workflow_runs_expensive_steps_only_for_selected_outputs():
    """Verifyが差分判定の出力を使い、対象外のCDK合成・AWS・ブラウザー・単体テストを起動しない。"""
    workflow = yaml.safe_load((ROOT / ".github/workflows/check.yml").read_text(encoding="utf-8"))
    steps = {step["run"]: step.get("if") for step in workflow["jobs"]["test"]["steps"] if "run" in step}
    for command, output in {
        "task synth": "synth",
        "task audit": "audit",
        "task emulator:install": "aws",
        "task browser:install": "chromium",
        "task docs:infra:render": "synth",
    }.items():
        assert steps[command] == f"steps.scope.outputs.{output} == 'true'", command
    run_suites = "uv run --locked --all-packages python -m tools.ci_scope --run-suites"
    assert steps[run_suites] == "steps.scope.outputs.suites != '[]'"
