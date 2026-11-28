# 管理者が属性の種類を登録・編集するAPIを提供する。
import json
from typing import Annotated

from app.apis.governance.directory import audit
from app.apis.governance.members import administrator
from app.core.metadata import BUILTIN_FIELDS
from app.dependencies import DB, User
from app.schemas import outputs
from app.schemas.errors import domain_errors
from app.schemas.metadata import MetadataSettings
from fastapi import APIRouter, HTTPException, Path, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from tsugite_db.models import DirectoryTree

router = APIRouter()


#: メタデータ項目の表示名と選択肢の公開範囲を設定する
@router.put(
    "/workspace/metadata/{key}",
    responses={**domain_errors(403, 409), 200: {"model": outputs.MetadataField}},
)
def save_field(
    #: メタデータ項目の識別子
    key: Annotated[str, Path(pattern=r"^[a-z][a-z0-9-]{0,62}$")],
    data: MetadataSettings,
    request: Request,
    actor: User,
    db: DB,
):
    administrator(actor)
    if key in BUILTIN_FIELDS:
        raise HTTPException(409, "業務で使用中のデータパーツです")
    row = db.get(DirectoryTree, "metadata")
    if row is None:
        row = DirectoryTree(id="metadata", units="{}")
        db.add(row)
    fields = json.loads(row.units)
    fields[key] = {"key": key, **data.model_dump(), "builtin": False}
    row.units = json.dumps(fields, ensure_ascii=False)
    audit(db, actor, request, "metadata.save", "", key)
    try:
        db.commit()
    except (IntegrityError, StaleDataError) as exc:
        db.rollback()
        raise HTTPException(409, "項目設定が変更されました。再読み込みしてください") from exc
    return fields[key]
