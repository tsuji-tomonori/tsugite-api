"""OpenAPIの操作と内部参照を読み取る。"""

from urllib.parse import unquote


def path_items(spec):
    """Read concrete Path Items and internal Path Item references in 3.0 and 3.1."""
    for path, item in spec.get("paths", {}).items():
        if not path.startswith("/"):
            continue
        seen = set()
        while isinstance(item, dict) and "$ref" in item:
            ref = item["$ref"]
            if ref in seen or not ref.startswith("#/"):
                item = None
                break
            seen.add(ref)
            item = spec
            for part in unquote(ref[2:]).split("/"):
                item = (
                    item.get(part.replace("~1", "/").replace("~0", "~"))
                    if isinstance(item, dict)
                    else None
                )
        if isinstance(item, dict):
            yield path, item
