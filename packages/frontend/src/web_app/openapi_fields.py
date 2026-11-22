from urllib.parse import unquote


def resolve(spec, node):
    """Resolve local JSON pointers without following remote or cyclic references."""
    seen = set()
    while isinstance(node, dict) and isinstance(node.get("$ref"), str):
        ref = node["$ref"]
        if not ref.startswith("#/") or ref in seen:
            break
        seen.add(ref)
        target = spec
        for part in unquote(ref[2:]).split("/"):
            name = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or name not in target:
                return node
            target = target[name]
        node = target
    return node


def parameters(spec, item, operation):
    merged = {}
    for source in (item, operation):
        for raw in source.get("parameters", []):
            param = resolve(spec, raw)
            if isinstance(param, dict) and "name" in param and "in" in param:
                merged[(param["in"], param["name"])] = param
    return list(merged.values())
