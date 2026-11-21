import json

from app.apis.catalog.common import DB, User, allowed_spec, event, listing
from app.apis.schemas import Listing, Register
from app.core.config import targets
from app.db.models import Asset, new_id
from fastapi import APIRouter, HTTPException, Request
from openapi_spec_validator import validate

router = APIRouter()


@router.post("/apis", response_model=Listing, status_code=201, operation_id="register")
def register(data: Register, request: Request, actor: User, db: DB):
    if data.owner not in actor.owners:
        raise HTTPException(403, "提供プロジェクトの権限が必要です")
    bindings = targets()
    for env, key in data.targets.items():
        target = bindings.get(key)
        if not target or target.owner != data.owner or target.environment != env:
            raise HTTPException(422, "プロジェクトと環境に対応する接続先を選んでください")
    spec = json.dumps(data.spec, ensure_ascii=False)
    if len(spec.encode()) > 500_000 or not allowed_spec(data.spec) or not data.spec.get("paths"):
        raise HTTPException(422, "外部参照を含まない500KB以内のOpenAPI JSONを指定してください")
    if not str(data.spec.get("openapi", "")).startswith(("3.0.", "3.1.")):
        raise HTTPException(422, "OpenAPI 3.0または3.1を指定してください")
    try:
        validate(data.spec)
    except Exception as exc:
        raise HTTPException(422, "OpenAPIの形式または内部参照を確認してください") from exc
    row = Asset(
        id=new_id(),
        name=data.name,
        summary=data.summary,
        owner=data.owner,
        base_path=data.base_path,
        targets=json.dumps(data.targets),
        spec=spec,
        published=False,
    )
    db.add(row)
    event(db, request, actor, row, "register", row.owner)
    db.commit()
    return listing(row)
