# ミューテーション検証を小さなテスト対象で動かし、実行前後の結果を照合する。
import sys

import pytest

from packages.tools.testing import mutation_test


@pytest.mark.parametrize(
    ("assertion", "status"),
    [
        pytest.param(
            "assert enabled",
            0,
            id="killed",
            marks=pytest.mark.case_detail("値の変化で対象のテストが失敗すれば検出する"),
        ),
        pytest.param(
            "assert isinstance(enabled, bool)",
            1,
            id="survived",
            marks=pytest.mark.case_detail("変更後も成功するテストを検出に含めない"),
        ),
        pytest.param(
            "assert not enabled",
            1,
            id="baseline-fails",
            marks=pytest.mark.case_detail("元の実装で失敗するテストを検出に含めない"),
        ),
        pytest.param(
            "pytest.skip('対象外')",
            1,
            id="skip",
            marks=pytest.mark.case_detail("スキップを変異の検出に含めない"),
        ),
    ],
)
def test_local_mutation_compares_target_before_and_after(monkeypatch, assertion, status):
    """同じ単体テストが元の実装で成功し変異で失敗した場合だけ検出に数える。"""
    mutant = mutation_test.Mutation("tools", "値の変更", "feature.py", "True", "False", "test_flag.py")

    def copy_fixture(workspace):
        (workspace / "feature.py").write_text("enabled = True\n")
        (workspace / "test_flag.py").write_text(
            f"import pytest\nfrom feature import enabled\n\ndef test_enabled():\n    {assertion}\n"
        )

    monkeypatch.setattr(mutation_test, "copy_sources", copy_fixture)
    monkeypatch.setattr(mutation_test, "MUTATIONS", (mutant,))
    monkeypatch.setattr(sys, "argv", ["mutation_test", "--layer", "tools"])
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    assert mutation_test.main() == status
