"""Enforce active GitHub line coverage rules on a pull request."""

import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote
from xml.etree import ElementTree

BASELINE_ARTIFACT = "line-coverage"
# Verify run 44918756792 measured 1,932 of 2,234 lines on this bootstrap commit.
BOOTSTRAP_SHA = "8086921fee910e881e0a328e1c9dbe6c493b0c3e"
BOOTSTRAP_COVERAGE = Fraction(1932 * 100, 2234)


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


def baseline_coverage(repository, branch, sha):
    if sha == BOOTSTRAP_SHA:
        return BOOTSTRAP_COVERAGE

    result = github_json(
        f"repos/{repository}/actions/workflows/check.yml/runs",
        "-f",
        f"branch={branch}",
        "-f",
        f"head_sha={sha}",
        "-f",
        "status=success",
        "-f",
        "per_page=1",
    )
    if not result["workflow_runs"]:
        raise ValueError(f"Waiting for a successful coverage baseline for {branch} at {sha}")

    run_id = result["workflow_runs"][0]["id"]
    with TemporaryDirectory() as folder:
        subprocess.run(
            [
                "gh",
                "run",
                "download",
                str(run_id),
                "--name",
                BASELINE_ARTIFACT,
                "--dir",
                folder,
                "--repo",
                repository,
            ],
            check=True,
        )
        return line_coverage(Path(folder) / "coverage.xml")


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
