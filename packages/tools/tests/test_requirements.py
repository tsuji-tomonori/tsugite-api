"""本文の定義を一度だけ掲載し、両方の一覧から日本語名の要件を開ける。"""

from subprocess import check_output
from urllib.parse import unquote

import pytest

from packages.tools.design.requirements import ITEMS, check_feature, generate

FIRST = "**利用者**は、**商品**を探すとき、**検索**できる"
SECOND = "**利用者**は、**商品**を選ぶとき、**検索**できる"
DEFINITIONS = "**利用者**（使う人）が**商品**（利用するAPI）を**検索**（候補を探す操作）する。"


def write_item(folder, title=FIRST, background=DEFINITIONS):
    path = folder / (title.replace("**", "") + ".md")
    path.write_text(
        f"# {title}\n\n## 背景\n\n{background}\n\n## なぜ必要か\n\n用途で探すため。\n\n"
        "## 決めた方針\n\n公開範囲で検索する。\n\n## 却下した方針\n\n却下の記録なし。\n",
        encoding="utf-8",
    )
    return path


def test_indexes_follow_sources(tmp_path):
    """本文の定義を一度だけ掲載し、両方の一覧から日本語名の要件を開ける。"""
    source = tmp_path / "items"
    source.mkdir()
    first = write_item(source)
    second = write_item(source, SECOND, "既存の商品を使う。")
    output = tmp_path / "output"
    generate(source, output)
    index = unquote((output / "index.md").read_text(encoding="utf-8"))
    glossary = unquote((output / "glossary.md").read_text(encoding="utf-8"))
    assert all(f"](items/{p.name})" in index for p in [first, second])
    assert glossary.count("## 商品\n") == 1
    assert "利用するAPI" in glossary and f"](items/{first.name})" in glossary
    assert (output / "items" / first.name).read_text(encoding="utf-8") == first.read_text(
        encoding="utf-8"
    )
    second.unlink()
    generate(source, output)
    assert second.stem not in (output / "index.md").read_text(encoding="utf-8")
    assert not (output / "items" / second.name).exists()


def test_undefined_term_in_condition_or_result_fails(tmp_path):
    """条件または操作で未定義の用語を使うと、その用語を示して失敗する。"""
    write_item(tmp_path, FIRST.replace("商品", "製品").replace("検索", "照会"))
    with pytest.raises(ValueError, match="未定義の共通語彙") as error:
        generate(tmp_path, tmp_path / "out")
    assert "製品" in str(error.value) and "照会" in str(error.value)


def test_duplicate_definition_fails(tmp_path):
    """別々の要件で同じ用語を再定義すると失敗する。"""
    write_item(tmp_path)
    write_item(tmp_path, SECOND)
    with pytest.raises(ValueError, match="定義済み"):
        generate(tmp_path, tmp_path / "out")


def test_wrong_filename_and_empty_section_fail(tmp_path):
    """見出しと異なるファイル名と、理由が空欄の要件をそれぞれ拒否する。"""
    path = write_item(tmp_path)
    wrong = path.rename(tmp_path / "別名.md")
    with pytest.raises(ValueError, match="ファイル名"):
        generate(tmp_path, tmp_path / "out")
    wrong.rename(path)
    path.write_text(path.read_text(encoding="utf-8").replace("用途で探すため。", ""), encoding="utf-8")
    with pytest.raises(ValueError, match="4つの見出し"):
        generate(tmp_path, tmp_path / "out")


def test_feature_requires_added_requirement(tmp_path, monkeypatch):
    """実際のPR相当の差分で編集・改名・テンプレートを除外し、新規要件だけを受け付ける。"""
    monkeypatch.chdir(tmp_path)

    def git(*args):
        return check_output(["git", "-c", "core.hooksPath=/dev/null", *args]).decode().strip()

    def commit():
        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "test")

    git("init", "-q")
    ITEMS.mkdir(parents=True)
    original = write_item(ITEMS)
    commit()
    base = git("rev-parse", "HEAD")
    write_item(ITEMS, background=DEFINITIONS + "変更した。")
    (ITEMS.parent / "template.md").write_text("要件のひな形", encoding="utf-8")
    commit()
    output = tmp_path.parent / (tmp_path.name + "-output")
    items = generate(ITEMS, output)
    with pytest.raises(ValueError, match="新規"):
        check_feature("feat/catalog", base, items)
    check_feature("fix/catalog", base, items)

    original.unlink()
    write_item(ITEMS, SECOND)
    commit()
    with pytest.raises(ValueError, match="新規"):
        check_feature("feat/catalog", base, generate(ITEMS, output))

    write_item(ITEMS, FIRST.replace("探すとき", "比較するとき"), "検索範囲を指定する。")
    commit()
    check_feature("feat/catalog", base, generate(ITEMS, output))
