"""Find possible storage effects from FastAPI dependencies and local Python calls."""

import ast
from collections import defaultdict
from dataclasses import dataclass, field
from functools import cache
from importlib.util import resolve_name
from pathlib import Path

import sqlglot
from sqlglot import exp
from tsugite_db.models import Base

ROOT = Path(__file__).resolve().parents[2]
FUNCTION = (ast.FunctionDef, ast.AsyncFunctionDef)


def name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return name(node.value) + "." + node.attr
    return ""


def literal(node):
    return node.value if isinstance(node, ast.Constant) else None


def body_nodes(node):
    """Visit executable statements, leaving nested functions to the call graph."""
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, FUNCTION + (ast.ClassDef,)):
            yield child
            yield from body_nodes(child)


@dataclass
class Facts:
    effects: set = field(default_factory=set)
    status: set = field(default_factory=set)
    calls: set = field(default_factory=set)
    unresolved: set = field(default_factory=set)
    edges: set = field(default_factory=set)


def raw_sql(sql):
    """Emit both the DML target and any source tables, excluding CTE aliases."""
    for stmt in sqlglot.parse(sql, read="postgres"):
        target = None
        op = "R"
        if isinstance(stmt, (exp.Insert, exp.Update, exp.Delete)):
            target = stmt.this
            if isinstance(target, exp.Schema):
                target = target.this
            op = {exp.Insert: "C", exp.Delete: "D", exp.Update: "U"}[type(stmt)]
        elif not isinstance(stmt, exp.Query):
            raise ValueError("未対応のSQL文")
        ctes = {cte.alias for cte in stmt.find_all(exp.CTE)}
        for table in stmt.find_all(exp.Table):
            if table is target or table.name not in ctes:
                yield (table.sql().split(" AS ")[0], op if table is target else "R")


def aws_action(operation):
    verb = operation.removeprefix("admin_").split("_")[0]
    return {
        "get": "R",
        "list": "R",
        "describe": "R",
        "scan": "R",
        "query": "R",
        "create": "C",
        "add": "C",
        "delete": "D",
        "remove": "D",
        "update": "U",
        "set": "U",
        "put": "C/U",
        "invoke": "実行",
    }.get(verb, "要確認")


