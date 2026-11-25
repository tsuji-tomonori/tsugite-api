# Quintが生成した確定履歴をpytestの入力にする。
"""Quintが生成した確定履歴をpytestの入力にする。"""

import json
from pathlib import Path

import pytest

CASES = json.loads((Path(__file__).parents[1] / "formal/cases.json").read_text())


def histories(domain):
    selected = [
        pytest.param(
            states, id=name, marks=pytest.mark.case_detail("形式仕様の操作と期待状態を照合する。")
        )
        for name, states in CASES.items()
        if name.split(".")[0] == domain
    ]
    if not selected:
        raise ValueError(f"{domain} の操作列がありません")
    return selected
