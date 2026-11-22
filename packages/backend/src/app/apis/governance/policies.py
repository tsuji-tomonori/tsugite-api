import json
from typing import Literal

from app.apis.catalog.common import DB, User, event, record
from app.apis.schemas import Input
from app.core.workspace import policy, units
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

router = APIRouter()


class Policy(Input):
    visibility: Literal["all", "restricted"] = "all"
    projects: list[str] = Field(default_factory=list)
    departments: list[str] = Field(default_factory=list)
    auto_departments: list[str] = Field(default_factory=list)
    auto_titles: list[str] = Field(default_factory=list)
    delegates: list[str] = Field(default_factory=list)


@router.get("/apis/{key}/policy", responses={200: {"model": Policy}})
def read(key: str, actor: User, db: DB):
    asset = record(db, key)
    if asset.owner not in actor.owners:
        raise HTTPException(403)
    return Policy(**policy(asset))


@router.put("/apis/{key}/policy", responses={200: {"model": Policy}})
def configure(key: str, data: Policy, revision: int, request: Request, actor: User, db: DB):
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
