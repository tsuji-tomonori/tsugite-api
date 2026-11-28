"""旧方式で測った成果物は比較元に階層付き画面がなく計測器の他の部分が一致するときだけ使う。"""

import subprocess

from packages.tools.ci import check_coverage as coverage


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

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    source = repo / "packages/frontend/src/web_app"
    source.mkdir(parents=True)
    (source / "app.py").touch()
    (source / "client.py").touch()

    def commit():
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=test",
                "-c",
                "user.email=test@example.org",
                "commit",
                "-qm",
                "tree",
            ],
            cwd=repo,
            check=True,
        )
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()

    flat = commit()
    (source / "pages").mkdir()
    (source / "pages/home.py").touch()
    nested = commit()
    # 設定と計測器は同じまま、比較元コミットのファイル構成だけを変える。
    (repo / "pyproject.toml").write_bytes((coverage.ROOT / "pyproject.toml").read_bytes())
    tracer = coverage.ROOT / coverage.BROWSER_TRACE
    monkeypatch.setattr(coverage, "BROWSER_TRACE", tracer)
    monkeypatch.setattr(coverage, "ROOT", repo)
    assert coverage.compatible_baseline(tmp_path, flat)
    assert not coverage.compatible_baseline(tmp_path, nested)
    marker.write_text(coverage.coverage_policy(legacy + "# different tracer"))
    assert not coverage.compatible_baseline(tmp_path, flat)


def test_baseline_resolves_its_own_frontend_builder(tmp_path):
    """開発ツール移動前の2種類の配置と移動後の配置で、比較元のビルダーを選ぶ。"""
    for name in (
        "tools/build_frontend.py",
        "packages/tools/packaging/build_frontend.py",
        "packages/tools/packaging/build_frontend.py",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        assert coverage.frontend_builder(tmp_path) == name


def test_baseline_matches_previous_japanese_header_only(tmp_path, monkeypatch):
    """計測器の冒頭だけが旧コメント形式なら保存済みの比較値を使い、処理が変われば再計測する。"""
    fixture = tmp_path / "collector.py"
    tracer = tmp_path / "tracer.py"
    monkeypatch.setattr(coverage, "BROWSER_FIXTURE", fixture)
    monkeypatch.setattr(coverage, "BROWSER_TRACE", tracer)
    fixture.write_text('# 画面を計測する。\n"""画面を計測する。"""\n\ncollect()\n', encoding="utf-8")
    tracer.write_text('# 通過行を記録する。\n"""通過行を記録する。"""\n\ntrace()\n', encoding="utf-8")
    marker = tmp_path / coverage.POLICY_FILE
    marker.parent.mkdir()
    marker.write_text(coverage.coverage_policy())
    fixture.write_text('"""画面を計測する。"""\n\ncollect()\n', encoding="utf-8")
    tracer.write_text('"""通過行を記録する。"""\n\ntrace()\n', encoding="utf-8")
    assert coverage.compatible_baseline(tmp_path, "base")
    tracer.write_text('"""通過行を記録する。"""\n\nother_trace()\n', encoding="utf-8")
    assert not coverage.compatible_baseline(tmp_path, "base")
