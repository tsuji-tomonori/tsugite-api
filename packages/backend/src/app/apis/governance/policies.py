# アクセスポリシーを管理する。
import json

from app.core.catalog import event, record
from app.core.workspace import policy, units
from app.dependencies import DB, User
from app.schemas.policies import Policy
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


#: APIの公開範囲と申請の承認条件を確認する
@router.get("/apis/{key}/policy", responses={200: {"model": Policy}})
def read(
    #: カタログ掲載APIの識別子
    key: str,
    actor: User,
    db: DB,
):
    asset = record(db, key)
    if asset.owner not in actor.owners:
        raise HTTPException(403)
    return Policy(**policy(asset))


#: APIの公開範囲と申請の承認条件を設定する
@router.put("/apis/{key}/policy", responses={200: {"model": Policy}})
def configure(
    #: カタログ掲載APIの識別子
    key: str,
    data: Policy,
    #: 変更前の版番号
    revision: int,
    request: Request,
    actor: User,
    db: DB,
):
    asset = record(db, key)
    if asset.owner not in actor.owners:
        raise HTTPException(403)
    if revision != asset.revision:
        raise HTTPException(409, "掲載条件が変更されています")
    tree = units(db)
    for kind, ids in (
        ("project", data.projects),
        ("department", data.departments + data.auto_departments + data.delegates),
    ):
        if any(tree.get(i, {}).get("kind") != kind for i in ids):
            raise HTTPException(422, "所属先を確認してください")
    if any(not t.strip() or len(t) > 120 for t in data.auto_titles):
        raise HTTPException(422, "役職名を確認してください")
    encoded = json.dumps(data.model_dump(), ensure_ascii=False)
    asset.policy = encoded
    event(db, request, actor, asset, "policy.update", asset.owner, detail=encoded)
    db.commit()
    return data