class SourceIndex:
    def __init__(self, roots=None):
        self.functions = {}
        self.scopes = {}
        self.paths = {}
        self.models = {m.class_.__name__: m.local_table.name for m in Base.registry.mappers}
        for root in roots or [ROOT / "packages/backend/src", ROOT / "packages/database/src"]:
            for path in sorted(root.rglob("*.py")):
                module = ".".join(path.relative_to(root).with_suffix("").parts).removesuffix(".__init__")
                tree = ast.parse(path.read_text(encoding="utf-8"))
                package = module if path.stem == "__init__" else module.rpartition(".")[0]
                self.index(module, tree, path, {}, package)

    def index(self, scope, tree, path, inherited, package):
        symbols = dict(inherited)
        nodes = list(body_nodes(tree))
        for node in nodes:
            if isinstance(node, ast.ImportFrom):
                module = resolve_name("." * node.level + (node.module or ""), package)
                for alias in node.names:
                    symbols[alias.asname or alias.name] = f"{module}.{alias.name}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    symbols[alias.asname or alias.name.split(".")[0]] = (
                        alias.name if alias.asname else alias.name.split(".")[0]
                    )

        def children(parent):
            for node in ast.iter_child_nodes(parent):
                if isinstance(node, FUNCTION + (ast.ClassDef,)):
                    yield node
                else:
                    yield from children(node)

        definitions = list(children(tree))
        for child in definitions:
            symbols[child.name] = f"{scope}.{child.name}"
        self.scopes[scope] = symbols
        for child in definitions:
            key = symbols[child.name]
            if isinstance(child, FUNCTION):
                self.functions[key] = child
                self.paths[key] = path
            self.index(key, child, path, symbols, package)

    def resolve(self, func, node):
        parts = name(node).split(".")
        return ".".join([self.scopes[func].get(parts[0], parts[0]), *parts[1:]])

    @cache
    def inspect(self, func, bindings=()):
        node = self.functions[func]
        facts = Facts()
        # Sort in source order so a reassignment on another branch adds a possible type.
        nodes = sorted(
            (
                n
                for statement in node.body
                if not isinstance(statement, FUNCTION)
                for n in (statement, *body_nodes(statement))
            ),
            key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)),
        )
        types = defaultdict(set)
        transient = set()
        added = set()
        for param, table, is_new in bindings:
            types[param].add(table)
            if is_new:
                transient.add(param)
        services = defaultdict(set)

        def model(expr):
            symbol = self.resolve(func, expr)
            prefix = "tsugite_db.models."
            return (
                {self.models[symbol[len(prefix) :]]}
                if symbol.startswith(prefix) and symbol[len(prefix) :] in self.models
                else set()
            )

        # A variable loaded on one branch and constructed on another can represent an UPDATE.
        assignments = defaultdict(list)
        for statement in nodes:
            if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        assignments[target.id].append(statement.value)
        constructed = {
            key
            for key, values in assignments.items()
            if all(isinstance(value, ast.Call) and model(value.func) for value in values)
        }

        def is_transient(expr):
            return (
                isinstance(expr, ast.Name)
                and expr.id in transient
                or isinstance(expr, ast.Call)
                and bool(model(expr.func))
            )

        def entities(expr):
            if isinstance(expr, ast.Name):
                return types[expr.id] | model(expr)
            if isinstance(expr, ast.Call):
                values = model(expr.func)
                if name(expr.func) in ("db.get", "db.scalar", "db.scalars", "select", "session.get"):
                    for part in ast.walk(expr.args[0]) if expr.args else []:
                        if isinstance(part, ast.Name):
                            values |= model(part) | types[part.id]
                callee = self.functions.get(self.resolve(func, expr.func))
                if callee and callee.returns:
                    cls = self.resolve(self.resolve(func, expr.func), callee.returns).split(".")[-1]
                    if cls in self.models:
                        values.add(self.models[cls])
                return values
            if isinstance(expr, ast.IfExp):
                return entities(expr.body) | entities(expr.orelse)
            return set()

        def service(expr):
            if isinstance(expr, ast.Name):
                return services[expr.id]
            if isinstance(expr, ast.IfExp):
                return service(expr.body) | service(expr.orelse)
            if (
                isinstance(expr, ast.Call)
                and self.resolve(func, expr.func) in {"boto3.client", "app.integrations.upstream.aws"}
                and expr.args
            ):
                return {literal(expr.args[0]) or "動的サービス"}
            return set()

        def add(kind, resource, op, point, detail):
            facts.effects.add((kind, resource, op, func, point.lineno, detail))

        for part in nodes:
            if isinstance(part, (ast.Assign, ast.AnnAssign, ast.For, ast.NamedExpr)):
                targets = part.targets if isinstance(part, ast.Assign) else [part.target]
                value = part.iter if isinstance(part, ast.For) else part.value
                for target in targets:
                    if isinstance(target, ast.Name):
                        if target.id in constructed:
                            transient.add(target.id)
                        else:
                            transient.discard(target.id)
                        types[target.id].update(entities(value))
                        services[target.id].update(service(value))
                    for attr in ast.walk(target):
                        if (
                            isinstance(attr, ast.Attribute)
                            and isinstance(attr.ctx, ast.Store)
                            and not is_transient(attr.value)
                        ):
                            for table in entities(attr.value):
                                add("SQL", table, "U", part, attr.attr + " に代入")
            if not isinstance(part, ast.Call):
                continue
            full = self.resolve(func, part.func)
            if full == "db.add" and part.args and isinstance(part.args[0], ast.Name):
                added.add(part.args[0].id)
            if full in {"db.flush", "db.commit"}:
                transient.difference_update(added)
                added.clear()
            candidates = [full]
            if full in {"starlette.concurrency.run_in_threadpool", "asyncio.to_thread"} and part.args:
                candidates.append(self.resolve(func, part.args[0]))
            for candidate in candidates:
                if candidate not in self.functions:
                    continue
                target = self.functions[candidate]
                names = [a.arg for a in [*target.args.posonlyargs, *target.args.args]]
                args = part.args if candidate == full else part.args[1:]
                values = [
                    *zip(names, args),
                    *((item.arg, item.value) for item in part.keywords if item.arg),
                ]
                passed = tuple(
                    sorted({(k, table, is_transient(v)) for k, v in values for table in entities(v)})
                )
                facts.edges.add((candidate, passed))
            arg = part.args[0] if part.args else None
            if full == "setattr" and not is_transient(arg):
                for table in entities(arg):
                    add("SQL", table, "U", part, ast.unparse(part.func) + " による属性更新")
            if isinstance(part.func, ast.Attribute) and part.func.attr in {
                "select_from",
                "join",
                "outerjoin",
            }:
                for expr in part.args:
                    for inner in ast.walk(expr):
                        for table in model(inner):
                            add("SQL", table, "R", part, part.func.attr)
            if full == "fastapi.HTTPException":
                code = literal(
                    arg or next((k.value for k in part.keywords if k.arg == "status_code"), None)
                )
                if isinstance(code, int):
                    facts.status.add(code)
            if full in {
                "sqlalchemy.select",
                "sqlalchemy.insert",
                "sqlalchemy.update",
                "sqlalchemy.delete",
            } or name(part.func) in {"db.get", "db.add", "db.delete", "db.add_all", "session.get"}:
                op = {"insert": "C", "add": "C", "add_all": "C", "delete": "D", "update": "U"}.get(
                    full.split(".")[-1], "R"
                )
                found = set()
                for expr in part.args if full == "sqlalchemy.select" else [arg]:
                    if expr is not None:
                        for inner in (
                            ast.walk(expr)
                            if full == "sqlalchemy.select" or name(part.func) == "db.add_all"
                            else [expr]
                        ):
                            found |= entities(inner)
                if not found and op != "R":
                    facts.unresolved.add((func, part.lineno, "ORM書込先"))
                for table in found:
                    add("SQL", table, op, part, name(part.func))
            if full == "sqlalchemy.text" or name(part.func).endswith(".exec_driver_sql"):
                try:
                    if not isinstance(literal(arg), str):
                        raise ValueError()
                    for table, op in raw_sql(literal(arg)):
                        add("SQL", table, op, part, literal(arg))
                except ValueError, sqlglot.errors.SqlglotError:
                    facts.unresolved.add((func, part.lineno, "SQL文または対象表"))
            if isinstance(part.func, ast.Attribute):
                for svc in service(part.func.value):
                    action = part.func.attr
                    detail = action
                    if any(
                        k.arg == "InvocationType" and literal(k.value) == "DryRun" for k in part.keywords
                    ):
                        detail += " (DryRun)"
                    add("AWS", svc, aws_action(action), part, detail)
        return facts

    def trace(self, roots):
        result = Facts()
        todo = [(func, ()) for func in roots]
        seen = set()
        while todo:
            frame = todo.pop()
            func, bindings = frame
            if frame in seen or func not in self.functions:
                continue
            seen.add(frame)
            result.calls.add(func)
            facts = self.inspect(func, bindings)
            result.effects.update(facts.effects)
            result.status.update(facts.status)
            result.unresolved.update(facts.unresolved)
            todo.extend(facts.edges - seen)
        return result
