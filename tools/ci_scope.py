"""Select PR checks and combine coverage from changed suites with the verified merge base."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from xml.etree import ElementTree

from tools.check_coverage import (
    POLICY_FILE,
    compatible_coverage,
    coverage_policy,
    download_merged_coverage,
)

ARTIFACTS = Path("artifacts")
PARTS = ARTIFACTS / "coverage-parts"
BROWSER = "tests/e2e/browser"
TOOLS = "tools/tests"
ARCHITECTURE = "tests/architecture"
BACKEND = "packages/backend/tests"
DATABASE = "packages/database/tests"
FRONTEND = "packages/frontend/tests"
INFRA = "packages/infra/tests"
FULL = {"full"}


def affected(path, suites):
    for suite in suites:
        if path.startswith(suite + "/"):
            return {suite}
    if path.startswith("docs/generated/"):
        return {"design", TOOLS}
    if path.endswith(".md") and ("/" not in path or path.startswith(("docs/", "deploy/", ".agents/"))):
        return set()
    if path.startswith(("packages/backend/src/", "packages/database/")):
        return {BACKEND, DATABASE, BROWSER, TOOLS, "types", "design", "aws"}
    if path.endswith(("/web_app/guide_content.py", "/web_app/guide_search.py")):
        return {FRONTEND, BROWSER, BACKEND}
    if path == "tools/build_frontend.py":
        return {FRONTEND, BROWSER, TOOLS, "aws_portal"}
    if path == "packages/frontend/public/index.html" or path.endswith(
        ("/web_app/client.py", "/web_app/app.py", "/web_app/product_views.py", "/web_app/api_docs.py")
    ):
        return {FRONTEND, BROWSER, "aws_portal"}
    if path.startswith(("packages/frontend/src/", "packages/frontend/public/")):
        return {FRONTEND, BROWSER}
    if path.startswith("agent/"):
        return {BACKEND, BROWSER, INFRA, "audit", "aws"}
    if path.startswith("packages/infra/"):
        return {INFRA, "aws", "audit"}
    if path.startswith("tools/design/"):
        return {TOOLS, "design"}
    if path in {"tools/emulator_e2e.py", "tools/build_backend.py"} or path.startswith("tests/e2e/aws/"):
        return {"aws", "audit"} if path == "tools/build_backend.py" else {"aws"}
    if path == "tools/audit_infra.py":
        return {"audit"}
    if path == "tools/test_report.py":
        return {BROWSER, "aws"}
    if path.startswith("examples/") or path == "tools/seed_marketplace.py":
        return {BACKEND, BROWSER, INFRA, "aws"}
    if path.startswith(".githooks/") or path in {".gitmessage.txt", "tools/test_git_hooks.sh"}:
        return {"hooks"}
    return FULL


def changed_paths(base):
    output = subprocess.check_output(
        ["git", "diff", "--no-renames", "--name-only", "-z", base, "HEAD", "--"]
    )
    return [os.fsdecode(name) for name in output.split(b"\0") if name]


def part_name(suite):
    return suite.replace("/", "-") + ".sqlite"


def select(paths, suites, cached):
    flags = set().union(*(affected(path, suites) for path in paths))
    with Path(__file__).resolve().parents[1].joinpath("pyproject.toml").open("rb") as file:
        roots = tomllib.load(file)["tool"]["coverage"]["run"]["source"]
    measured_changes = {
        path
        for path in paths
        if path.endswith(".py")
        and "/tests/" not in path
        and any(path.startswith(root + "/") for root in roots)
    }
    full = "full" in flags or any(path.endswith("/pyproject.toml") for path in paths)
    if full:
        flags.update({"types", "design", "aws", "audit", "hooks"})
    selected = set(suites) if full else flags.intersection(suites)
    if ARCHITECTURE in suites and paths:
        selected.add(ARCHITECTURE)
    # The legacy artifact has a complete XML report but no per-suite data.
    reuse_xml = not selected and not full and (cached / "coverage.xml").is_file()
    if not reuse_xml:
        for suite in suites:
            part = cached / "coverage-parts" / part_name(suite)
            index = part.with_suffix(".json")
            if not part.is_file() or (
                measured_changes
                and part.stat().st_size
                and (not index.is_file() or measured_changes.intersection(json.loads(index.read_text())))
            ):
                selected.add(suite)
    aws = "aws" in flags or "aws_portal" in flags
    synth = aws or "audit" in flags
    return {
        "full": full,
        "suites": [suite for suite in suites if suite in selected],
        "lint": full or any(path.endswith((".py", ".pyi")) for path in paths),
        "types": "types" in flags,
        "design": "design" in flags,
        "audit": "audit" in flags,
        "hooks": "hooks" in flags and Path("tools/test_git_hooks.sh").exists(),
        "synth": synth,
        "frontend_build": bool(selected & {BROWSER, BACKEND, TOOLS}) and not synth,
        "chromium": BROWSER in selected or aws,
        "aws": aws,
        "aws_portal_only": "aws_portal" in flags and "aws" not in flags,
        "report": BROWSER in selected and aws,
        "reuse_xml": reuse_xml,
    }


def configured_suites():
    with Path("pyproject.toml").open("rb") as file:
        return tomllib.load(file)["tool"]["pytest"]["ini_options"]["testpaths"]


def plan(base):
    merge_base = subprocess.check_output(["git", "merge-base", base, "HEAD"], text=True).strip()
    paths = changed_paths(merge_base)
    suites = configured_suites()
    cached = Path(os.environ["RUNNER_TEMP"]) / "tsugite-base-coverage"
    cached.mkdir(exist_ok=True)
    if not any("full" in affected(path, suites) for path in paths):
        download_merged_coverage(
            os.environ["GITHUB_REPOSITORY"], os.environ["BASE_BRANCH"], merge_base, cached
        )
    if not compatible_coverage(cached):
        cached = cached / "no-compatible-baseline"
    result = select(paths, suites, cached)
    PARTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / POLICY_FILE).write_text(coverage_policy() + "\n")
    for suite in suites:
        source = cached / "coverage-parts" / part_name(suite)
        if suite not in result["suites"] and source.is_file():
            shutil.copyfile(source, PARTS / source.name)
            index = source.with_suffix(".json")
            if index.is_file():
                shutil.copyfile(index, PARTS / index.name)
    if result["reuse_xml"]:
        shutil.copyfile(cached / "coverage.xml", ARTIFACTS / "coverage.xml")
    result["setup"] = merge_base != base or any(
        value for key, value in result.items() if key != "reuse_xml"
    )
    (ARTIFACTS / "ci-plan.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        for key, value in result.items():
            print(f"{key}={json.dumps(value)}", file=output)


def write_coverage_report(destination):
    from coverage import Coverage

    # 全スイートの計測済みデータを、同名の app.py も識別できるリポジトリ相対パスで出力する。
    coverage = Coverage(source=[str(Path.cwd())])
    coverage.load()
    coverage.xml_report(outfile=str(destination))
    totals = {}
    for entry in ElementTree.parse(destination).iter("class"):
        path = Path(entry.attrib["filename"])
        if path.parts[0] == "packages":
            area = path.parts[1]
        else:
            area = "models" if path.parts[:2] == ("agent", "models") else path.parts[0]
        counts = totals.setdefault(area, [0, 0])
        lines = entry.findall("./lines/line")
        counts[0] += sum(int(line.attrib["hits"]) > 0 for line in lines)
        counts[1] += len(lines)
    for area, (covered, total) in sorted(totals.items()):
        if total:
            print(f"{area}: {covered}/{total} lines ({100 * covered / total:.2f}%)")


def run_suites():
    from coverage import CoverageData

    plan_data = json.loads((ARTIFACTS / "ci-plan.json").read_text())
    reports = ElementTree.Element("testsuites")
    for suite in plan_data["suites"]:
        part = PARTS / part_name(suite)
        prefix = ARTIFACTS / part.stem
        junit = prefix.with_suffix(".xml")
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            suite,
            "--cov",
            "--cov-config=pyproject.toml",
            f"--junitxml={junit}",
            f"--given-md={prefix}.md",
            f"--given-html={prefix}.html",
        ]
        result = subprocess.run(command, env={**os.environ, "COVERAGE_FILE": str(part.resolve())})
        if junit.exists():
            reports.extend(ElementTree.parse(junit).getroot().iter("testsuite"))
            ElementTree.ElementTree(reports).write(ARTIFACTS / "junit.xml", encoding="utf-8")
        result.check_returncode()
        data = CoverageData(basename=str(part))
        data.read()
        executed = sorted(Path(name).as_posix() for name in data.measured_files() if data.lines(name))
        part.with_suffix(".json").write_text(json.dumps(executed) + "\n")
        if not executed:
            part.write_bytes(b"")
    parts = [PARTS / part_name(suite) for suite in configured_suites()]
    measured = [str(part) for part in parts if part.stat().st_size]
    subprocess.run([sys.executable, "-m", "coverage", "combine", "--keep", *measured], check=True)
    write_coverage_report(ARTIFACTS / "coverage.xml")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("--base")
    command.add_argument("--run-suites", action="store_true")
    args = parser.parse_args()
    if args.base:
        plan(args.base)
    else:
        run_suites()
