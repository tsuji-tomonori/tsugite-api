# Quintの実行履歴を再生成し、pytestが読む入力と期待状態の差分を検出する。
"""Quintの実行履歴を再生成し、pytestが読む入力と期待状態の差分を検出する。"""

import argparse
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "cases.json"


def decode(value):
    if isinstance(value, dict):
        if set(value) == {"#bigint"}:
            return int(value["#bigint"])
        return {key: decode(item) for key, item in value.items() if key != "#meta"}
    if isinstance(value, list):
        return [decode(item) for item in value]
    return value


def generate(quint, directory):
    cases = {}
    for model in sorted(ROOT.glob("*.qnt")):
        work = directory / model.stem
        work.mkdir()
        ir = work / "model.json"
        subprocess.run([quint, "parse", model, "--out", ir], check=True)
        module = next(m for m in json.loads(ir.read_text())["modules"] if m["name"] == model.stem)
        runs = {d["name"] for d in module["declarations"] if d.get("qualifier") == "run"}
        if not runs or any(not name.endswith("Test") for name in runs):
            raise ValueError(f"{model}: 実行可能な名前付きケースが必要です")
        subprocess.run(
            [
                quint,
                "test",
                model,
                "--backend=typescript",
                "--seed=1",
                "--out-itf",
                work / "{test}.itf.json",
            ],
            check=True,
        )
        for name in sorted(runs):
            trace = json.loads((work / f"{name}.itf.json").read_text())
            states = decode(trace["states"])
            if trace["#meta"]["status"] != "passed" or len(states) < 2:
                raise ValueError(f"{model}:{name}: 完了した操作列がありません")
            cases[f"{model.stem}.{name}"] = states
    return json.dumps(cases, ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quint", default="quint")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    with TemporaryDirectory() as tmp:
        generated = generate(args.quint, Path(tmp))
    if args.write:
        CASES.write_text(generated, encoding="utf-8")
    elif generated != CASES.read_text(encoding="utf-8"):
        raise SystemExit("Quintケースに差分があります。generate.py --write で更新してください")
