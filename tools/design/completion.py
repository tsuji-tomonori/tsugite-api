"""PRのワークフロー、検査設定、テストの定義から完了の定義を生成する。"""

import argparse
import ast
import json
import os
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

import yaml

from packages.database.src.tsugite_db.source_docs import SourceDocs
from tools.ci import ci_scope
from tools.ci.check_coverage import branch_rules, coverage_limits
from tools.testing.emulator_e2e import AWS_SUITE

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = Path(".github/workflows/check.yml")
DOCUMENT = Path("docs/generated/dev-rules/definition-of-done.md")


def table(headers, rows):
    def row(cells):
        return "| " + " | ".join(str(c).replace("|", r"\|").replace("\n", " ") for c in cells) + " |"

    return [row(headers), row(["---"] * len(headers)), *(row(cells) for cells in rows)]


def mapping(node):
    return {key.value: value for key, value in node.value}


def workflow_checks(source, link):
    """YAMLノードの開始位置に隣接する説明と、同じステップの実行条件を結び付ける。"""
    document = mapping(yaml.compose(source, Loader=yaml.BaseLoader))
    lines = source.splitlines()
    for job in mapping(document["jobs"]).values():
        for step in mapping(job)["steps"].value:
            fields = mapping(step)
            index = step.start_mark.line
            prefix = lines[index - 1].strip()
            if "run" not in fields or prefix == "# 実行準備":
                continue
            if not prefix.startswith("#:") or not prefix[2:].strip():
                raise ValueError(f"{WORKFLOW}:{index + 1}: 検査の説明を #: コメントで指定してください")
            title = fields.get("name", fields.get("run"))
            condition = fields["if"].value if "if" in fields else ""
            yield (
                link(title.value, WORKFLOW, index + 1),
                prefix.removeprefix("#:").strip(),
                f"`{condition}`" if condition else "すべてのPR",
            )


def suite_labels():
    labels = {}
    for path in ("tools/ci/ci_scope.py", "tools/testing/emulator_e2e.py"):
        source = SourceDocs((ROOT / path).read_text(encoding="utf-8"), path)
        for node in source.tree.body:
            if isinstance(node, ast.Assign) and (label := source.label(node)):
                labels[ast.literal_eval(node.value)] = label
    return labels


def test_rows(directory, link):
    files = sorted(set(directory.rglob("test_*.py")) | set(directory.rglob("*_test.py")))
    for path in files:
        tree = ast.parse(path.read_bytes(), filename=str(path))
        groups = [("", tree.body)]
        groups.extend(
            (node.name + ".", node.body)
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test")
        )
        for owner, nodes in groups:
            for node in nodes:
                if not isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) or not node.name.startswith("test_"):
                    continue
                description = ast.get_docstring(node)
                if not description:
                    raise ValueError(f"{path}:{node.lineno}: テストの日本語説明が必要です")
                details = [
                    mark.args[0].value
                    for decorator in node.decorator_list
                    for mark in ast.walk(decorator)
                    if isinstance(mark, ast.Call)
                    and isinstance(mark.func, ast.Attribute)
                    and mark.func.attr == "case_detail"
                    and mark.args
                    and isinstance(mark.args[0], ast.Constant)
                    and isinstance(mark.args[0].value, str)
                ]
                yield (
                    description,
                    "<br>".join(details) or "—",
                    link(owner + node.name, path.relative_to(ROOT), node.lineno),
                )


def change_examples(suites, labels):
    """各配布単位の実ファイルを一つ変更した場合の最小の計画をCIと同じ関数で求める。"""
    source = SourceDocs((ROOT / "tools/ci/ci_scope.py").read_text(encoding="utf-8"))
    selector = next(node for node in source.tree.body if getattr(node, "name", "") == "select")
    checks = source.literal_labels(selector)
    with TemporaryDirectory() as empty_cache:
        for suite in suites:
            area = Path(suite).parent
            if area.parent != Path("packages"):
                continue
            example = next(
                p for p in sorted((ROOT / area / "src").rglob("*.py")) if p.name != "__init__.py"
            ).relative_to(ROOT)
            plan = ci_scope.select([example.as_posix()], suites, Path(empty_cache))
            selected = [labels[name] for name in plan["suites"]]
            extra = [title for flag, title in checks.items() if plan[flag]]
            yield labels[suite], f"`{example.as_posix()}`", "、".join(selected), "、".join(extra) or "—"


