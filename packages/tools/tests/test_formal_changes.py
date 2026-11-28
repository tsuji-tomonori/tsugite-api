# 一時リポジトリの分岐点と変更した方針から、同じPRの形式仕様だけを照合する。
import json
import subprocess
from pathlib import Path

import pytest

from packages.tools.design import formal_changes as gate

POLICY = "申請を承認する。\n\n> Quint review.approveTest — 承認時の状態を観測する。"
DISPLAY = "バナーを閉じる。\n\n> 実装検証 test_banner — 表示のみ：閉じた後の画面を検査する。"


def item(policy):
    return (
        f"# **利用者**は、操作できる\n\n## 決めた方針\n\n{policy}\n\n### 受入テスト\n\n"
        "- 受入テスト `packages/frontend/tests/test_banner.py::test_banner`\n"
    )


@pytest.fixture
def pr(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gate.git("init", "-q")
    gate.git("config", "user.name", "Test")
    gate.git("config", "user.email", "test@example.invalid")
    path = Path(gate.ITEMS) / "申請.md"
    path.parent.mkdir(parents=True)
    path.write_text(item(POLICY))
    gate.FORMAL.mkdir(parents=True)

    def commit():
        gate.git("add", ".")
        gate.git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "test")
        return gate.git("rev-parse", "HEAD").strip()

    return path, commit


def test_business_policy_requires_its_quint_domain(pr):
    """無関係なモデル、生成JSONの編集、表示段落の例外では業務ルールの変更を通さない。"""
    path, commit = pr
    base = commit()
    path.write_text(item(POLICY.replace("承認する。", "却下する。") + "\n\n" + DISPLAY))
    (gate.FORMAL / "audience.qnt").write_text("module audience {}")
    (gate.FORMAL / "cases.json").write_text('{"review.approveTest": []}')
    commit()
    with pytest.raises(ValueError, match="対応するQuint.*review.approveTest"):
        gate.check(base)


def test_implementation_only_policy_requires_category_reason_and_test(pr):
    """表示段落には理由と実装テストを求め、開発工程の指定は開発者の方針に限る。"""
    path, commit = pr
    base = commit()
    extra = path.with_name("画面.md")
    for invalid in (
        DISPLAY.replace("表示のみ：", ""),
        DISPLAY.replace("閉じた後の画面を検査する。", " "),
        DISPLAY.replace("test_banner", ""),
        DISPLAY.replace("表示のみ", "開発工程"),
    ):
        extra.write_text(item(invalid))
        commit()
        with pytest.raises(ValueError, match="実装検証の区分と理由"):
            gate.check(base)
    extra.write_text(item(DISPLAY))
    commit()
    gate.check(base)
    extra.write_text(item(DISPLAY.replace("表示のみ", "開発工程")).replace("**利用者**", "**開発者**"))
    commit()
    gate.check(base)


def test_removed_quint_policy_cannot_downgrade_to_display(pr):
    """既存の業務ルールを表示例外に置き換えたり要件ごと削除したりすると元のモデル差分が必要になる。"""
    path, commit = pr
    base = commit()
    path.write_text(item(DISPLAY))
    commit()
    with pytest.raises(ValueError, match="review.approveTest"):
        gate.check(base)
    path.unlink()
    commit()
    with pytest.raises(ValueError, match="review.approveTest"):
        gate.check(base)


def test_renamed_item_and_other_branch_use_merge_base(pr):
    """要件の改名や段落の並べ替えは許可し、相手ブランチだけのモデル更新を借用できない。"""
    path, commit = pr
    path.write_text(item(POLICY + "\n\n" + DISPLAY))
    base = commit()
    gate.git("checkout", "-qb", "target")
    (gate.FORMAL / "review.qnt").write_text("module review {}")
    target = commit()
    gate.git("checkout", "-qb", "proposal", base)
    renamed = path.rename(path.with_name("承認.md"))
    renamed.write_text(item(DISPLAY + "\n\n" + POLICY))
    commit()
    gate.check(target)
    renamed.write_text(renamed.read_text().replace("申請を承認", "申請を却下"))
    commit()
    with pytest.raises(ValueError, match="review.approveTest"):
        gate.check(target)


def test_only_referenced_runs_or_shared_model_count(pr, monkeypatch):
    """Quintの解析結果からコメント・内部番号・別ケースを除き、参照ケースの追加や共通モデルの変更を認める。"""
    path, commit = pr
    model = gate.FORMAL / "review.qnt"

    # パッケージ単体テストではQuint CLIの出力境界に解析済みの宣言を渡す。
    def parse(command, **kwargs):
        if command[0] == gate.QUINT:
            _, _, source, _, output = command
            output.write_text(source.read_text())
            return subprocess.CompletedProcess(command, 0)
        return run(command, **kwargs)

    run = subprocess.run
    monkeypatch.setattr(subprocess, "run", parse)
    declarations = [
        {"qualifier": "run", "name": "approveTest", "expr": {"kind": "int", "value": 1, "id": 1}},
        {"qualifier": "run", "name": "otherTest", "expr": {"value": 2}},
        {"qualifier": "val", "name": "safe", "expr": {"value": True}},
    ]

    def save():
        model.write_text(json.dumps({"modules": [{"name": "review", "declarations": declarations}]}))
        return commit()

    base = save()
    path.write_text(item(POLICY.replace("承認する。", "却下する。")))
    declarations.append({"name": "unused", "qualifier": "val", "expr": {"value": True}})
    declarations[0]["doc"] = "新しいコメント"
    declarations[0]["expr"]["id"] = 88
    declarations[1]["expr"]["value"] = 10
    save()
    with pytest.raises(ValueError, match="review.approveTest"):
        gate.check(base)
    declarations.append({"qualifier": "run", "name": "rejectTest", "expr": {"value": 3}})
    path.write_text(item(POLICY.replace("review.approveTest", "review.approveTest review.rejectTest")))
    save()
    gate.check(base)
    path.write_text(item(POLICY.replace("承認する。", "却下する。")))
    declarations[2]["expr"] = {
        "kind": "app",
        "opcode": "and",
        "args": [{"kind": "name", "name": "unused"}],
    }
    save()
    gate.check(base)
