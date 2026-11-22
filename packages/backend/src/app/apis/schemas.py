from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Env = Literal[
    #: 検証環境
    "sandbox",
    #: 準本番環境
    "staging",
    #: 本番環境
    "production",
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


FieldLabel = Annotated[str, Field(min_length=1, max_length=100)]
Answer = Annotated[str, Field(min_length=1, max_length=500)]
Route = Literal[
    #: 従来方式
    "legacy",
    #: 自動承認
    "auto",
    #: 提供者
    "provider",
    #: 部署
    "department",
    #: 部署承認後に提供者が承認
    "department_provider",
    #: 個別指定の承認経路
    "custom",
]


#: 利用申請の追加質問
class ApplicationField(Input):
    #: 申請画面の質問名
    label: FieldLabel
    #: 回答が必須か
    required: bool = True
    #: 申請で受理する回答の候補
    allowed_values: list[Answer] = Field(default_factory=list, max_length=100)


#: 環境別の利用条件・承認設定
class Offer(Input):
    #: 申請者に表示する案内
    instructions: str = Field("", max_length=4000)
    #: 利用規約の本文
    terms: str = Field("", max_length=8000)
    #: 申請の承認経路
    route: Route = "provider"
    #: 承認担当の順序
    steps: list[Annotated[str, Field(pattern=r"^(provider|department|unit/[a-z][a-z0-9-]{0,62})$")]] = (
        Field(default_factory=list[str], max_length=12)
    )
    #: 追加の申請項目
    fields: list[ApplicationField] = Field(default_factory=list[ApplicationField], max_length=20)

    @model_validator(mode="after")
    def unique_labels(self) -> Self:
        if (self.route == "custom") != bool(self.steps):
            raise ValueError("カスタム承認には承認者を1段階以上設定してください")
        if len({f.label for f in self.fields}) != len(self.fields):
            raise ValueError("申請項目の名前が重複しています")
        return self


#: APIのカタログ登録内容
class Register(Input):
    #: 提供プロジェクトの識別子
    owner: str = Field(min_length=1, max_length=63)
    #: API名
    name: str = Field(min_length=1, max_length=120)
    #: APIの用途・概要
    summary: str = Field(min_length=1, max_length=1000)
    #: 環境別の接続先
    targets: dict[Env, str] = Field(min_length=1, max_length=3)
    #: 接続先APIの基底パス
    base_path: str = Field("", pattern=r"^(?:/[A-Za-z0-9_-]+)*$", max_length=300)
    #: 提供者が登録したOpenAPI仕様
    spec: dict[str, Any]
    #: 提供環境ごとの利用条件
    offers: dict[Env, Offer] | None = None
    #: 公開版の変更説明
    release_note: str = Field("", max_length=2000)


#: カタログ掲載APIの概要
class Listing(BaseModel):
    #: カタログ掲載APIの識別子
    id: str
    #: API名
    name: str
    #: 提供プロジェクトの識別子
    owner: str
    #: APIの用途・概要
    summary: str
    #: 利用できる提供環境
    environments: list[Env]
    #: カタログで公開中か
    published: bool
    #: 更新時の競合検出に使う版番号
    revision: int


#: APIカタログの検索結果ページ
class CatalogPage(BaseModel):
    #: このページの掲載API
    items: list[Listing]
    #: ページ番号
    page: int
    #: 1ページの表示件数
    page_size: int
    #: 検索結果の総件数
    total: int


#: カタログ掲載APIの詳細
class Detail(Listing):
    #: 提供環境ごとの利用条件
    offers: dict[str, Any] = Field(default_factory=dict)
    #: API仕様の公開履歴
    releases: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])
    #: 公開版の変更説明
    release_note: str = ""
    #: 許可されたAPI操作
    allowed_operations: list[str] | None = None
    #: 接続先APIの基底パス
    base_path: str = ""
    #: 環境別の接続先設定
    bindings: dict[str, str] = Field(default_factory=dict)
    #: 提供者が登録したOpenAPI仕様
    spec: dict[str, Any]


#: API利用申請の入力
class Apply(Input):
    #: 利用規約に同意したか
    terms_accepted: bool = False
    #: 申請者が確認した利用条件の版
    offer_version: str = ""
    #: 追加の申請項目に対する回答
    answers: dict[FieldLabel, Answer] = Field(default_factory=dict, max_length=20)
    #: 個人として申請するか
    personal: bool = False
    #: 利用を申請するプロジェクトの識別子
    project: str = Field(pattern=r"^[a-z][a-z0-9-]{0,62}$")
    #: 提供環境
    environment: Env
    #: 利用申請の理由
    reason: str = Field(min_length=1, max_length=1000)


#: 利用申請への処理指示
class Decision(Input):
    #: 申請への処理（承認・却下・取り下げ・取消）
    action: Literal[
        #: 承認
        "approve",
        #: 却下
        "reject",
        #: 取消
        "revoke",
        #: 取り下げ
        "withdraw",
    ]
    #: 更新時の競合検出に使う版番号
    revision: int = Field(ge=1)
    #: 審査・取り下げ・取消の理由
    reason: str = Field(min_length=1, max_length=1000)


#: API利用申請と審査状態
class Right(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    #: 利用申請・利用権の識別子
    id: str
    #: カタログ掲載APIの識別子
    asset_id: str
    #: 利用プロジェクトの識別子
    project: str
    #: 提供環境
    environment: Env
    #: 利用申請の理由
    reason: str
    #: 対象利用者の識別子
    subject: str | None = None
    #: 申請者の識別子
    applicant: str | None = None
    #: カタログ掲載APIの名称
    asset_name: str = ""
    #: 審査・取消の理由
    decision_reason: str | None = None
    #: 申請時に保存した利用条件・回答・審査履歴
    application: dict[str, Any] = Field(default_factory=dict)
    #: 現在の承認担当
    stage: str | None = None
    #: 利用申請の審査状態
    status: Literal[
        #: 審査待ち
        "pending",
        #: 承認済み
        "approved",
        #: 却下済み
        "rejected",
        #: 取消済み
        "revoked",
        #: 取り下げ済み
        "withdrawn",
    ]
    #: 更新時の競合検出に使う版番号
    revision: int


#: 監査履歴の明細
class Audit(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    #: 監査対象の操作日時
    at: datetime
    #: 操作した利用者・システムの識別子
    actor: str
    #: 利用プロジェクトの識別子
    project: str
    #: 提供プロジェクトの識別子
    owner: str
    #: カタログ掲載APIの識別子
    asset_id: str
    #: 提供環境
    environment: str
    #: 操作種別
    action: str
    #: 監査記録の詳細
    detail: str
    #: リクエスト識別子
    request_id: str
