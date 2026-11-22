"""Bind standalone #: comments to Python declarations using AST and COMMENT tokens."""

import ast
import tokenize
from functools import cache
from io import StringIO
from pathlib import Path


class SourceDocs:
    def __init__(self, source, filename="<source>"):
        self.tree = ast.parse(source, filename=filename)
        self.comments = {
            token.start[0]: token.string.removeprefix("#:").strip()
            for token in tokenize.generate_tokens(StringIO(source).readline)
            if token.type == tokenize.COMMENT
            and token.string.startswith("#:")
            and not token.line[: token.start[1]].strip()
        }

    def label(self, node):
        return self.comments.get(node.lineno - 1, "")

    def fields(self, cls):
        return {
            item.target.id: self.label(item)
            for item in cls.body
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
        }


@cache
def read_source(path: Path):
    # The argument is always a Python implementation file.
    if path.suffix != ".py":
        raise ValueError(f"Pythonソースを指定してください: {path}")
    return SourceDocs(path.read_text(encoding="utf-8"), str(path))
