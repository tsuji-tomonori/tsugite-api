import json
from typing import Literal

from app.apis.catalog.common import DB, User, record
from app.apis.governance.directory import audit, federated_members, manages, roster
from app.apis.governance.keys import key_assets
from app.apis.schemas import Input
from app.core.credential_policy import (
    approved_assets,
    effective,
    minutes,
    operations,
    unit_bounds,
)
from app.core.workspace import ancestry, private_project, units
from app.db.models import Access, Asset, CredentialRule
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from sqlalchemy import select

router = APIRouter()


class Lifetime(Input):
    max_minutes: int | None = Field(default=None, ge=1, le=60)


class Permission(Input):
    subject: str = Field(min_length=1, max_length=180)
    operations: list[str] | None


def members_for(db, projects, extra=()):
    people, known = roster(db)
    members = {}
    tree = units(db)
    for project in sorted(projects):
        for r in [
            *(row for row in known if row["unit_id"] == project),
            *federated_members(db, tree, project, known),
        ]:
            members[r["subject"]] = r["username"]
    for s in extra:
        members[s] = people.get(s, s)
    return [{"subject": s, "username": n} for s, n in sorted(members.items())]


def owner(db, asset_id, actor):
    asset = record(db, asset_id)
    if asset.owner not in actor.owners:
        raise HTTPException(403)
    return asset


def subscribers(db, asset):
    grants = list(
        db.scalars(
            select(Access).where(Access.asset_id == asset.id, Access.status.in_(["approved", "pending"]))
        )
    )
    return members_for(db, {g.project for g in grants}, [g.subject for g in grants if g.subject])


@router.get("/apis/{key}/operation-policy")
def get_operations(key: str, db: DB, actor: User):
    asset = owner(db, key, actor)
    prefix = "person/" + key + "/"
    configured = {
        r.id[len(prefix) :]: json.loads(r.ops)
        for r in db.scalars(
            select(CredentialRule).where(
                CredentialRule.id.startswith(prefix), CredentialRule.ops.is_not(None)
            )
        )
        if r.ops is not None
    }
    return {
        "operations": operations(asset),
        "members": subscribers(db, asset),
        "permissions": configured,
    }


@router.put("/apis/{key}/operation-policy")
def set_operations(key: str, data: Permission, request: Request, db: DB, actor: User):
    asset = owner(db, key, actor)
    if data.operations is not None and not set(data.operations) <= set(operations(asset)):
        raise HTTPException(422, "仕様に含まれる操作を指定してください")
    identity = "person/" + key + "/" + data.subject
    row = db.get(CredentialRule, identity)
    if not row:
        if data.subject not in {r["subject"] for r in subscribers(db, asset)}:
            raise HTTPException(422, "申請元の利用者を選んでください")
        row = CredentialRule(id=identity)
        db.add(row)
    row.ops = None if data.operations is None else json.dumps(sorted(set(data.operations)))
    audit(
        db, actor, request, "permission.save", asset.owner, key + " " + data.subject + " " + str(row.ops)
    )
    db.commit()
    return {"subject": data.subject, "operations": data.operations}


def bound_resource(db, kind, key, actor):
    if kind == "apis":
        owner(db, key, actor)
        return "api/" + key, 60
    tree = units(db)
    if not manages(actor, tree, key):
        raise HTTPException(403)
    above = ancestry(tree, [tree[key].get("parent")])
    children = {k for k in tree if tree[k]["kind"] == "project" and key in ancestry(tree, [k])}
    assets = db.scalars(
        select(Access.asset_id)
        .where(Access.project.in_(children), Access.status == "approved")
        .distinct()
    )
    cap = min(
        [60]
        + [minutes(db, "unit/" + p) or 60 for p in above]
        + [minutes(db, "api/" + a) or 60 for a in assets]
    )
    return "unit/" + key, cap


@router.get("/credential-limits/{kind}/{key}")
def get_limit(kind: Literal["units", "apis"], key: str, db: DB, actor: User):
    identity, cap = bound_resource(db, kind, key, actor)
    return {"inherited_minutes": cap, "max_minutes": minutes(db, identity)}


@router.put("/credential-limits/{kind}/{key}")
def set_limit(
    kind: Literal["units", "apis"], key: str, data: Lifetime, request: Request, db: DB, actor: User
):
    identity, cap = bound_resource(db, kind, key, actor)
    if data.max_minutes is not None and data.max_minutes > cap:
        raise HTTPException(422, f"上位の上限 {cap} 分を超えています")
    row = db.get(CredentialRule, identity)
    if not row:
        row = CredentialRule(id=identity)
        db.add(row)
    row.limit_minutes = data.max_minutes
    audit(db, actor, request, "lifetime.save", key, str(data.max_minutes))
    db.commit()
    return {"inherited_minutes": cap, "max_minutes": data.max_minutes}


@router.get("/credentials/options")
def options(project: str, actor: User, db: DB):
    if project not in actor.projects and project != private_project(actor.subject):
        raise HTTPException(403)
    assets = []
    for item in key_assets(actor, db):
        asset = db.get(Asset, item.id)
        if asset:
            assets.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "operations": operations(asset),
                    "max_minutes": effective(db, project, actor.departments, [item.id]),
                }
            )
    return {
        "assets": assets,
        "members": members_for(db, {project}, [actor.subject]),
        "limits": unit_bounds(db, project, actor.departments),
        "max_minutes": effective(
            db, project, actor.departments, approved_assets(db, project, actor.subject)
        ),
        "may_manage": manages(actor, units(db), project),
    }
