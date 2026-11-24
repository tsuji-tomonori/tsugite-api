"""部署・プロジェクトの廃止と移管。関連データと監査記録は同じトランザクションで確定する。"""

import json

from app.apis.governance.directory import audit, roster, save_tree
from app.apis.governance.members import administrator
from app.core.catalog import right_id
from app.core.workspace import ancestry, configured_projects, project_ids, retired_units, units
from app.dependencies import DB, User
from app.schemas import outputs
from app.schemas.unit_lifecycle import Transfer
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from tsugite_db.models import (
    Access,
    Affiliation,
    AlertRule,
    Asset,
    CredentialRule,
    DirectoryTree,
    PortalKey,
)

router = APIRouter()


def conflict(message):
    raise HTTPException(409, message)


def replace_ids(values, source, target):
    return list(dict.fromkeys(target if value == source else value for value in values))


def move_record(db, row, identity, **changes):
    if db.get(type(row), identity) is not None:
        conflict("移管先に同じ設定があります。重複を解消してください")
    # Aurora DSQLでは主キーをUPDATEできないため、同じトランザクションで置換する。
    values = {col.key: getattr(row, col.key) for col in row.__table__.columns}
    values.update(changes)
    db.add(type(row)(**values))
    db.delete(row)


def require_destination(target, dependency):
    if not target:
        conflict(dependency + "があります。移管先を選択してください")


def asset_references(db, source, target):
    for asset in db.scalars(select(Asset).where(Asset.removed_at.is_(None))):
        if asset.owner == source:
            require_destination(target, "提供中または下書きのAPI")
            asset.owner = target
        policy = json.loads(asset.policy or "{}")
        for field in ("projects", "departments", "auto_departments", "delegates"):
            if source in policy.get(field, []):
                require_destination(target, "APIの公開・承認条件")
                policy[field] = replace_ids(policy[field], source, target)
                asset.policy = json.dumps(policy, ensure_ascii=False)
        offers = json.loads(asset.offers or "{}")
        for offer in offers.values():
            if "unit/" + source in offer.get("steps", []):
                require_destination(target, "承認経路")
                offer["steps"] = [
                    "unit/" + target if step == "unit/" + source else step for step in offer["steps"]
                ]
                asset.offers = json.dumps(offers, ensure_ascii=False)


def pending_steps(db, source, target):
    for grant in db.scalars(select(Access).where(Access.status == "pending")):
        form = grant.application
        if source in form.get("departments", []) or "unit/" + source in form.get("steps", []):
            require_destination(target, "承認待ちの申請")
            form["departments"] = replace_ids(form.get("departments", []), source, target)
            form["steps"] = [
                "unit/" + target if step == "unit/" + source else step for step in form.get("steps", [])
            ]
            grant.submission = json.dumps(form, ensure_ascii=False)
            if grant.stage == "unit/" + source:
                grant.stage = "unit/" + target


def migrate_references(db, source, target):
    asset_references(db, source, target)
    pending_steps(db, source, target)
    for grant in db.scalars(select(Access).where(Access.project == source)):
        if grant.status not in ("pending", "approved"):
            continue
        require_destination(target, "利用申請・利用権")
        key = right_id(grant.asset_id, target, grant.environment, grant.subject or "")
        move_record(db, grant, key, id=key, project=target)
    for rule in db.scalars(
        select(AlertRule).where(AlertRule.project == source, AlertRule.enabled.is_(True))
    ):
        require_destination(target, "監視設定")
        key = right_id(rule.asset_id, target, rule.environment)
        move_record(db, rule, key, id=key, project=target)
    for key in db.scalars(
        select(PortalKey).where(PortalKey.project == source, PortalKey.revoked.is_(False))
    ):
        require_destination(target, "発行済みの認証情報")
        key.project = target
    limit = db.get(CredentialRule, "unit/" + source)
    if limit:
        require_destination(target, "組織のトークン上限設定")
        key = "unit/" + target
        move_record(db, limit, key, id=key)
    if not target:
        if any(r["unit_id"] == source for r in roster(db)[1]):
            conflict("所属者がいます。所属を解除するか移管先を選択してください")
        return
    for row in db.scalars(select(Affiliation).where(Affiliation.unit_id == source)):
        move_record(db, row, (row.subject, target), unit_id=target)


def retire(key, target, request, actor, db):
    administrator(actor)
    tree = units(db)
    retired = retired_units(db).copy()
    if key not in tree:
        if key in retired and retired[key] == target:
            return {"removed": True}
        raise HTTPException(404, "対象の組織が見つかりません")
    if target:
        if target not in tree or tree[target]["kind"] != tree[key]["kind"]:
            raise HTTPException(422, "同じ種類の移管先を選んでください")
        if key in ancestry(tree, [target]):
            raise HTTPException(422, "自分自身や配下の部署へ移管できません")
        if any(tree[k]["stopped"] for k in ancestry(tree, [key, target])):
            conflict("利用停止中の組織は移管できません")
    elif key in project_ids(db, configured_projects()):
        conflict("接続設定のあるプロジェクトです。移管先を選択してください")
    for child in tree.values():
        if child["parent"] == key:
            require_destination(target, "配下の部署・プロジェクト")
            child["parent"] = target
    migrate_references(db, key, target)
    entry = tree.pop(key)
    # 移管の連鎖は常に最終移管先を指す。削除した識別子は再発行しない。
    retired = {k: target if v == key else v for k, v in retired.items()}
    retired[key] = target
    row = db.get(DirectoryTree, "retired")
    if not row:
        row = DirectoryTree(id="retired")
        db.add(row)
    row.units = json.dumps(retired)
    audit(
        db,
        actor,
        request,
        "unit.transfer" if target else "unit.delete",
        key,
        json.dumps({"name": entry["name"], "destination": target}, ensure_ascii=False),
    )
    save_tree(db, tree)
    db.info["retired_units"] = retired
    return {"removed": True}


#: 未使用の部署・プロジェクトを削除する
@router.delete("/workspace/units/{key}", responses={200: {"model": outputs.Removed}})
def delete_unit(
    #: 削除する組織の識別子
    key: str,
    request: Request,
    actor: User,
    db: DB,
):
    return retire(key, "", request, actor, db)


#: 関連する所属と利用設定を既存の組織へ移管し、移管元を廃止する
@router.post("/workspace/units/{key}/transfer", responses={200: {"model": outputs.Removed}})
def transfer_unit(
    #: 移管元の組織の識別子
    key: str,
    data: Transfer,
    request: Request,
    actor: User,
    db: DB,
):
    if not data.destination:
        raise HTTPException(422, "移管先を指定してください")
    return retire(key, data.destination, request, actor, db)
