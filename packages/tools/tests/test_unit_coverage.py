# 行と分岐のカバレッジ下限が独立して適用されることを検証する。
from packages.tools.ci.unit_coverage import check_totals


def test_coverage_compares_exact_line_and_branch_counts():
    """境界値を許容し、片方だけが基準未満なら表示上の丸めで合格にしない。"""
    totals = dict(covered_lines=90000, num_statements=100000, covered_branches=17, num_branches=20)
    limits = {"line": 90, "branch": 85}
    assert check_totals("example", totals, limits)
    assert not check_totals("example", totals | {"covered_lines": 89999}, limits)
    assert not check_totals("example", totals | {"covered_branches": 16}, limits)
    assert check_totals("example", totals | {"num_branches": 0, "covered_branches": 0}, limits)
    assert not check_totals("example", totals | {"num_statements": 0, "covered_lines": 0}, limits)


def test_gate_uses_only_the_packages_own_unit_run(tmp_path, monkeypatch):
    """他スイートの結果で単体の未計測を補わず、未実行・分岐なし計測・下限未達を区別する。"""
    import pytest
    from coverage import Coverage

    from packages.tools.ci import unit_coverage
    from packages.tools.ci.ci_coverage_parts import PARTS, part_name

    monkeypatch.chdir(tmp_path)
    package = tmp_path / "packages/sample"
    package.mkdir(parents=True)
    (package / "pyproject.toml").touch()
    (tmp_path / "pyproject.toml").write_text("[tool.tsugite.unit-coverage]\nline=90\nbranch=85\n")
    PARTS.mkdir(parents=True)
    sample = package / "sample.py"
    code = "def select(value):\n    if value:\n        return 1\n    return 2\n"
    sample.write_text(code)

    def measure(suite, branch, both):
        part = PARTS / part_name(suite)
        part.unlink(missing_ok=True)
        tracer = Coverage(data_file=part, branch=branch)
        scope = {}
        with tracer.collect():
            exec(compile(code, str(sample), "exec"), scope)
            assert scope["select"](True) == 1
            if both:
                assert scope["select"](False) == 2
        tracer.save()

    measure("tests/architecture", True, True)
    with pytest.raises(SystemExit, match="単体テストの計測結果がありません"):
        unit_coverage.main()
    suite = "packages/sample/tests"
    measure(suite, False, True)
    with pytest.raises(SystemExit, match="分岐が計測されていません"):
        unit_coverage.main()
    measure(suite, True, False)
    with pytest.raises(SystemExit, match="基準を満たさないパッケージ"):
        unit_coverage.main()
    measure(suite, True, True)
    assert unit_coverage.main() is None
