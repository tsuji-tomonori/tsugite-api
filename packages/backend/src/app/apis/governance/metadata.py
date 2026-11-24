import json
from typing import Annotated

from app.apis import outputs
from app.apis.catalog.common import DB, User
from app.apis.governance.directory import audit
from app.apis.governance.members import administrator
from app.apis.schemas import Input
from app.core.metadata import BUILTIN_FIELDS
from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from tsugite_db.models import DirectoryTree

router = APIRouter()


#: 利用者メタデータの項目設定
class MetadataSettings(Input):
    #: 画面に表示する項目名
    label: str = Field(min_length=1, max_length=120)
    #: 値の名称を全利用者に公開するか
    public_values: bool = False


#: メタデータ項目の表示名と選択肢の公開範囲を設定する
@router.put("/workspace/metadata/{key}", responses={200: {"model": outputs.MetadataField}})
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
