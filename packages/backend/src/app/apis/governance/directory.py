import json
from typing import Literal

from app.apis import outputs
from app.apis.catalog.common import DB, User
from app.apis.governance.members import administrator, projects
from app.apis.schemas import Input
from app.core.auth import DEMO_GROUPS
from app.core.config import local_demo, settings
from app.core.workspace import ancestry, units
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from sqlalchemy import func, select
from tsugite_db.models import AccessLog, Affiliation, Asset, DirectoryTree, Event, LogUnit, Member

router = APIRouter()


#: 部署・プロジェクトの編集内容
class UnitData(Input):
    #: 組織の種類（部署・プロジェクト）
    kind: Literal[
        #: プロジェクト
        "project",
        #: 部署
        "department",
    ]
    #: 部署・プロジェクト名
    name: str = Field(min_length=1, max_length=120)
    #: 親部署の識別子
    parent: str = ""


#: 組織への所属設定
class Membership(Input):
    #: 対象利用者の識別子
    subject: str = Field(min_length=1, max_length=180)
    #: 部署・プロジェクトの識別子
    unit_id: str
    #: 所属先の管理者か
    leader: bool = False
    #: 役職名
    title: str = Field("", max_length=120)


#: 組織の利用停止設定
class State(Input):
    #: 組織の利用を停止中か
    stopped: bool


def audit(db, actor, request, action, unit, detail):
    db.add(
        Event(
            actor=actor.subject,
            owner="",
            asset_id="",
            environment="",
            project=unit,
            action=action,
            detail=detail,
            request_id=request.state.request_id,
        )
    )


def roster(db):
    members = {
        m.subject: m.username for m in db.scalars(select(Member).where(Member.deleted.is_(False)))
    }
    affiliations = {
        (a.subject, a.unit_id): dict(
            subject=a.subject, unit_id=a.unit_id, leader=a.leader, title=a.title, active=a.active
        )
        for a in db.scalars(select(Affiliation))
    }
    legacy = [
        (m.subject, m.project)
        for m in db.scalars(select(Member).where(Member.deleted.is_(False)))
        if m.project
    ]
    if local_demo():
        for who, groups in DEMO_GROUPS.items():
            m = db.get(Member, who)
            if m and m.deleted:
                continue
            members.setdefault(who, who)
            legacy.extend((who, g[4:]) for g in groups if g.startswith(("use-", "own-")))
    for who, unit in legacy:
        affiliations.setdefault(
            (who, unit), dict(subject=who, unit_id=unit, title="", leader=False, active=True)
        )
    rows = []
    for data in affiliations.values():
        if data["active"]:
            m = db.get(Member, data["subject"])
            if m and m.deleted:
                continue
            members.setdefault(data["subject"], data["subject"])
            rows.append({**data, "username": members[data["subject"]]})
    return members, rows


def manages(actor, tree, key):
    return key in tree and (actor.admin or bool(actor.leads & ancestry(tree, [key])))


#: 組織の構成と利用者の所属を確認する
@router.get("/workspace", responses={200: {"model": outputs.Workspace}})
def workspace(actor: User, db: DB):
    tree = units(db)
    people, rows = roster(db)
    own = [r for r in rows if r["subject"] == actor.subject]
    visible = [r for r in rows if r["subject"] == actor.subject or manages(actor, tree, r["unit_id"])]
    people_ids = set(people) if actor.admin else {r["subject"] for r in visible}
    return {
        "admin": actor.admin,
        "units": list(tree.values()),
        "leads": sorted(k for k in tree if manages(actor, tree, k)),
        "my_units": sorted(set(actor.projects) | {r["unit_id"] for r in own}),
        "memberships": visible,
        "users": [{"subject": i, "username": people[i]} for i in sorted(people_ids)],
        "titles": sorted({r["title"] for r in visible if r["title"]}),
    }


def save_tree(db, tree):
    row = db.info["workspace_tree"]
    if not row:
        row = DirectoryTree(id="tree")
        db.add(row)
    row.units = json.dumps(tree, ensure_ascii=False)
    db.commit()


#: 部署・プロジェクトを登録または更新する
@router.put("/workspace/units/{key}", responses={200: {"model": outputs.Unit}})
def unit(
    #: 部署・プロジェクトの識別子
    key: str,
    data: UnitData,
    request: Request,
    actor: User,
    db: DB,
):
    import re

    administrator(actor)
    tree = units(db)
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", key) or key.startswith("person-"):
        raise HTTPException(422, "識別子を確認してください")
    if data.parent and (
        tree.get(data.parent, {}).get("kind") != "department" or key in ancestry(tree, [data.parent])
    ):
        raise HTTPException(422, "親部署が存在しないか、循環する配置です")
    if key in tree and tree[key]["kind"] != data.kind:
        raise HTTPException(409, "種類の変更はできません")
    tree[key] = {"id": key, **data.model_dump(), "stopped": tree.get(key, {}).get("stopped", False)}
    audit(db, actor, request, "unit.save", key, data.name)
    save_tree(db, tree)
    return tree[key]


