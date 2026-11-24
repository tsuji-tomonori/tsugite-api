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
