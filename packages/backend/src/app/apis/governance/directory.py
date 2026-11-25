# 部署やプロジェクトの情報を提供する。
import json

from app.apis.governance.members import administrator, projects
from app.apis.governance.profiles import check_managed_identity
from app.core.auth import DEMO_GROUPS
from app.core.config import local_demo, settings
from app.core.member_profiles import directory_accounts, directory_fields, directory_profiles
from app.core.metadata import BUILTIN_FIELDS, metadata_fields, parent_kind
from app.core.workspace import ancestry, retired_units, units
from app.dependencies import DB, User
from app.schemas import outputs
from app.schemas.directory import Membership, State, UnitData
from app.schemas.errors import domain_errors
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select
from tsugite_db.models import AccessLog, Affiliation, Asset, DirectoryTree, Event, LogUnit, Member

router = APIRouter()


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
    retired = retired_units(db)
    for who, unit in legacy:
        unit = retired.get(unit, unit)
        if not unit:
            continue
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
    return (
        key in tree
        and tree[key]["kind"] in BUILTIN_FIELDS
        and (actor.admin or bool(actor.leads & ancestry(tree, [key])))
    )


#: 組織の構成と利用者の所属を確認する
@router.get("/workspace", responses={200: {"model": outputs.Workspace}})
def workspace(actor: User, db: DB):
    tree = units(db)
    people, rows = roster(db)
    managed = (
        set(tree)
        if actor.admin
        else {key for key in tree if actor.metadata_leads & ancestry(tree, [key])}
    )
    fields_by_key = metadata_fields(db)
    own_units = set(actor.projects).union(*actor.metadata.values())
    public = {key for key, unit in tree.items() if fields_by_key[unit["kind"]]["public_values"]}
    visible_values = ancestry(tree, own_units | managed | public)
    visible_units = [unit for key, unit in tree.items() if key in visible_values]
    visible = [
        r
        for r in rows
        if r["unit_id"] in managed or (r["subject"] == actor.subject and r["unit_id"] in own_units)
    ]
    people_ids = set(people) if actor.admin else {r["subject"] for r in visible}
    profiles = directory_profiles(db, people_ids)
    accounts = directory_accounts(db, people_ids)
    fields = {
        subject: directory_fields(profiles.get(subject), accounts.get(subject)) for subject in people_ids
    }
    return {
        "admin": actor.admin,
        "metadata_fields": list(fields_by_key.values()),
        "units": visible_units,
        "leads": sorted(key for key in managed if tree[key]["kind"] in BUILTIN_FIELDS),
        "my_units": sorted(own_units),
        "memberships": [{**row, **fields[row["subject"]]} for row in visible],
        "users": [{"subject": i, "username": people[i], **fields[i]} for i in sorted(people_ids)],
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
@router.put(
    "/workspace/units/{key}", responses={**domain_errors(403, 409), 200: {"model": outputs.Unit}}
)
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
    if key in retired_units(db):
        raise HTTPException(409, "廃止した識別子は再使用できません")
    if data.kind not in metadata_fields(db):
        raise HTTPException(422, "登録済みのメタデータ項目を選択してください")
    if data.parent and (
        tree.get(data.parent, {}).get("kind") != parent_kind(data.kind)
        or key in ancestry(tree, [data.parent])
    ):
        raise HTTPException(422, "親の種類が一致しないか、循環する配置です")
    if key in tree and tree[key]["kind"] != data.kind:
        raise HTTPException(409, "種類の変更はできません")
    tree[key] = {"id": key, **data.model_dump(), "stopped": tree.get(key, {}).get("stopped", False)}
    audit(db, actor, request, "unit.save", key, data.name)
    save_tree(db, tree)
    return tree[key]


#: 利用者の所属・役職・管理権限を設定する
@router.put(
    "/workspace/memberships", responses={**domain_errors(403, 404, 409), 200: {"model": Membership}}
)
def assign(data: Membership, request: Request, actor: User, db: DB):
    request.state.target_subject_id = data.subject
    administrator(actor)
    if data.unit_id not in units(db):
        raise HTTPException(404)
    member = db.get(Member, data.subject)
    if member and member.deleted:
        raise HTTPException(409, "削除済みのユーザーです")
    check_managed_identity(data.subject, member)
    row = db.get(Affiliation, (data.subject, data.unit_id))
    if not row:
        row = Affiliation(subject=data.subject, unit_id=data.unit_id)
        db.add(row)
    row.leader, row.title, row.active = data.leader, data.title, True
    audit(db, actor, request, "affiliation.save", data.unit_id, data.subject)
    db.commit()
    return data


#: 利用者の所属を解除する
@router.delete(
    "/workspace/memberships", responses={**domain_errors(404), 200: {"model": outputs.Removed}}
)
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
@router.put(
    "/workspace/units/{key}/state", responses={**domain_errors(403), 200: {"model": outputs.Unit}}
)
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
    retired = retired_units(db)
    for group_project in projects():
        project = retired.get(group_project, group_project)
        if not project:
            continue
        if key not in ancestry(tree, [project]):
            continue
        for prefix in ("use-", "own-"):
            cursor = {}
            while True:
                try:
                    #: 利用者・グループの管理（Cognitoユーザープール） / グループの利用者を一覧
                    page = client.list_users_in_group(
                        UserPoolId=pool, GroupName=prefix + group_project, **cursor
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
@router.get(
    "/workspace/units/{key}/usage", responses={**domain_errors(403), 200: {"model": outputs.Usage}}
)
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
    subjects = {row["subject"] for row in scoped}
    profiles = directory_profiles(db, subjects)
    accounts = directory_accounts(db, subjects)
    for row in scoped:
        row.update(directory_fields(profiles.get(row["subject"]), accounts.get(row["subject"])))
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
