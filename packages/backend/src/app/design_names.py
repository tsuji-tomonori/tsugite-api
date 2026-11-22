"""Japanese display names for the portal's own OpenAPI contract."""

import tomllib
from functools import cache
from pathlib import Path

from fastapi import FastAPI

from app.apis.product_contract import describe_product_fields


@cache
def vocabulary():
    with Path(__file__).with_name("api_names.toml").open("rb") as file:
        return tomllib.load(file)


def localize(schema, *, strict=False):
    names = vocabulary()

    def label(group, key, fallback=None):
        result = names[group].get(key, fallback)
        if strict and not result:
            raise ValueError(f"api_names.toml に和名を追加してください: [{group}] {key}")
        return result

    schemas = schema.get("components", {}).get("schemas", {})
    describe_product_fields(schemas)
    for model, record in schemas.items():
        if title := label("schemas", model):
            record["title"] = title
        for key, prop in record.get("properties", {}).items():
            title = label("context", f"{model}.{key}", names["fields"].get(key))
            if title and isinstance(prop, dict):
                prop["title"] = title
    for path, item in schema["paths"].items():
        resource = path.removeprefix("/api/").split("/")[0]
        for method, op in item.items():
            if method not in {"get", "post", "put", "patch", "delete", "head", "options", "trace"}:
                continue
            if title := label("operations", f"{method.upper()} {path}"):
                op["summary"] = title
            for param in [*item.get("parameters", []), *op.get("parameters", [])]:
                key = param["name"]
                title = label("resource_keys", resource) if key == "key" else label("parameters", key)
                if title:
                    param["x-ja-name"] = title
                    param.setdefault("description", title)
                    if isinstance(param.get("schema"), dict):
                        param["schema"]["title"] = title
            for response in op.get("responses", {}).values():
                response["description"] = {
                    "Successful Response": "正常に処理できました",
                    "Validation Error": "入力内容が条件を満たしていません",
                }.get(response["description"], response["description"])
                for key, header in response.get("headers", {}).items():
                    if title := label("parameters", key):
                        header["x-ja-name"] = title
                        header.setdefault("description", title)


class PortalAPI(FastAPI):
    def openapi(self):
        previous = self.openapi_schema
        document = super().openapi()
        if document is not previous:
            localize(document)
        return document
