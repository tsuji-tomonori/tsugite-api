"""Common lifetime and operation decisions used by the portal and both invoke paths."""

import json
from time import time

from app.core.openapi import path_items
from app.core.workspace import ancestry, units
from fastapi import HTTPException
from sqlalchemy import select
from tsugite_db.models import Access, CredentialRule, PortalKey


def clock():
    return int(time())


def operations(asset):
    spec = json.loads(asset.spec)
    return sorted(
        f"{m.upper()} {p}"
        for p, item in path_items(spec)
        for m in item
        if m in ("get", "post", "put", "patch", "delete")
    )


def individual(db, key, subject):
    rule = db.get(CredentialRule, "person/" + key + "/" + subject)
    return json.loads(rule.ops) if rule and rule.ops is not None else None


def minutes(db, identity):
    row = db.get(CredentialRule, identity)
    return row.limit_minutes if row else None


def unit_bounds(db, project, departments=()):
    tree = units(db)
    return [
        {"name": tree.get(k, {}).get("name", k), "minutes": n}
        for k in sorted(ancestry(tree, {project, *departments}))
        if (n := minutes(db, "unit/" + k)) is not None
    ]


def approved_assets(db, project, subject):
    return set(
        db.scalars(
            select(Access.asset_id).where(
                Access.project == project,
                Access.status == "approved",
                (Access.subject.is_(None)) | (Access.subject == subject),
            )
        )
    )


def effective(db, project, departments, assets):
    bounds = unit_bounds(db, project, departments)
    caps = [minutes(db, "api/" + a) or 60 for a in assets]
    return min([60] + [r["minutes"] for r in bounds] + caps)


def check_operation(db, asset, actor, operation, project):
    limits = effective(db, project, actor.departments, [asset.id])
    key = db.get(PortalKey, actor.key_id) if actor.key_id else None
    if key and not key.mode:
        starts = [key.created or 0]
        if actor.issued:
            starts.append(actor.issued)
        if not starts[0] or clock() >= min(starts) + limits * 60:
            raise HTTPException(401, "APIキーの有効期限が切れました")
    elif actor.issued:
        if clock() >= actor.issued + limits * 60:
            raise HTTPException(401, "このAPIの有効期限を超えました")
    elif limits < 60:
        raise HTTPException(401, "このAPIには発行時刻を確認できるトークンが必要です")
    if key and key.mode:
        if actor.generation != key.revision:
            raise HTTPException(401, "認証情報が更新されました")
        config = json.loads(key.config)
        allowed = config["operations"].get(asset.id)
        if allowed is not None and operation not in allowed:
            raise HTTPException(403, "この認証情報では操作できません")
    if actor.machine and key and not key.mode:
        # A project member can issue a legacy shared key. It cannot replace a
        # named person on an API where the provider has set individual rules.
        if db.scalar(
            select(CredentialRule.id)
            .where(
                CredentialRule.id.startswith("person/" + asset.id + "/"), CredentialRule.ops.is_not(None)
            )
            .limit(1)
        ):
            raise HTTPException(403, "このAPIには本人の認証またはシステム認証が必要です")
    allowed = individual(db, asset.id, actor.subject)
    if allowed is not None and operation not in allowed:
        raise HTTPException(403, "この利用者には操作が許可されていません")
