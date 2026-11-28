# 変更した方針とQuintの宣言をGitの分岐点から照合する。
"""PRで変わった要件の方針を、分岐点からのQuint宣言の差分と照合する。"""

import argparse
import json
import re
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory

ITEMS = "docs/requirements/items"
FORMAL = Path("tests/formal")
QUINT = FORMAL / "node_modules/.bin/quint"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], encoding="utf-8")


@dataclass(frozen=True)
class Clause:
    text: str
    refs: frozenset[str]
    implementation_only: bool


def clauses(body: str) -> set[Clause]:
    policy = body.partition("## 決めた方針\n")[2].partition("### 受入テスト")[0]
    if not policy:
        return set()
    developer = body.startswith("# **開発者**は、")
    blocks = policy.strip().split("\n\n")
    result = set()
    for text, evidence in zip(blocks[::2], blocks[1::2], strict=True):
        refs = set()
        exception = False
        for line in evidence.splitlines():
            method, _, reason = line.partition(" — ")
            if method.startswith("> Quint "):
                refs.update(method.removeprefix("> Quint ").split())
            elif method.startswith("> 実装検証 test_"):
                category, _, detail = reason.partition("：")
                exception |= bool(detail.strip()) and (
                    category == "表示のみ" or (developer and category == "開発工程")
                )
        result.add(Clause(" ".join(text.split()), frozenset(refs), exception))
    return result


def changed_items(base: str) -> Iterator[tuple[str, str, str]]:
    fields = iter(git("diff", "-M", "--name-status", "-z", base, "HEAD", "--", ITEMS).split("\0")[:-1])
    for status in fields:
        old = new = next(fields)
        if status.startswith("R"):
            new = next(fields)
        before = "" if status == "A" else git("show", f"{base}:{old}")
        after = "" if status == "D" else git("show", f"HEAD:{new}")
        yield new, before, after


def model_declarations(source: str, domain: str) -> dict:
    """構文木の識別番号、コメントと宣言順に依存せず、式・型・文字列の内容を比較する。"""
    with TemporaryDirectory() as directory:
        model = Path(directory) / f"{domain}.qnt"
        output = Path(directory) / "ir.json"
        model.write_text(source, encoding="utf-8")
        subprocess.run([QUINT, "parse", model, "--out", output], check=True)
        ir = json.loads(
            output.read_text(encoding="utf-8"),
            object_hook=lambda obj: {k: v for k, v in obj.items() if k not in {"id", "doc"}},
        )
    module = next(m for m in ir["modules"] if m["name"] == domain)
    return {decl["name"]: decl for decl in module["declarations"]}


def referenced_names(node) -> Iterator[str]:
    """Quint式の名前参照と演算子の呼び出しをたどる。"""
    if isinstance(node, dict):
        if node.get("kind") == "name":
            yield node["name"]
        elif node.get("kind") == "app":
            yield node["opcode"]
        for value in node.values():
            yield from referenced_names(value)
    elif isinstance(node, list):
        for value in node:
            yield from referenced_names(value)


def relevant_declarations(declarations: dict, case: str) -> dict:
    pending = ["init", "step", "safe", case]
    reached = {}
    while pending:
        name = pending.pop()
        if name in declarations and name not in reached:
            reached[name] = declarations[name]
            pending.extend(referenced_names(reached[name]))
    return reached


def model_changes(base: str) -> Callable[[str], bool]:
    changed = set(git("diff", "--name-only", "-z", base, "HEAD", "--", str(FORMAL)).split("\0"))

    @cache
    def declarations(revision: str, domain: str) -> dict:
        path = f"{FORMAL}/{domain}.qnt"
        if not git("ls-tree", "--name-only", revision, "--", path):
            return {}
        return model_declarations(git("show", f"{revision}:{path}"), domain)

    @cache
    def changed_case(ref: str) -> bool:
        if not re.fullmatch(r"[A-Za-z_]\w*\.[A-Za-z_]\w*Test", ref):
            raise ValueError(f"Quintケースの指定が不正です: {ref}")
        domain, case = ref.split(".")
        if f"{FORMAL}/{domain}.qnt" not in changed:
            return False

        return relevant_declarations(declarations(base, domain), case) != relevant_declarations(
            declarations("HEAD", domain), case
        )

    return changed_case


def check(base_ref: str) -> None:
    base = git("merge-base", base_ref, "HEAD").strip()
    changed_case = model_changes(base)
    errors = []
    for path, before, after in changed_items(base):
        old, new = clauses(before), clauses(after)
        added = new - old
        changed_domains = {ref.split(".")[0] for clause in added for ref in clause.refs}
        # 同じモデルの新ケースで方針を置き換えたときは、その新ケースの差分を検査する。
        removed = {
            clause
            for clause in old - new
            if clause.refs and not any(ref.split(".")[0] in changed_domains for ref in clause.refs)
        }
        for clause in added:
            if not clause.refs and not clause.implementation_only:
                errors.append(f"{path}: {clause.text} — Quintケースか、実装検証の区分と理由が必要です")
        for clause in added | removed:
            if clause.refs and not any(changed_case(ref) for ref in sorted(clause.refs)):
                refs = " ".join(sorted(clause.refs))
                errors.append(
                    f"{path}: {clause.text} — 対応するQuintモデルまたはケースを更新してください: {refs}"
                )
    if errors:
        raise ValueError("\n".join(sorted(set(errors))))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    try:
        check(parser.parse_args().base)
    except ValueError as error:
        parser.exit(1, f"{error}\n")
