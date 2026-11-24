# 要件のMarkdown原本を検査し、相対リンクで読める二つの索引を生成する。
"""要件のMarkdown原本を検査し、相対リンクで読める二つの索引を生成する。"""

import argparse
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

ITEMS = Path("docs/requirements/items")
SECTIONS = ("背景", "なぜ必要か", "決めた方針", "却下した方針")
TERM = re.compile(r"\*\*([^*\n]+)\*\*")
DEFINITION = re.compile(r"\*\*([^*\n]+)\*\*（([^（）\n]+)）")


@dataclass(frozen=True)
class Requirement:
    path: Path
    actor: str
    terms: set[str]
    body: str


def read_requirement(path: Path) -> Requirement:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{path}: 通常のMarkdownファイルを置いてください")
    body = path.read_text(encoding="utf-8")
    heading, _, rest = body.partition("\n")
    title = heading.removeprefix("# ")
    if not heading.startswith("# ") or TERM.sub(r"\1", title) != path.stem:
        raise ValueError(f"{path}: 要件文をそのままファイル名にしてください")
    sentence = re.fullmatch(r"(.+?)は、([^、]+?)とき、([^、]+?)できる", title)
    if not sentence:
        raise ValueError(f"{path}: 主体は、条件のとき、操作できる の順で書いてください")
    actor, condition, action = sentence.groups()
    if not TERM.fullmatch(actor) or not all(TERM.search(part) for part in (condition, action)):
        raise ValueError(f"{path}: 主体・条件・操作の共通語彙を太字で指定してください")
    sections = re.split(r"^## (.+)$", rest, flags=re.MULTILINE)
    if (
        sections[0].strip()
        or tuple(sections[1::2]) != SECTIONS
        or not all(section.strip() for section in sections[2::2])
        or re.search(r"^# ", rest, re.MULTILINE)
    ):
        raise ValueError(f"{path}: 4つの見出しとそれぞれの本文が必要です")
    return Requirement(path, actor[2:-2], set(TERM.findall(title)), body)


def link(item: Requirement) -> str:
    return f"[{item.path.stem}](items/{quote(item.path.name)})"


def generate(source: Path, output: Path) -> list[Requirement]:
    items = [read_requirement(path) for path in sorted(source.iterdir())]
    if not items or any(item.path.suffix != ".md" for item in items):
        raise ValueError(f"{source}: 要件を1件につき1つの.mdファイルで置いてください")

    definitions: dict[str, tuple[str, Requirement]] = {}
    groups: dict[str, list[Requirement]] = defaultdict(list)
    for item in items:
        groups[item.actor].append(item)
        for term, meaning in DEFINITION.findall(item.body.partition("\n")[2]):
            if term in definitions:
                raise ValueError(f"{item.path}: {term} は {definitions[term][1].path} で定義済みです")
            definitions[term] = (meaning, item)
    for item in items:
        unknown = item.terms - definitions.keys()
        if unknown:
            raise ValueError(f"{item.path}: 未定義の共通語彙 {', '.join(sorted(unknown))}")

    index = ["# 要件一覧", "", "[用語一覧](glossary.md)", "", f"全{len(items)}件。"]
    for actor, group in sorted(groups.items()):
        index.extend(["", f"## {actor}", ""])
        index.extend(f"- {link(item)}" for item in group)
    glossary = ["# 用語一覧", "", "[要件一覧](index.md)"]
    for term, (meaning, item) in sorted(definitions.items()):
        glossary.extend(["", f"## {term}", "", meaning, "", f"定義元　{link(item)}"])

    copies = output / "items"
    copies.mkdir(parents=True, exist_ok=True)
    for old in copies.glob("*.md"):
        if not (source / old.name).exists():
            old.unlink()
    for item in items:
        (copies / item.path.name).write_text(item.body, encoding="utf-8", newline="\n")
    for name, lines in (("index.md", index), ("glossary.md", glossary)):
        (output / name).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return items


def check_feature(branch: str, base: str | None, items: list[Requirement]) -> None:
    if branch != "feat" and not branch.startswith("feat/"):
        return
    if not base:
        raise ValueError("featブランチの新規要件を検査するには --base が必要です")
    paths = (
        subprocess.check_output(
            [
                "git",
                "diff",
                "--find-renames",
                "--find-copies-harder",
                "--diff-filter=A",
                "--name-only",
                "-z",
                f"{base}...HEAD",
                "--",
            ]
        )
        .decode("utf-8")
        .split("\0")
    )
    if not set(paths).intersection(item.path.as_posix() for item in items):
        raise ValueError("featブランチには新規の要件ファイルが1件以上必要です")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default="")
    parser.add_argument("--base")
    args = parser.parse_args()
    try:
        items = generate(ITEMS, Path("artifacts/requirements"))
        check_feature(args.branch, args.base, items)
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    print(f"要件{len(items)}件から要件一覧と用語一覧を生成しました")


if __name__ == "__main__":
    main()
