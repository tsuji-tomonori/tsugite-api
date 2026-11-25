# 実際のHTTP応答を公開仕様と照合する。
from functools import cached_property

import schemathesis
from starlette.routing import compile_path


class Contract:
    def __init__(self, document):
        self.document = document
        self.schema = schemathesis.openapi.from_dict(document)

    @cached_property
    def paths(self):
        return [
            (compile_path(path)[0], path)
            for path in sorted(self.document["paths"], key=lambda p: "{" in p)
        ]

    def check(self, path, method, response):
        operation = self.document["paths"][path][method.lower()]
        status = str(response.status_code)
        assert status in operation["responses"], (method, path, status)
        content = operation["responses"][status].get("content", {})
        if content:
            media = response.headers.get("content-type", "").partition(";")[0]
            assert media in content, (method, path, status, media)
        self.schema[path][method].validate_response(response)

    def observe(self, response):
        path = response.request.url.path
        method = response.request.method
        for pattern, template in self.paths:
            if pattern.fullmatch(path) and method.lower() in self.document["paths"][template]:
                response.read()
                self.check(template, method, response)
                return


def validation_request(path, operation):
    """FastAPIが検査するボディ、必須引数、型・列挙値・長さの制約から不正入力を作る。"""
    values = {p["name"]: "test" for p in operation.get("parameters", []) if p["in"] == "path"}
    if "requestBody" in operation:
        return path.format(**values), {"content": b"{", "headers": {"Content-Type": "application/json"}}
    for p in operation["parameters"]:
        schema = p["schema"]
        if p["in"] == "query" and p.get("required"):
            return path.format(**values), {}
        if "maxLength" in schema:
            value = "a" * (schema["maxLength"] + 1)
        elif (
            schema.get("type") in {"boolean", "integer", "number"}
            or "enum" in schema
            or "format" in schema
        ):
            value = "invalid"
        else:
            continue
        if p["in"] == "path":
            values[p["name"]] = value
            return path.format(**values), {}
        return path.format(**values), {"params": {p["name"]: value}}
    raise AssertionError(f"422の入力例が必要です: {path}")
