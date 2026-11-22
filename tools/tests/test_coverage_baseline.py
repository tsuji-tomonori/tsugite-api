from unittest.mock import Mock

from tools import check_coverage as coverage


def test_flat_baseline_requires_equivalent_file_selection(tmp_path, monkeypatch):
    """旧方式で測った成果物は比較元に階層付き画面がなく計測器の他の部分が一致するときだけ使う。"""
    old_selection = 'path.name: path.as_posix() for path in FRONTEND.glob("*.py")'
    current_selection = (
        'path.relative_to(FRONTEND).as_posix(): path.as_posix() for path in FRONTEND.rglob("*.py")'
    )
    fixture = tmp_path / "collector.py"
    fixture.write_text("paths = {" + current_selection + "}")
    monkeypatch.setattr(coverage, "BROWSER_FIXTURE", fixture)
    legacy = "paths = {" + old_selection + "}"
    marker = tmp_path / coverage.POLICY_FILE
    marker.parent.mkdir(parents=True)
    marker.write_text(coverage.coverage_policy(legacy))
    root = "packages/frontend/src/web_app/"
    paths = Mock(return_value=(root + "app.py\\0").encode())
    monkeypatch.setattr(coverage.subprocess, "check_output", paths)
    assert coverage.compatible_baseline(tmp_path, "base-commit")
    assert "base-commit" in paths.call_args.args[0]
    paths.return_value += (root + "portal_pages/home.py\\0").encode()
    assert not coverage.compatible_baseline(tmp_path, "base-commit")
    paths.return_value = (root + "app.py\\0").encode()
    marker.write_text(coverage.coverage_policy(legacy + "\\n# different tracer"))
    assert not coverage.compatible_baseline(tmp_path, "base-commit")
