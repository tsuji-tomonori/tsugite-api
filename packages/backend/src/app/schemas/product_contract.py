"""OpenAPI shapes for product details serialized as flexible JSON, including older grants."""

from dataclasses import dataclass
from typing import Any, NotRequired, TypedDict, is_typeddict

from pydantic import BaseModel, TypeAdapter


#: 商品に表示する申請項目
class PublishedQuestion(TypedDict):
    #: 申請画面の質問名
    label: str
    #: 回答が必須か
    required: bool
    #: 申請で受理する回答の候補
    allowed_values: NotRequired[list[str]]


#: 公開中の環境別利用条件
class PublishedOffer(TypedDict, total=False):
    #: 申請者に表示する案内
    instructions: str
    #: 利用規約の本文
    terms: str
    #: 申請の承認経路
    route: str
    #: 承認担当の順序
    steps: list[str]
    #: 追加の申請項目
    fields: list[PublishedQuestion]
    #: 申請条件の版番号
    version: str


#: API仕様の公開版
class ReleaseEntry(TypedDict):
    #: 商品内の公開版番号
    number: int
    #: 仕様を公開した日時
    published_at: str
    #: 商品APIのバージョン
    api_version: str
    #: OpenAPI規格のバージョン
    openapi: str
    #: この公開版の変更説明
    note: str
    #: 追加した操作・構成要素
    added: list[str]
    #: 削除した操作・構成要素
    removed: list[str]
    #: 変更した操作・構成要素
    changed: list[str]


#: 承認段階ごとの審査記録
class ReviewStep(TypedDict):
    #: この段階の審査日時
    at: str
    #: この段階の承認担当
    stage: str
    #: 審査を行った利用者
    actor: str
    #: 審査の理由
    reason: str
    #: 段階の審査結果（承認・却下）
    action: str


#: 申請時点の利用条件と審査記録
class ApplicationEvidence(TypedDict, total=False):
    #: 申請の承認経路
    route: str
    #: 承認担当の順序
    steps: list[str]
    #: 段階ごとの審査結果
    decisions: list[ReviewStep]
    #: 申請時点の申請者の所属部署
    departments: list[str]
    #: 利用規約の本文
    terms: str
    #: 利用申請の受付日時
    submitted_at: str
    #: 利用規約に同意したか
    terms_accepted: bool
    #: 申請条件の版番号
    version: str
    #: 追加の申請項目に対する回答
    answers: dict[str, str]


@dataclass(frozen=True)
class PublishedShape:
    """Shape advertised for flexible JSON whose older stored records must still round-trip."""

    annotation: Any


def describe_product_fields(schemas: dict[str, Any]) -> None:
    """商品項目の公開形式をOpenAPIのスキーマに反映する。"""
    pending = [BaseModel]
    seen = set()
    while pending:
        model = pending.pop()
        if model in seen:
            continue
        seen.add(model)
        pending.extend(model.__subclasses__())
        if not model.__module__.startswith("app.") or model.__name__ not in schemas:
            continue
        properties = schemas[model.__name__].get("properties", {})
        for name, field in model.model_fields.items():
            key = field.serialization_alias or field.alias or name
            for marker in field.metadata:
                if not isinstance(marker, PublishedShape) or key not in properties:
                    continue
                shape = TypeAdapter(marker.annotation).json_schema(
                    ref_template="#/components/schemas/{model}"
                )
                schemas.update(shape.pop("$defs", {}))
                if is_typeddict(marker.annotation):
                    title = marker.annotation.__name__
                    schemas[title] = shape
                    shape = {"$ref": f"#/components/schemas/{title}"}
                properties[key].update(shape)
