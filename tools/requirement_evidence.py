"""要件に記載したテストを実行結果と照合し、読める証跡と終了コードを返す。"""

import argparse
import ast
import json
import os
import shutil
import sys
import tomllib
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree

ITEMS = Path("docs/requirements/items")
AWS = "tests/e2e/aws"
BROWSER = "tests/e2e/browser"
PREFIX = "- 受入テスト "


@dataclass(frozen=True)
class Check:
    node: str
    suite: str
    shot: str


def catalogue(root: Path, suites: Collection[str]) -> tuple[dict[str, list[Check]], list[str]]:
    requirements = {}
    errors = []
    functions: dict[Path, set[str]] = {}
    for item in sorted((root / ITEMS).glob("*.md")):
        checks = []
        for line in item.read_text(encoding="utf-8").splitlines():
            if not line.startswith(PREFIX):
                continue
            parts = line.removeprefix(PREFIX).split(" / ")
            node = parts[0].strip("`")
            source, _, name = node.partition("::")
            suite = next((s for s in suites if source.startswith(s + "/")), "")
            shot = parts[1].strip("`") if len(parts) == 2 else ""
            file = root / source
            if (
                len(parts) > 2
                or not suite
                or ".." in Path(source).parts
                or not file.name.startswith("test_")
                or file.suffix != ".py"
                or not file.is_file()
                or not name.startswith("test_")
                or (suite == BROWSER and not shot)
                or (shot and (Path(shot).name != shot or not shot.endswith(".png")))
            ):
                errors.append(f"{item.stem}　受入テストの指定が不正です　{line}")
                continue
            if file not in functions:
                try:
                    tree = ast.parse(file.read_bytes(), filename=source)
                except (OSError, SyntaxError) as exc:
                    errors.append(f"{source}　テスト定義を読み込めません　{exc}")
                    functions[file] = set()
                else:
                    functions[file] = {
                        f.name
                        for f in tree.body
                        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                    }
            if name not in functions[file]:
                errors.append(f"{item.stem}　テスト関数がありません　{node}")
            checks.append(Check(node, suite, shot))
        if not checks:
            errors.append(f"{item.stem}　受入テストがありません")
        requirements[item.stem] = checks
    if not requirements:
        errors.append("要件ファイルがありません")
    return requirements, errors


def read_results(reports: Iterable[Path]) -> tuple[dict[str, list[ElementTree.Element]], list[str]]:
    cases = defaultdict(list)
    errors = []
    for report in reports:
        try:
            xml = ElementTree.parse(report)
        except (OSError, ElementTree.ParseError) as exc:
            errors.append(f"JUnitを読み込めません　{report.name}　{exc}")
            continue
        for case in xml.iter("testcase"):
            node = case.find("./properties/property[@name='nodeid']")
            if node is not None and node.get("value"):
                cases[node.attrib["value"].split("[", 1)[0]].append(case)
            if any(case.find(tag) is not None for tag in ("error", "failure")):
                errors.append(
                    f"{report.name}　{case.get('classname', '')}.{case.get('name', '')} が失敗"
                )
    return cases, errors


