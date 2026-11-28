"""構文木とコメントのトークンから、業務名を示す「#:」と直後のPython宣言を対応付ける。"""

import ast
import tokenize
from functools import cache
from io import StringIO
from pathlib import Path


class SourceDocs:
    def __init__(self, source: str, filename: str = "<source>"):
        self.tree: ast.Module = ast.parse(source, filename=filename)
        self.comments = {
            token.start[0]: token.string.removeprefix("#:").strip()
            for token in tokenize.generate_tokens(StringIO(source).readline)
            if token.type == tokenize.COMMENT
            and token.string.startswith("#:")
            and not token.line[: token.start[1]].strip()
        }

    def label(self, node):
        return self.comments.get(node.lineno - 1, "")

    def literal_labels(self, node):
        """The first string literal on each annotated line names the actual API or SDK key."""
        strings = sorted(
            (
                item
                for item in ast.walk(node)
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            ),
            key=lambda item: (item.lineno, item.col_offset),
        )
        labels = {}
        seen = set()
        for item in strings:
            if item.lineno not in seen and (title := self.label(item)):
                labels[item.value] = title
                seen.add(item.lineno)
        return labels

    def fields(self, cls):
        return {
            item.target.id: self.label(item)
            for item in cls.body
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
        }


@cache
def read_source(path: Path) -> SourceDocs:
    # The argument is always a Python implementation file.
    if path.suffix != ".py":
        raise ValueError(f"Pythonソースを指定してください: {path}")
    return SourceDocs(path.read_text(encoding="utf-8"), str(path))
