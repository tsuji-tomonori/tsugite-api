"""Select PR checks and combine coverage from changed suites with the verified merge base."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

from tools.check_coverage import (
    POLICY_FILE,
    compatible_coverage,
    coverage_policy,
    download_merged_coverage,
)
from tools.ci_coverage_parts import ARTIFACTS, PARTS, part_name, run_parts

BROWSER = "tests/e2e/browser"
TOOLS = "tools/tests"
ARCHITECTURE = "tests/architecture"
AGENT = "packages/agent/tests"
BACKEND = "packages/backend/tests"
DATABASE = "packages/database/tests"
FRONTEND = "packages/frontend/tests"
INFRA = "packages/infra/tests"
FULL = {"full"}


def affected(path, suites):
    if path in {"tests/e2e/browser/conftest.py", "tests/support/pyodide_trace.py"}:
        return FULL
    for suite in suites:
        if path.startswith(suite + "/"):
            return {suite, "types"} if suite == AGENT else {suite}
    if path.startswith("docs/requirements/items/"):
        return FULL
    if path.startswith("docs/generated/infra/") or path == "tools/design/infrastructure.py":
        return {TOOLS, "infra_design"}
    if path.startswith("docs/generated/"):
        return {"design", TOOLS}
    if path.lower().endswith(".md") and (
        "/" not in path
        or path.startswith(("docs/", "deploy/", ".agents/", ".github/"))
        or Path(path).name.lower() == "readme.md"
    ):
        return set()
    if path == "packages/backend/src/app/core/log_record.py":
        return {AGENT, BACKEND, FRONTEND, BROWSER, TOOLS, "types", "aws", "aws_portal"}
    if path.startswith("packages/backend/"):
        return {AGENT, BACKEND, BROWSER, TOOLS, "types", "design", "aws"}
    if path.startswith("packages/database/"):
        return {DATABASE, AGENT, BACKEND, BROWSER, TOOLS, "types", "design", "aws"}
    if path.endswith(("/web_app/guide_content.py", "/web_app/guide_search.py")):
        return {AGENT, FRONTEND, BROWSER, BACKEND}
    if path == "tools/build_frontend.py":
        return {FRONTEND, BROWSER, TOOLS, "aws_portal"}
    if (
        path.startswith("packages/frontend/src/web_app/portal_pages/") and path.endswith(".py")
    ) or path.endswith(
        (
            "/portal_shell.py",
            "/portal_session.py",
            "/portal_ui.py",
            "/portal_navigation.py",
            "/screen_registry.py",
            "/listing_data.py",
        )
    ):
        return {FRONTEND, BROWSER, "aws_portal"}
    if path == "packages/frontend/public/index.html" or path.endswith(
        ("/web_app/client.py", "/web_app/app.py", "/web_app/product_views.py", "/web_app/api_docs.py")
    ):
        return {FRONTEND, BROWSER, "aws_portal"}
    if path == "packages/frontend/pyproject.toml":
        return {FRONTEND, BROWSER, TOOLS, "aws_portal"}
    if path.startswith("packages/frontend/"):
        return {FRONTEND, BROWSER}
    if path.startswith("packages/agent/"):
        return {AGENT, BACKEND, BROWSER, INFRA, "types", "audit", "aws"}
    if path == "tools/build_chat.py":
        return {AGENT, BACKEND, BROWSER, INFRA, TOOLS, "types", "audit", "aws"}
    if path.startswith("packages/infra/"):
        return {INFRA, "aws", "audit"}
    if path.startswith("tools/design/"):
        return {TOOLS, "design"}
    if path == "tools/pyproject.toml":
        return {TOOLS}
    if path == "tests/e2e/pyproject.toml":
        return {BROWSER, "aws"}
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


def lock_projects(previous, current):
    """ロックの変更を消費するワークスペースを旧版と新版の両方から求める。"""
    if {k: v for k, v in previous.items() if k != "package"} != {
        k: v for k, v in current.items() if k != "package"
    }:
        return {"uv.lock"}
    versions = []
    owners = {}
    for lock in (previous, current):
        entries = {}
        graph = {}
        members = {}
        for package in lock["package"]:
            name = package["name"]
            entries.setdefault(name, []).append(package)
            edges = graph.setdefault(name, set())
            edges.update(dep["name"] for dep in package.get("dependencies", []))
            for key in ("optional-dependencies", "dev-dependencies"):
                for group in package.get(key, {}).values():
                    edges.update(dep["name"] for dep in group)
            source = package["source"]
            member = source.get("editable", source.get("virtual"))
            if member is not None:
                members[name] = (Path(member) / "pyproject.toml").as_posix()
        versions.append(entries)
        for member, path in members.items():
            pending = [member]
            seen = set()
            while pending:
                name = pending.pop()
                if name in seen or (name != member and name in members):
                    continue
                seen.add(name)
                owners.setdefault(name, set()).add(path)
                pending.extend(graph.get(name, ()))
    old, new = versions
    affected_projects = set()
    for name in old.keys() | new.keys():
        if old.get(name) != new.get(name):
            affected_projects.update(owners.get(name, {"uv.lock"}))
    return affected_projects or {"uv.lock"}


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
    full = "full" in flags
    if full:
        flags.update({"types", "design", "aws", "audit", "hooks"})
    selected = set(suites) if full else flags.intersection(suites)
    if ARCHITECTURE in suites and (full or selected or any(p.endswith((".py", ".pyi")) for p in paths)):
        selected.add(ARCHITECTURE)
    # The legacy artifact has a complete XML report but no per-suite data.
    reuse_xml = not selected and not full and (cached / "coverage.xml").is_file()
    if selected and not full:
        for suite in suites:
            part = cached / "coverage-parts" / part_name(suite)
            index = part.with_suffix(".json")
            if (
                measured_changes
                and part.is_file()
                and part.stat().st_size
                and (not index.is_file() or measured_changes.intersection(json.loads(index.read_text())))
            ):
                selected.add(suite)
    aws = "aws" in flags or "aws_portal" in flags
    synth = aws or "audit" in flags or "infra_design" in flags
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


def scope_inputs(base):
    merge_base = subprocess.check_output(["git", "merge-base", base, "HEAD"], text=True).strip()
    paths = changed_paths(merge_base)
    if "uv.lock" in paths and Path("uv.lock").is_file():
        old = subprocess.run(["git", "show", f"{merge_base}:uv.lock"], capture_output=True)
        if old.returncode == 0:
            with Path("uv.lock").open("rb") as stream:
                projects = lock_projects(tomllib.loads(old.stdout.decode()), tomllib.load(stream))
            paths = [path for path in paths if path != "uv.lock"] + sorted(projects)
    suites = configured_suites()
    cached = Path(os.environ["RUNNER_TEMP"]) / "tsugite-base-coverage"
    return merge_base, paths, suites, cached


def write_outputs(values):
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        for key, value in values.items():
            print(f"{key}={value if isinstance(value, str) else json.dumps(value)}", file=output)


def missing_parts(result, suites, cached):
    if not result["suites"]:
        return []
    return [
        suite
        for suite in suites
        if suite not in result["suites"] and not (cached / "coverage-parts" / part_name(suite)).is_file()
    ]


def inspect_base(base):
    merge_base, paths, suites, cached = scope_inputs(base)
    if not any("full" in affected(path, suites) for path in paths):
        cached.mkdir(exist_ok=True)
        download_merged_coverage(
            os.environ["GITHUB_REPOSITORY"], os.environ["BASE_BRANCH"], merge_base, cached
        )
    cached = coverage_cache(cached)
    result = select(paths, suites, cached)
    write_outputs({"missing": missing_parts(result, suites, cached)})


def coverage_cache(cached):
    return cached if compatible_coverage(cached) else cached / "no-compatible-baseline"


def measure_missing_base_parts(base, missing):
    # PRで実行するスイートと、全体カバレッジの合算にだけ必要な比較元の計測を分ける。
    merge_base, _, _, cached = scope_inputs(base)
    destination = coverage_cache(cached) / "coverage-parts"
    destination.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    for name in ("VIRTUAL_ENV", "GH_TOKEN", "UV_PROJECT_ENVIRONMENT"):
        env.pop(name, None)
    with TemporaryDirectory() as folder:
        checkout = Path(folder) / "base"
        subprocess.run(["git", "worktree", "add", "--detach", str(checkout), merge_base], check=True)
        try:
            uv = ["uv", "run", "--locked", "--all-packages"]
            if BROWSER in missing:
                subprocess.run(
                    [*uv, "playwright", "install", "--with-deps", "chromium", "--only-shell"],
                    cwd=checkout,
                    env=env,
                    check=True,
                )
            if set(missing) & {BROWSER, BACKEND, TOOLS}:
                subprocess.run(
                    [*uv, "python", "tools/build_frontend.py"], cwd=checkout, env=env, check=True
                )
            subprocess.run(
                [
                    *uv,
                    "python",
                    str(Path(__file__).with_name("ci_coverage_parts.py").resolve()),
                    *missing,
                ],
                cwd=checkout,
                env=env,
                check=True,
            )
            for suite in missing:
                part = checkout / PARTS / part_name(suite)
                for file in (part, part.with_suffix(".json")):
                    shutil.copyfile(file, destination / file.name)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(checkout)], check=True)


def plan(base):
    merge_base, paths, suites, cached = scope_inputs(base)
    cached = coverage_cache(cached)
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
    result["setup"] = any(value for key, value in result.items() if key != "reuse_xml")
    result["coverage"] = bool(result["suites"]) or result["reuse_xml"]
    result["documents"] = any(path.lower().endswith(".md") for path in paths)
    result["coverage_base"] = merge_base if result["reuse_xml"] else base
    (ARTIFACTS / "ci-plan.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    write_outputs(result)


def write_coverage_report(destination):
    from coverage import Coverage

    # 全スイートの計測済みデータを、同名の app.py も識別できるリポジトリ相対パスで出力する。
    coverage = Coverage(source=[str(Path.cwd())])
    coverage.load()
    coverage.xml_report(outfile=str(destination))
    totals = {}
    for entry in ElementTree.parse(destination).iter("class"):
        path = Path(entry.attrib["filename"])
        area = path.parts[1] if path.parts[0] == "packages" else path.parts[0]
        if path.is_relative_to("packages/agent/src/agent/models"):
            area = "models"
        counts = totals.setdefault(area, [0, 0])
        lines = entry.findall("./lines/line")
        counts[0] += sum(int(line.attrib["hits"]) > 0 for line in lines)
        counts[1] += len(lines)
    for area, (covered, total) in sorted(totals.items()):
        if total:
            print(f"{area}: {covered}/{total} lines ({100 * covered / total:.2f}%)")


def run_suites():
    plan_data = json.loads((ARTIFACTS / "ci-plan.json").read_text())
    run_parts(plan_data["suites"])
    parts = [PARTS / part_name(suite) for suite in configured_suites()]
    measured = [str(part) for part in parts if part.stat().st_size]
    subprocess.run([sys.executable, "-m", "coverage", "combine", "--keep", *measured], check=True)
    write_coverage_report(ARTIFACTS / "coverage.xml")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("--base")
    command.add_argument("--inspect-base")
    command.add_argument("--measure-base")
    command.add_argument("--run-suites", action="store_true")
    args = parser.parse_args()
    if args.base:
        plan(args.base)
    elif args.inspect_base:
        inspect_base(args.inspect_base)
    elif args.measure_base:
        measure_missing_base_parts(args.measure_base, json.loads(os.environ["MISSING_SUITES"]))
    else:
        run_suites()
