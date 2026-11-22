"""Enforce active GitHub line coverage rules on a pull request."""

import hashlib
import json
import os
import subprocess
import sys
import tomllib
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote
from xml.etree import ElementTree

BASELINE_ARTIFACT = "line-coverage"
ROOT = Path(__file__).resolve().parents[2]
POLICY_FILE = Path("coverage-parts/policy.sha256")
BROWSER_FIXTURE = Path("tests/e2e/browser/conftest.py")
BROWSER_TRACE = Path("tests/support/pyodide_trace.py")


def coverage_policy():
    with (ROOT / "pyproject.toml").open("rb") as file:
        config = tomllib.load(file)["tool"]["coverage"]
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode())
    for path in (BROWSER_FIXTURE, BROWSER_TRACE):
        digest.update((ROOT / path).read_text(encoding="utf-8").encode())
    return digest.hexdigest()


def compatible_coverage(folder):
    marker = Path(folder) / POLICY_FILE
    return marker.is_file() and marker.read_text().strip() == coverage_policy()


def github_json(endpoint, *query_args):
    return json.loads(
        subprocess.check_output(
            ["gh", "api", "--method", "GET", endpoint, *query_args],
            encoding="utf-8",
        ),
        parse_float=Fraction,
    )


def line_coverage(path):
    report = ElementTree.parse(path).getroot()
    covered = int(report.attrib["lines-covered"])
    total = int(report.attrib["lines-valid"])
    if not 0 <= covered <= total or total == 0:
        raise ValueError(f"Invalid line counts in {path}: {covered}/{total}")
    return Fraction(covered * 100, total)


def download_merged_coverage(repository, branch, sha, folder):
    pulls = github_json(f"repos/{repository}/commits/{sha}/pulls")
    base_tree = github_json(f"repos/{repository}/git/commits/{sha}")["tree"]["sha"]
    for pull in pulls:
        if not (
            pull["merged_at"]
            and pull["merge_commit_sha"] == sha
            and pull["base"]["ref"] == branch
            and pull["base"]["repo"]["full_name"] == repository
        ):
            continue

        head = pull["head"]["sha"]
        if github_json(f"repos/{repository}/git/commits/{head}")["tree"]["sha"] != base_tree:
            continue

        result = github_json(
            f"repos/{repository}/actions/workflows/check.yml/runs",
            "-f",
            f"head_sha={head}",
            "-f",
            "event=pull_request",
            "-f",
            "status=success",
        )
        for run in result["workflow_runs"]:
            run_id = run["id"]
            artifacts = github_json(
                f"repos/{repository}/actions/runs/{run_id}/artifacts",
                "-f",
                f"name={BASELINE_ARTIFACT}",
            )["artifacts"]
            if not any(not artifact["expired"] for artifact in artifacts):
                continue

            pull_number = pull["number"]
            print(f"Using coverage from merged pull request #{pull_number}, run {run_id}")
            subprocess.run(
                [
                    "gh",
                    "run",
                    "download",
                    str(run_id),
                    "--name",
                    BASELINE_ARTIFACT,
                    "--dir",
                    str(folder),
                    "--repo",
                    repository,
                ],
                check=True,
            )
            return True
    return False


def merged_pr_coverage(repository, branch, sha):
    with TemporaryDirectory() as folder:
        if download_merged_coverage(repository, branch, sha, folder) and compatible_coverage(folder):
            return line_coverage(Path(folder) / "coverage.xml")
    return None


def only_browser_timeouts(junit):
    report = ElementTree.parse(junit)
    failures = list(report.iter("failure"))
    return (
        bool(failures)
        and report.find(".//error") is None
        and all("playwright._impl._errors.TimeoutError" in (entry.text or "") for entry in failures)
    )


def measure_base_coverage(sha):
    print(f"No coverage artifact matches {sha}; measuring the base in this PR run.", flush=True)
    env = os.environ.copy()
    for name in ("GH_TOKEN", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
        env.pop(name, None)

    with TemporaryDirectory() as folder:
        path = Path(folder) / "base"
        subprocess.run(["git", "worktree", "add", "--detach", str(path), sha], check=True, env=env)
        try:
            subprocess.run(["task", "setup", "browser:install"], cwd=path, check=True, env=env)
            # Older base commits keep the builder directly under tools/.
            builder = "tools/packaging/build_frontend.py"
            if not (path / builder).is_file():
                builder = "tools/build_frontend.py"
            subprocess.run(
                ["uv", "run", "--locked", "--all-packages", "python", builder],
                cwd=path,
                check=True,
                env=env,
            )
            (path / "artifacts").mkdir(exist_ok=True)
            # 同じ計測方法で比較するため、ベースの実装とテストに現在のブラウザー計測だけを加える。
            fixture = path / BROWSER_FIXTURE
            with fixture.open("a", encoding="utf-8") as stream:
                stream.write("\n" + (ROOT / BROWSER_FIXTURE).read_text(encoding="utf-8"))
            (path / BROWSER_TRACE).write_bytes((ROOT / BROWSER_TRACE).read_bytes())
            report = Path("artifacts/coverage.xml")
            command = [
                "uv",
                "run",
                "--locked",
                "--all-packages",
                "pytest",
                "-q",
                "--cov",
                f"--cov-config={ROOT / 'pyproject.toml'}",
                f"--cov-report=xml:{report}",
            ]
            junit = path / "artifacts/baseline-tests.xml"
            command.append(f"--junitxml={junit}")
            result = subprocess.run(command, cwd=path, env=env)
            if result.returncode == 1 and junit.is_file() and only_browser_timeouts(junit):
                # pytest-cov は再実行の開始時に前回のデータを消去する。
                print("Retrying the base measurement after a Playwright timeout", flush=True)
                result = subprocess.run(command, cwd=path, env=env)
            result.check_returncode()
            return line_coverage(path / report)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(path)], check=True, env=env)


def baseline_coverage(repository, branch, sha):
    coverage = merged_pr_coverage(repository, branch, sha)
    return measure_base_coverage(sha) if coverage is None else coverage


def main(report_path):
    repository = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ["BASE_BRANCH"]
    branch_ref = quote(branch, safe="")
    rules = github_json(f"repos/{repository}/rules/branches/{branch_ref}")
    thresholds = [rule["parameters"] for rule in rules if rule["type"] == "code_coverage"]
    minimum = max((rule.get("minimum_coverage", 0) for rule in thresholds), default=0)
    max_drop = min(
        (drop for rule in thresholds if (drop := rule.get("max_coverage_drop", 0)) > 0),
        default=0,
    )
    current = line_coverage(report_path)
    print(f"PR line coverage: {float(current):.2f}%")
    print(
        f"Active rules: minimum {float(minimum):g}%, "
        f"maximum drop {float(max_drop):g} points (0 = disabled)"
    )
    if current < minimum:
        raise ValueError("PR line coverage is below the configured minimum")

    if max_drop:
        baseline = baseline_coverage(repository, branch, os.environ["BASE_SHA"])
        drop = baseline - current
        print(f"{branch} line coverage: {float(baseline):.2f}%; drop: {float(drop):+.2f} points")
        if drop > max_drop:
            raise ValueError("PR line coverage drop exceeds the configured maximum")


if __name__ == "__main__":
    try:
        main(Path(sys.argv[1]))
    except (
        OSError,
        ValueError,
        KeyError,
        ElementTree.ParseError,
        subprocess.CalledProcessError,
    ) as error:
        sys.exit(f"Line coverage check failed: {error}")
