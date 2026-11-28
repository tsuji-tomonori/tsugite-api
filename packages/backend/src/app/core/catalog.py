# 商品情報の取得とカタログ操作を共通化する。
import json

from app.core.diagnostics import asset_object
from app.schemas.catalog import Listing
from fastapi import HTTPException
from sqlalchemy.orm import Session
from tsugite_db.models import Asset, Event


def event(db, request, actor, asset, action, project="", environment="", detail=""):
    request.state.diagnostics = {"asset_id": asset.id}
    db.add(
        Event(
            actor=actor.subject,
            asset_id=asset.id,
            owner=asset.owner,
            project=project,
            environment=environment,
            action=action,
            detail=detail,
            request_id=request.state.request_id,
        )
    )


def record(db: Session, key: str) -> Asset:
    row = db.get(Asset, key)
    if row is None or row.removed_at is not None:
        raise HTTPException(404, "APIが見つかりません")
    return row


def listing(row: Asset) -> Listing:
    return Listing(
        id=row.id,
        slug=row.route.slug if row.route else None,
        owner=row.owner,
        responsible=row.responsible,
        publication_stage=json.loads(row.publication_request)["remaining"][0]
        if row.publication_request
        else None,
        name=row.name,
        summary=row.summary,
        environments=list(asset_object(row, "targets")),
        published=row.published,
        revision=row.revision,
    )


def right_id(asset_id: str, project: str, environment: str, subject: str = "") -> str:
    from hashlib import sha256

    base = f"{asset_id}/{project}/{environment}"
    return base + "/" + sha256(subject.encode()).hexdigest()[:32] if subject else base


def allowed_spec(node):
    if isinstance(node, dict):
        return all(
            (
                key not in {"$ref", "$dynamicRef", "$recursiveRef"}
                or isinstance(v, str)
                and v.startswith("#/")
            )
            and key not in {"$id", "$dynamicAnchor"}
            and allowed_spec(v)
            for key, v in node.items()
        )
    return not isinstance(node, list) or all(allowed_spec(v) for v in node)


NEXT = {
    "approve": ("pending", "approved"),
    "reject": ("pending", "rejected"),
    "withdraw": ("pending", "withdrawn"),
    "revoke": ("approved", "revoked"),
}