def collect_image(value: str, artifacts: Path, output: Path) -> str:
    name, _, caption = value.partition("|")
    source = (artifacts / name.replace("\\", "/")).resolve()
    base = (artifacts / "screenshots").resolve()
    if not source.is_relative_to(base) or source.suffix != ".png":
        raise ValueError("スクリーンショットのパスが不正です")
    with source.open("rb") as image:
        header = image.read(24)
        if (
            len(header) != 24
            or header[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            or min(int.from_bytes(header[i : i + 4], "big") for i in (16, 20)) == 0
        ):
            raise ValueError("PNG画像のヘッダーを読み込めません")
        image.seek(-12, 2)
        if image.read() != b"\x00\x00\x00\x00IEND\xaeB`\x82":
            raise ValueError("PNG画像の末尾が欠落しています")
    relative = Path("screenshots") / source.relative_to(base)
    dest = output / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    return f"[{caption or source.stem}]({quote(relative.as_posix())})"


def render(
    requirements: dict[str, list[Check]],
    cases: dict[str, list[ElementTree.Element]],
    selected: Collection[str],
    artifacts: Path,
    output: Path,
    errors: list[str],
    *,
    portal_only: bool = False,
) -> bool:
    output.mkdir(parents=True, exist_ok=True)
    pages = output / "items"
    pages.mkdir(exist_ok=True)
    lines = ["# 要件別のテスト結果", ""]
    commit = os.environ.get("EVIDENCE_COMMIT")
    if commit:
        lines.extend([f"対象コミット　`{commit}`", ""])
    suite = ElementTree.Element("testsuite", name="要件別の受入テスト")
    verdicts: Counter[str] = Counter()
    failed = bool(errors)
    for title, checks in requirements.items():
        evidence = ElementTree.Element("testsuite", name=title)
        rows = []
        statuses = []
        for check in checks:
            scheduled = check.suite in selected and not (
                portal_only and check.suite == AWS and not check.node.endswith("::test_cognito_browser")
            )
            if not scheduled:
                statuses.append("対象外")
                rows.append(f"- 差分CIの対象外　`{check.node}`")
                continue
            results = cases.get(check.node, [])
            if not results:
                statuses.append("未実行")
                rows.append(f"- 未実行　`{check.node}`")
            if results:
                counts = {
                    value.get("value")
                    for case in results
                    for value in case.findall("./properties/property[@name='variants']")
                }
                ids = [case.get("name") for case in results]
                if (counts and counts != {str(len(results))}) or len(ids) != len(set(ids)):
                    statuses.append("件数不一致")
                    rows.append(f"- 不一致　収集した条件とJUnitの件数が一致しません　`{check.node}`")
            for case in results:
                evidence.append(case)
                status = "成功"
                detail = ""
                for tag, label in (("error", "エラー"), ("failure", "失敗"), ("skipped", "スキップ")):
                    problem = case.find(tag)
                    if problem is not None:
                        status = label
                        detail = problem.get("message", "").replace("\n", " ")[:350]
                        break
                images = []
                for prop in case.findall("./properties/property[@name='screenshot']"):
                    value = prop.get("value", "")
                    name = Path(value.partition("|")[0].replace("\\", "/")).name
                    if name == check.shot or (status != "成功" and name.startswith("failure-")):
                        try:
                            images.append(collect_image(value, artifacts, output))
                        except (OSError, ValueError) as exc:
                            status, detail = "証跡不足", str(exc)
                if status == "成功" and check.shot and not images:
                    status, detail = "証跡不足", check.shot
                desc = case.find("./properties/property[@name='case_description']")
                description = desc.get("value", "") if desc is not None else ""
                identifier = check.node.partition("::")[0] + "::" + case.get("name", "")
                rows.append(f"- {status}　{description}（{case.get('time', '0')} 秒）　`{identifier}`")
                for prop in case.findall("./properties/property[@name='measurement']"):
                    rows.append("  - " + prop.get("value", ""))
                if detail:
                    rows.append(f"  - {detail}")
                rows.extend("  - " + image for image in images)
                statuses.append(status)
        if any(s in {"失敗", "エラー"} for s in statuses):
            verdict = "不合格"
            failed = True
        elif not statuses or any(s not in {"対象外", "成功"} for s in statuses):
            verdict = "検証未完了"
            failed = True
        elif "対象外" in statuses:
            verdict = "部分実行" if "成功" in statuses else "対象外"
        else:
            verdict = "合格"
        verdicts[verdict] += 1
        record = ElementTree.SubElement(suite, "testcase", classname="requirements", name=title)
        if verdict in {"不合格", "検証未完了"}:
            ElementTree.SubElement(record, "failure", message=verdict).text = "\n".join(rows)
        elif verdict != "合格":
            ElementTree.SubElement(record, "skipped", message=verdict)
        page = pages / (title + ".md")
        xml = page.with_suffix(".xml")
        ElementTree.ElementTree(evidence).write(xml, encoding="utf-8", xml_declaration=True)
        rows = [
            row.replace("  - [", "  - ![").replace("](screenshots/", "](../screenshots/") for row in rows
        ]
        page.write_text(
            "\n".join(
                [
                    f"# {title}",
                    "",
                    f"判定　{verdict}",
                    "",
                    *([f"対象コミット　`{commit}`", ""] if commit else []),
                    "## 実行したテストと証跡",
                    "",
                    *rows,
                    "",
                    f"[テスト実行記録（JUnit XML）]({quote(xml.name)})",
                    "",
                ]
            ),
            encoding="utf-8",
            newline="\n",
        )
        lines.append(f"- [{verdict}　{title}](items/{quote(page.name)})")
    if errors:
        record = ElementTree.SubElement(suite, "testcase", classname="ci", name="実行と定義の検査")
        ElementTree.SubElement(record, "error", message="要件検証を完了できません").text = "\n".join(
            errors
        )
        lines.extend(["## 実行または定義のエラー", "", *("- " + error for error in errors), ""])
    lines[2:2] = [
        f"全 {len(requirements)} 要件　"
        + " / ".join(
            f"{label} {verdicts[label]}件"
            for label in ("合格", "不合格", "検証未完了", "部分実行", "対象外")
        ),
        "",
    ]
    suite.set("tests", str(len(suite)))
    for attribute, tag in (("failures", "failure"), ("errors", "error"), ("skipped", "skipped")):
        suite.set(attribute, str(len(suite.findall("testcase/" + tag))))
    ElementTree.ElementTree(suite).write(
        output / "requirements.xml", encoding="utf-8", xml_declaration=True
    )
    (output / "report.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")
    return not failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--plan", type=Path, help="差分CIが今回実行するテスト層")
    parser.add_argument(
        "--artifacts", type=Path, default=Path("artifacts"), help="今回のJUnitと画像のディレクトリ"
    )
    args = parser.parse_args()
    root = Path.cwd()
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    suites = [*config["tool"]["pytest"]["ini_options"]["testpaths"], AWS]
    requirements, errors = catalogue(root, suites)
    if args.check:
        print("\n".join(errors) if errors else f"{len(requirements)}件の要件に受入テストがあります")
        return int(bool(errors))
    artifacts = args.artifacts
    selected = suites
    portal_only = False
    if args.plan and args.plan.is_file():
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        selected = [*plan["suites"], *([AWS] if plan["aws"] else [])]
        portal_only = plan["aws_portal_only"]
    elif args.plan:
        errors.append("今回のCI実行計画がありません")
    reports = []
    if any(s != AWS for s in selected):
        reports.append(artifacts / "junit.xml")
    if AWS in selected:
        reports.append(artifacts / "aws-emulator.xml")
    cases, report_errors = read_results(reports)
    return int(
        not render(
            requirements,
            cases,
            selected,
            artifacts,
            root / "evidence",
            errors + report_errors,
            portal_only=portal_only,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
