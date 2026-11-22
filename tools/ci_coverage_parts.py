"""選択したpytestスイートの実行結果と、リポジトリ相対パスのカバレッジを保存する。"""

import json
import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

ARTIFACTS = Path("artifacts")
PARTS = ARTIFACTS / "coverage-parts"


def part_name(suite):
    return suite.replace("/", "-") + ".sqlite"


def run_parts(suites):
    from coverage import CoverageData

    PARTS.mkdir(parents=True, exist_ok=True)
    reports = ElementTree.Element("testsuites")
    for suite in suites:
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


if __name__ == "__main__":
    run_parts(sys.argv[1:])