#: 利用者の所属・役職・管理権限を設定する
@router.put("/workspace/memberships", responses={200: {"model": Membership}})
def assign(data: Membership, request: Request, actor: User, db: DB):
    request.state.target_subject_id = data.subject
    administrator(actor)
    if data.unit_id not in units(db):
        raise HTTPException(404)
    member = db.get(Member, data.subject)
    if member and member.deleted:
        raise HTTPException(409, "削除済みのユーザーです")
    row = db.get(Affiliation, (data.subject, data.unit_id))
    if not row:
        row = Affiliation(subject=data.subject, unit_id=data.unit_id)
        db.add(row)
    row.leader, row.title, row.active = data.leader, data.title, True
    audit(db, actor, request, "affiliation.save", data.unit_id, data.subject)
    db.commit()
    return data


#: 利用者の所属を解除する
@router.delete("/workspace/memberships", responses={200: {"model": outputs.Removed}})
def unassign(
    #: 対象利用者の識別子
    subject: str,
    #: 所属先の部署・プロジェクト識別子
    unit_id: str,
    request: Request,
    actor: User,
    db: DB,
):
    administrator(actor)
    if unit_id not in units(db):
        raise HTTPException(404)
    row = db.get(Affiliation, (subject, unit_id))
    if not row:
        row = Affiliation(subject=subject, unit_id=unit_id, title="", leader=False)
        db.add(row)
    row.active = False
    audit(db, actor, request, "affiliation.remove", unit_id, subject)
    db.commit()
    return {"removed": True}


#: 部署・プロジェクトの利用を停止または再開する
@router.put("/workspace/units/{key}/state", responses={200: {"model": outputs.Unit}})
def change_state(
    #: 部署・プロジェクトの識別子
    key: str,
    data: State,
    request: Request,
    actor: User,
    db: DB,
):
    tree = units(db)
    if not manages(actor, tree, key):
        raise HTTPException(403)
    tree[key]["stopped"] = data.stopped
    audit(db, actor, request, "unit.stop" if data.stopped else "unit.resume", key, tree[key]["name"])
    save_tree(db, tree)
    return tree[key]


def federated_members(db, tree, key, known):
    pool = settings().get("pool_id")
    if local_demo() or not pool:
        return []
    import boto3

    client = boto3.client("cognito-idp")
    seen = {(r["subject"], r["unit_id"]) for r in known}
    added = []
    for project in projects():
        if key not in ancestry(tree, [project]):
            continue
        for prefix in ("use-", "own-"):
            cursor = {}
            while True:
                try:
                    #: 利用者・グループの管理（Cognitoユーザープール） / グループの利用者を一覧
                    page = client.list_users_in_group(
                        UserPoolId=pool, GroupName=prefix + project, **cursor
                    )
                except client.exceptions.ResourceNotFoundException:
                    break
                for user in page.get("Users", []):
                    sub = next((a["Value"] for a in user["Attributes"] if a["Name"] == "sub"), None)
                    if not sub or (sub, project) in seen or db.get(Affiliation, (sub, project)):
                        continue
                    member = db.get(Member, sub)
                    if member and member.deleted:
                        continue
                    seen.add((sub, project))
                    added.append(
                        dict(
                            subject=sub,
                            username=user["Username"],
                            unit_id=project,
                            title="",
                            leader=False,
                        )
                    )
                if not page.get("NextToken"):
                    break
                cursor = {"NextToken": page["NextToken"]}
    return added


def unit_condition(tree, key):
    return (
        AccessLog.project == key
        if tree[key]["kind"] == "project"
        else AccessLog.request_id.in_(select(LogUnit.request_id).where(LogUnit.unit_id == key))
    )


#: 部署・プロジェクトの所属者とAPI利用実績を取得する
@router.get("/workspace/units/{key}/usage", responses={200: {"model": outputs.Usage}})
def usage(
    #: 部署・プロジェクトの識別子
    key: str,
    actor: User,
    db: DB,
):
    tree = units(db)
    if not manages(actor, tree, key):
        raise HTTPException(403)
    _, members = roster(db)
    scoped = [m for m in members if key in ancestry(tree, [m["unit_id"]])]
    scoped.extend(federated_members(db, tree, key, scoped))
    condition = unit_condition(tree, key)
    base = select(func.count(AccessLog.request_id)).where(condition)

    def grouped(col):
        return db.execute(select(col, func.count()).where(condition).group_by(col)).all()

    return {
        "unit_id": key,
        "members": scoped,
        "calls": db.scalar(base),
        "errors": db.scalar(base.where(AccessLog.status >= 400)),
        "by_project": [{"project": p, "calls": n} for p, n in grouped(AccessLog.project)],
        "by_api": [
            {"asset_id": a, "name": asset.name if (asset := db.get(Asset, a)) else a, "calls": n}
            for a, n in grouped(AccessLog.asset_id)
        ],
    }
