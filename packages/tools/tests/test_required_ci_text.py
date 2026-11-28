"""CIとコミット時のテキスト検査を一時リポジトリの実際の差分で確かめる。"""

import subprocess
import sys
from pathlib import Path

import pytest

from packages.tools.ci import check_text


def git(*arguments):
    return subprocess.check_output(["git", *arguments], text=True).strip()


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    git("init", "--quiet", "-b", "feat/texts")
    git("config", "user.name", "テスト")
    git("config", "user.email", "test@example.invalid")
    git("config", "core.autocrlf", "false")
    (tmp_path / ".gitattributes").write_text("*.md text\n*.png binary\n")
    (tmp_path / "既存.md").write_bytes(b"old\n")
    git("add", ".")
    git("commit", "-qm", "base")
    return tmp_path


@pytest.mark.parametrize(
    ("content", "valid"),
    [
        pytest.param(
            "継手\n".encode(),
            True,
            id="utf8",
            marks=pytest.mark.case_detail("日本語のUTF-8とLFを許可する"),
        ),
        pytest.param(
            b"\xef\xbb\xbfheading\n",
            False,
            id="bom",
            marks=pytest.mark.case_detail("UTF-8のBOMを拒否する"),
        ),
        pytest.param(
            b"\xff\n",
            False,
            id="encoding",
            marks=pytest.mark.case_detail("UTF-8として読めないバイトを拒否する"),
        ),
        pytest.param(
            b"a\r\nb\n", False, id="crlf", marks=pytest.mark.case_detail("途中のCRLFを拒否する")
        ),
        pytest.param(
            b"a", False, id="no-newline", marks=pytest.mark.case_detail("末尾の改行がない文書を拒否する")
        ),
        pytest.param(
            b"a\n\n",
            False,
            id="two-newlines",
            marks=pytest.mark.case_detail("末尾に改行が二つある文書を拒否する"),
        ),
    ],
)
def test_text_encoding_and_terminator(content, valid):
    """変更したテキストの符号化と改行が規約に一致するときだけ受け付ける。"""
    assert (not list(check_text.violations(content))) == valid


def test_staged_text_uses_index_and_ignores_binary(checkout, monkeypatch, capsys):
    """ステージ済みの不正な日本語名の文書を特定し、修正をステージしたら画像とともに許可する。"""
    name = "空白 を含む.md"
    document = checkout / name
    document.write_bytes(b"missing newline")
    (checkout / "capture.png").write_bytes(b"\x89PNG\0\xff")
    git("add", ".")
    document.write_text("修正済み\n")
    monkeypatch.setattr(sys, "argv", ["check_text", "--staged"])
    assert check_text.main() == 1
    output = capsys.readouterr()
    assert name in output.out + output.err
    git("add", name)
    assert check_text.main() == 0


def test_pull_request_range_and_full_checkout(checkout, monkeypatch):
    """PR差分は未変更の既存違反を除外し、全体検査は既存違反も検出する。"""
    (checkout / "既存.md").write_bytes(b"no newline")
    git("add", ".")
    git("commit", "-qm", "existing invalid text")
    base = git("rev-parse", "HEAD")
    (checkout / "追加.md").write_text("追記\n")
    git("add", ".")
    git("commit", "-qm", "new valid text")
    monkeypatch.setattr(sys, "argv", ["check_text", "--base", base])
    assert check_text.main() == 0
    monkeypatch.setattr(sys, "argv", ["check_text"])
    assert check_text.main() == 1
    Path("追加.md").write_bytes(b"invalid")
    git("add", ".")
    git("commit", "-qm", "changed invalid text")
    monkeypatch.setattr(sys, "argv", ["check_text", "--base", base])
    assert check_text.main() == 1


@pytest.mark.parametrize(
    "branch",
    [
        pytest.param("main", id="main", marks=pytest.mark.case_detail("mainでの直接コミットを拒否する")),
        pytest.param(
            "master", id="master", marks=pytest.mark.case_detail("masterでの直接コミットを拒否する")
        ),
    ],
)
def test_staged_protects_release_branches(checkout, monkeypatch, branch):
    """配備対象ブランチでは規約どおりの文書だけをステージしていても直接コミットを拒否する。"""
    git("switch", "-qc", branch)
    (checkout / "説明.md").write_text("正常な文書\n")
    git("add", "説明.md")
    monkeypatch.setattr(sys, "argv", ["check_text", "--staged"])
    with pytest.raises(SystemExit, match="ブランチ"):
        check_text.main()
