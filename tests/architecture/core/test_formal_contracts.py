"""要件の各方針が実在の検査につながり、Quintに孤立したケースが残らないことを確認する。"""

import ast
import json
import os
from pathlib import Path

import yaml

from packages.tools.design.requirements import DEFINITION, read_requirement

from .project import ROOT

FORMAL = ROOT / "tests/formal"


def replay_functions():
    domains = {}
    for path in (ROOT / "packages/backend/tests").glob("test_quint*.py"):
        for fn in ast.parse(path.read_text()).body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            for deco in fn.decorator_list:
                if not isinstance(deco, ast.Call) or len(deco.args) != 2:
                    continue
                source = deco.args[1]
                if (
                    isinstance(source, ast.Call)
                    and isinstance(source.func, ast.Name)
                    and source.func.id == "histories"
                ):
                    domain = ast.literal_eval(source.args[0])
                    assert domain not in domains, f"{domain}: 再生先の重複"
                    domains[domain] = f"{path.relative_to(ROOT)}::{fn.name}"
    return domains


def test_formal_requirement_coverage():
    """各方針から実在する受入テストや再生ケースを参照し、モデルの全ケースを使用する。"""
    cases = json.loads((FORMAL / "cases.json").read_text())
    drivers = replay_functions()
    assert set(drivers) == {path.stem for path in FORMAL.glob("*.qnt")}
    used = set()
    report = [
        "# 用語・要件から検証方法をたどる",
        "",
        "用語は要件の表題と定義元から取得する。各行の方針と検証範囲を併せて確認する。",
    ]
    term_sources = {}
    for path in sorted((ROOT / "docs/requirements/items").glob("*.md")):
        requirement = read_requirement(path)
        body = requirement.body
        terms = requirement.terms | {term for term, _ in DEFINITION.findall(body)}
        for term in terms:
            term_sources.setdefault(term, []).append(path.stem)
        report.extend(["", f"## {path.stem}", "", "用語　" + "、".join(sorted(terms))])
        policy, tests = body.split("## 決めた方針\n", 1)[1].split("### 受入テスト", 1)
        nodes = {
            line.split(chr(96))[1] for line in tests.splitlines() if line.startswith("- 受入テスト ")
        }
        blocks = policy.strip().split("\n\n")
        assert len(blocks) % 2 == 0, f"{path.name}: 方針段落ごとに検証方法を指定してください"
        for clause, evidence in zip(blocks[::2], blocks[1::2], strict=True):
            assert clause.strip() and not clause.startswith("> "), (path, clause)
            report.extend(["", clause, ""])
            for line in evidence.splitlines():
                prefix, sep, reason = line.partition(" — ")
                assert sep and reason.strip(), (path, line)
                kind, _, keys = prefix.partition(" ")
                assert kind == ">", (path, line)
                method, _, refs = keys.partition(" ")
                assert method in ("Quint", "実装検証") and refs.strip(), (path, line)
                for ref in refs.split():
                    if method == "Quint":
                        assert ref in cases, (path, ref)
                        assert drivers[ref.split(".")[0]] in nodes, (
                            path,
                            ref,
                            "再生先の受入テストがありません",
                        )
                        used.add(ref)
                        report.append(f"- `{ref}` → `{drivers[ref.split('.')[0]]}`　{reason}")
                    else:
                        matches = sorted(node for node in nodes if node.endswith("::" + ref))
                        assert matches, (path, ref)
                        report.extend(f"- `{node}`　{reason}" for node in matches)
    assert used == set(cases), f"要件に対応しないケース: {set(cases) - used}"
    if destination := os.getenv("FORMAL_COVERAGE_REPORT"):
        index = ["", "## 用語索引", ""]
        index.extend(
            f"- **{term}**　" + "／".join(titles) for term, titles in sorted(term_sources.items())
        )
        Path(destination).write_text("\n".join(report + index) + "\n", encoding="utf-8")


def test_verify_runs_models_and_replays():
    """Verifyが一覧と操作列を再生成し、モデル検査・実装再生と証跡の保存を毎回実行する。"""
    workflow = yaml.load((ROOT / ".github/workflows/check.yml").read_text(), Loader=yaml.BaseLoader)
    plan = workflow["jobs"]["plan"]["steps"]
    assert any(step.get("run") == "bash tests/formal/check.sh" and "if" not in step for step in plan)
    artifact = next(
        step["with"] for step in plan if step.get("with", {}).get("name") == "formal-verification"
    )
    assert {"docs/generated/formal/domains.md", "tests/formal/*.qnt"} <= set(
        artifact["path"].splitlines()
    )
    script = (FORMAL / "check.sh").read_text()
    for command in (
        'python3 tests/formal/document.py --quint "$quint" --check',
        "tests/formal/generate.py",
        "--backend=tlc --invariant=safe",
        "packages/backend/tests/test_quint",
    ):
        assert command in script
