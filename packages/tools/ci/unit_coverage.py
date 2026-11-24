# pytestが保存した単体テストの計測結果からパッケージごとの行・分岐カバレッジを判定する。
import json
import sys
import tempfile
import tomllib
from pathlib import Path

from coverage import Coverage

from .ci_coverage_parts import PARTS, part_name


def check_totals(name, totals, limits):
    results = []
    passed = True
    for label, covered_key, total_key in (
        ("line", "covered_lines", "num_statements"),
        ("branch", "covered_branches", "num_branches"),
    ):
        covered, total = totals[covered_key], totals[total_key]
        # 分岐のないコードは全分岐を満たす。実行文がない場合は計測不備として扱う。
        meets = 100 * covered >= limits[label] * total and (total > 0 or label == "branch")
        passed &= meets
        value = f"{100 * covered / total:.2f}%" if total else "対象なし"
        results.append(f"{label} {covered}/{total} ({value}, 下限 {limits[label]}%)")
    print(f"{name}: {', '.join(results)}")
    return passed


def main():
    config = tomllib.loads(Path("pyproject.toml").read_text())["tool"]
    failures = []
    for project in sorted(Path("packages").glob("*/pyproject.toml")):
        package = project.parent
        part = PARTS / part_name((package / "tests").as_posix())
        if not part.is_file() or not part.stat().st_size:
            failures.append(f"{package.name}（単体テストの計測結果がありません）")
            continue
        measured = Coverage(data_file=str(part))
        measured.load()
        if not measured.get_data().has_arcs():
            failures.append(f"{package.name}（分岐が計測されていません）")
            continue
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "coverage.json"
            measured.json_report(outfile=str(report), include=[f"{package.as_posix()}/*"])
            totals = json.loads(report.read_text())["totals"]
        if not check_totals(package.name, totals, config["tsugite"]["unit-coverage"]):
            failures.append(package.name)
    if failures:
        sys.exit("単体テストのカバレッジ基準を満たさないパッケージ　" + "、".join(failures))


if __name__ == "__main__":
    main()
