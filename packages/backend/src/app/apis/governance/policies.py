import json
from typing import Literal

from app.apis.catalog.common import DB, User, event, record
from app.apis.schemas import Input
from app.core.metadata import BUILTIN_FIELDS, metadata_fields
from app.core.workspace import policy, units
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

router = APIRouter()


#: APIの公開範囲と承認条件
class Policy(Input):
    #: APIの公開範囲
    visibility: Literal[
        #: 全体公開
        "all",
        #: 限定公開
        "restricted",
    ] = "all"
    #: 閲覧を許可するプロジェクト
    projects: list[str] = Field(default_factory=list)
    #: 閲覧を許可する部署
    departments: list[str] = Field(default_factory=list)
    #: 閲覧を許可する任意メタデータの値
    metadata_values: list[str] = Field(default_factory=list)
    #: 自動承認の対象部署
    auto_departments: list[str] = Field(default_factory=list)
    #: 自動承認の対象役職
    auto_titles: list[str] = Field(default_factory=list)
    #: 承認を委任する部署
    delegates: list[str] = Field(default_factory=list)


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
    previous = policy(asset).get("metadata_values", [])
    if "metadata_values" not in data.model_fields_set:
        data.metadata_values = previous
    else:
        fields = metadata_fields(db)
        for key in set(data.metadata_values) - set(previous):
            kind = tree.get(key, {}).get("kind")
            if kind not in fields or kind in BUILTIN_FIELDS or not fields[kind]["public_values"]:
                raise HTTPException(422, "全利用者に公開しているメタデータの値を選択してください")
    if any(not t.strip() or len(t) > 120 for t in data.auto_titles):
        raise HTTPException(422, "役職名を確認してください")
    encoded = json.dumps(data.model_dump(), ensure_ascii=False)
    asset.policy = encoded
    event(db, request, actor, asset, "policy.update", asset.owner, detail=encoded)
    db.commit()
    return data
