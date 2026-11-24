"""Project the source comments of registered routes and models onto their OpenAPI contract."""

import ast
import inspect
from functools import cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts
from tsugite_db.source_docs import read_source

from app.schemas.product_contract import describe_product_fields


@cache
def declarations():
    models, enums = {}, {}
    for path in sorted(Path(__file__).parent.rglob("*.py")):
        source = read_source(path)
        for node in ast.walk(source.tree):
            if isinstance(node, ast.ClassDef) and source.label(node):
                if node.name in models:
                    raise ValueError(f"スキーマ名が重複しています: {path} {node.name}")
                models[node.name] = (source, node)
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and node.value.id == "Literal"
            ):
                values = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
                if all(isinstance(v, ast.Constant) and source.label(v) for v in values):
                    key = tuple(v.value for v in values if isinstance(v, ast.Constant))
                    labels = tuple(source.label(v) for v in values)
                    if enums.setdefault(key, labels) != labels:
                        raise ValueError(f"同じ列挙型の説明が一致しません: {path} {key}")
    return models, enums


@cache
def model_fields(model):
    models, _ = declarations()
    source, cls = models[model]
    inherited = {}
    for base in reversed(cls.bases):
        if isinstance(base, ast.Name) and base.id in models:
            inherited.update(model_fields(base.id))
    return {**inherited, **source.fields(cls)}


@cache
def function_source(call):
    if not inspect.isfunction(call):
        return None
    call = inspect.unwrap(call)
    source = read_source(Path(call.__code__.co_filename))
    first = call.__code__.co_firstlineno
    for node in ast.walk(source.tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == call.__name__:
            if min([node.lineno, *(d.lineno for d in node.decorator_list)]) <= first <= node.lineno:
                return source, node
    return None


def parameter_labels(dependency):
    labels = {}
    for child in dependency.dependencies:
        labels.update(parameter_labels(child))
    if parsed := function_source(dependency.call):
        source, fn = parsed
        args = {a.arg: a for a in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]}
        for fields in (
            dependency.path_params,
            dependency.query_params,
            dependency.header_params,
            dependency.cookie_params,
        ):
            for field in fields:
                if field.name in args:
                    labels[field.alias] = source.label(args[field.name])
    return labels


def operation_labels(route, method):
    parsed = function_source(route.endpoint)
    if parsed is None:
        return "", {}
    source, fn = parsed
    labels = parameter_labels(route.dependant)
    for dec in fn.decorator_list:
        if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute) or not dec.args:
            continue
        path = dec.args[0]
        if not isinstance(path, ast.Constant) or not isinstance(path.value, str):
            continue
        if dec.func.attr not in {method.lower(), "api_route"} or not route.path.endswith(path.value):
            continue
        # OpenAPI extras can declare HTTP headers independently of the handler signature.
        labels.update(source.literal_labels(dec))
        return source.label(dec).replace("{method}", method), labels
    return "", labels


def localize(schema, routes=(), *, strict=False):
    def required(value, location):
        if strict and not value:
            raise ValueError(f"定義元に和名のコメントが必要です: {location}")
        return value

    models, _ = declarations()
    schemas = schema.get("components", {}).get("schemas", {})
    describe_product_fields(schemas)
    for model, record in schemas.items():
        if model not in models:
            required(None, model)
            continue
        source, node = models[model]
        record["title"] = source.label(node)
        labels = model_fields(model)
        for key, prop in record.get("properties", {}).items():
            if title := required(labels.get(key), f"{model}.{key}"):
                prop["title"] = title

    endpoints = {
        (route.path_format, method.lower()): route
        for route in iter_route_contexts(routes)
        if isinstance(route.original_route, APIRoute)
        for method in (route.methods or ())
    }
    for path, item in schema["paths"].items():
        for method, op in item.items():
            if method not in {"get", "post", "put", "patch", "delete", "head", "options", "trace"}:
                continue
            route = endpoints.get((path, method))
            title, labels = operation_labels(route, method.upper()) if route else ("", {})
            location = f"{method.upper()} {path}"
            if required(title, location):
                op["summary"] = title
            for param in [*item.get("parameters", []), *op.get("parameters", [])]:
                key = param["name"]
                if title := required(labels.get(key), f"{location} {key}"):
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
                    if title := required(labels.get(key), f"{location} {key}"):
                        header["x-ja-name"] = title
                        header.setdefault("description", title)


class PortalAPI(FastAPI):
    def openapi(self):
        previous = self.openapi_schema
        document = super().openapi()
        if document is not previous:
            localize(document, self.routes)
        return document
