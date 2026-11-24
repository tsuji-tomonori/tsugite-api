import json

from app.apis.governance.directory import audit, federated_members, manages, roster
from app.apis.governance.keys import key_assets
from app.core.catalog import record
from app.core.credential_policy import (
    approved_assets,
    effective,
    minutes,
    operations,
    unit_bounds,
)
from app.core.workspace import ancestry, private_project, units
from app.dependencies import DB, User
from app.schemas import outputs
from app.schemas.credential_settings import Lifetime, LimitTarget, Permission
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from tsugite_db.models import Access, Asset, CredentialRule

router = APIRouter()


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


#: APIの利用者別操作権限を確認する
@router.get("/apis/{key}/operation-policy", responses={200: {"model": outputs.OperationPolicy}})
def get_operations(
    #: カタログ掲載APIの識別子
    key: str,
    db: DB,
    actor: User,
):
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


#: APIの利用者別操作権限を設定する
@router.put("/apis/{key}/operation-policy", responses={200: {"model": Permission}})
def set_operations(
    #: カタログ掲載APIの識別子
    key: str,
    data: Permission,
    request: Request,
    db: DB,
    actor: User,
):
    request.state.target_subject_id = data.subject
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


#: API・組織単位のトークン有効期間上限を確認する
@router.get("/credential-limits/{kind}/{key}", responses={200: {"model": outputs.Limit}})
def get_limit(
    #: 上限の設定対象（API・組織）
    kind: LimitTarget,
    #: 上限を設定するAPIまたは組織の識別子
    key: str,
    db: DB,
    actor: User,
):
    identity, cap = bound_resource(db, kind, key, actor)
    return {"inherited_minutes": cap, "max_minutes": minutes(db, identity)}


#: API・組織単位のトークン有効期間上限を設定する
@router.put("/credential-limits/{kind}/{key}", responses={200: {"model": outputs.Limit}})
def set_limit(
    #: 上限の設定対象（API・組織）
    kind: LimitTarget,
    #: 上限を設定するAPIまたは組織の識別子
    key: str,
    data: Lifetime,
    request: Request,
    db: DB,
    actor: User,
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


#: 認証情報の発行時に選べる対象と上限を取得する
@router.get("/credentials/options", responses={200: {"model": outputs.CredentialOptions}})
def options(
    #: 利用プロジェクトの識別子
    project: str,
    actor: User,
    db: DB,
):
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
