import inspect

import pytest

from tests.architecture.case_text import is_japanese_case_text


def pytest_collection_modifyitems(items):
    invalid = []
    for item in items:
        description = inspect.getdoc(getattr(item, "obj", None)) or ""
        details = [mark.args for mark in item.iter_markers("case_detail")]
        if not is_japanese_case_text(description):
            invalid.append(f"{item.nodeid}: 条件と期待結果を簡潔な日本語のdocstringで書いてください")
        if hasattr(item, "callspec") and not details:
            invalid.append(
                f"{item.nodeid}: パラメーターごとに case_detail で日本語の説明を付けてください"
            )
        for args in details:
            if len(args) != 1 or not isinstance(args[0], str) or not is_japanese_case_text(args[0]):
                invalid.append(f"{item.nodeid}: case_detail に簡潔な日本語の説明を1つ指定してください")
            else:
                description += f"（{args[0]}）"
        item.user_properties.append(("case_description", description))
    if invalid:
        raise pytest.UsageError("\n".join(invalid))