def render(rules, branch, source_prefix):
    def link(label, path, line=None):
        return f"[{label}]({source_prefix}{quote(path.as_posix())}" + (f"#L{line})" if line else ")")

    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]
    frontend_mypy = tomllib.loads(
        (ROOT / "packages/frontend/pyproject.toml").read_text(encoding="utf-8")
    )["tool"]["mypy"]
    suites = config["pytest"]["ini_options"]["testpaths"]
    labels = suite_labels()
    minimum, drop = coverage_limits(rules)
    coverage = config["coverage"]["run"]

    def code(values):
        return "、".join(f"`{value}`" for value in values)

    lines = [
        "# 開発完了の定義",
        "",
        f"`{branch}` 向けのPRは、差分に応じて選ばれた検査に合格することが完了条件です。"
        "各テストのリンクから、条件と期待結果を実装で確認できます。",
        "",
        "## 全体の行カバレッジ",
        "",
        "単体・結合テストとブラウザーE2Eの計測を合算します。分野別の数値は内訳です。"
        "合否には対象ブランチの有効なGitHubルールを使います。",
        "",
        *table(
            ["判定項目", "基準・対象"],
            [
                ("全体の最低行カバレッジ", f"{float(minimum):g}%以上" if minimum else "下限指定なし"),
                ("比較元からの低下幅", f"{float(drop):g}ポイント以内" if drop else "低下幅の制限なし"),
                ("計測対象", code(coverage["source"])),
                ("計測から除くパターン", code(coverage.get("omit", []))),
            ],
        ),
        "",
        "## 分野別の変更と必要な検査",
        "",
        "実在するファイルを1つ変更した場合の例です。複数のファイルを変更すると対象が広がります。"
        "過去の計測で変更行を通ったスイートも再実行の対象になります。",
        "",
        *table(
            ["分野", "変更ファイルの例", "合格が必要なテスト", "追加の検査・生成"],
            change_examples(suites, labels),
        ),
        "",
        "## CIの検査項目と実行条件",
        "",
        "条件欄の `steps.scope.outputs` は、PRの差分からCIが決めた実行計画です。"
        "各行のリンクは判定を実行するステップを指します。",
        "",
        *table(
            ["検査", "確認内容", "実行条件"],
            workflow_checks((ROOT / WORKFLOW).read_text(encoding="utf-8"), link),
        ),
        "",
        "### 静的解析の設定",
        "",
        *table(
            ["ツール", "ルール・対象"],
            [
                ("Ruff", code(config["ruff"]["lint"]["select"])),
                ("Pyright", code(config["pyright"]["include"])),
                ("Pyright（strict）", code(config["pyright"].get("strict", []))),
                (f"mypy（strict={config['mypy']['strict']}）", code(config["mypy"]["files"])),
                (
                    f"フロントエンドのmypy（strict={frontend_mypy['strict']}）",
                    code(frontend_mypy["files"]),
                ),
            ],
        ),
        "",
        "## テストが確認する条件と期待結果",
        "",
        "分野ごとにテスト関数を1行ずつ掲載します。条件別の確認内容はテストに付けた日本語の説明から取得します。",
    ]
    for suite in [*suites, AWS_SUITE]:
        rows = list(test_rows(ROOT / suite, link))
        if not rows:
            raise ValueError(f"{suite}: 対象のテストがありません")
        lines += [
            "",
            f"### {labels[suite]}（{len(rows)}項目）",
            "",
            *table(["確認内容", "条件別の確認内容", "テスト定義"], rows),
        ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default=os.environ.get("BASE_BRANCH", "main"))
    parser.add_argument("--rules-file", type=Path, help="対象ブランチの有効なルール配列を保存したJSON")
    parser.add_argument("--artifact", action="store_true", help="CIの成果物として保存")
    args = parser.parse_args()
    repo = os.environ.get("GITHUB_REPOSITORY", "{owner}/{repo}")
    rules = (
        json.loads(args.rules_file.read_text(encoding="utf-8"))
        if args.rules_file
        else branch_rules(repo, args.branch)
    )
    destination = DOCUMENT
    prefix = "../" * len(destination.parent.parts)
    if args.artifact:
        destination = Path("artifacts/definition-of-done.md")
        sha = os.environ.get("PR_HEAD_SHA") or os.environ["GITHUB_SHA"]
        prefix = f"https://github.com/{repo}/blob/{sha}/"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render(rules, args.branch, prefix), encoding="utf-8", newline="\n")
    print(destination)


if __name__ == "__main__":
    main()
