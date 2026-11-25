# APIの応答モデルを定義する。
"""Response contracts for handlers that build JSON dictionaries directly."""

from datetime import datetime
from typing import Literal, NotRequired, TypedDict


#: サーバー内部のエラー
class InternalServerError(TypedDict):
    #: 問い合わせ用のエラー分類
    error_code: Literal["INTERNAL_ERROR"]
    #: 利用者に表示するエラー内容
    detail: str


#: HTTPエラーの内容
class ErrorDetail(TypedDict):
    #: 利用者に表示するエラー内容
    detail: str


#: サービスの稼働状態
class Health(TypedDict):
    #: サービスの稼働状態
    status: str


#: ポータルのログイン設定
class PortalConfig(TypedDict):
    #: デモ環境か
    demo: bool
    #: ログイン用ドメイン
    domain: str
    #: ユーザープールの認証API接続先
    identity_endpoint: str
    #: ポータルのログイン用クライアント識別子
    client_id: str


#: デモログインの認証結果
class DemoToken(TypedDict):
    #: アクセストークン
    access_token: str


#: 利用者に表示できる接続先
class VisibleTarget(TypedDict):
    #: 提供プロジェクトの識別子
    owner: str
    #: 提供環境
    environment: str


#: 利用者のメタデータ項目
class MetadataField(TypedDict):
    #: メタデータのキー
    key: str
    #: 項目の表示名
    label: str
    #: 業務機能で使用中のデータパーツか
    builtin: bool
    #: 値の名称を全利用者に公開するか
    public_values: bool


#: ログイン利用者の所属と権限
class Profile(TypedDict):
    #: ナビゲーションに表示するメタデータ項目
    metadata_fields: list[MetadataField]
    #: 本人のメタデータ（項目キーごとの値の識別子）
    metadata: dict[str, list[str]]
    #: 管理者が参照できるプロジェクト
    known_projects: list[str]
    #: 管理者が参照できるプロジェクトの識別子と表示名の対応
    known_project_labels: NotRequired[dict[str, str]]
    #: 個人用プロジェクトの識別子
    personal_project: str
    #: 管理権限を持つ組織
    leads: list[str]
    #: 所属部署
    departments: list[str]
    #: 役職一覧
    titles: list[str]
    #: 全体管理者か
    admin: bool
    #: 対象利用者の識別子
    subject: str
    #: 利用プロジェクト一覧
    projects: list[str]
    #: 提供者として担当するプロジェクト
    owners: list[str]
    #: 監査担当者か
    auditor: bool
    #: 利用者が参照できる接続先
    targets: dict[str, VisibleTarget]


#: 登録した項目の識別子
class Identifier(TypedDict):
    #: 識別子
    id: str


#: 削除結果
class Deleted(TypedDict):
    #: 削除済みか
    deleted: bool


#: 所属の解除結果
class Removed(TypedDict):
    #: 所属を解除したか
    removed: bool


#: 認証情報の失効結果
class Revoked(TypedDict):
    #: 認証情報が失効済みか
    revoked: bool


#: 通知の既読登録結果
class Read(TypedDict):
    #: 既読にしたか
    read: bool


#: 未読通知の件数
class Unread(TypedDict):
    #: 未読通知件数
    unread: int


#: 所属先で表示する利用者の情報
class PersonNames(TypedDict):
    #: メールアドレス
    email: str | None
    #: 氏名
    full_name: str | None
    #: 表示名
    display_name: str | None


#: 権限設定で選択する利用者
class MemberIdentity(TypedDict):
    #: 対象利用者の識別子
    subject: str
    #: ログイン名
    username: str


#: 利用者の識別情報
class Person(MemberIdentity, PersonNames):
    pass


#: 編集用の利用者プロフィール
class MemberProfile(PersonNames):
    #: 利用者の識別子
    subject: str
    #: 更新時に照合する版番号
    revision: int


#: ポータル利用者
class Member(Person):
    #: 利用者の役割
    role: str
    #: 所属プロジェクトの識別子
    project: NotRequired[str]
    #: 削除済みか
    deleted: NotRequired[bool]


#: 利用者一覧のページ
class MemberPage(TypedDict):
    #: このページの利用者
    items: list[Member]
    #: 次ページを取得するためのカーソル
    next: str
    #: 招待先に選べるプロジェクト
    projects: list[str]


#: 部署・プロジェクトの登録情報
class Unit(TypedDict):
    #: 部署・プロジェクトの識別子
    id: str
    #: 所属先を分類するメタデータのキー
    kind: str
    #: 部署・プロジェクト名
    name: str
    #: 親部署の識別子
    parent: str
    #: 組織の利用を停止中か
    stopped: bool


#: 利用者の所属情報
class Affiliation(Person):
    #: 部署・プロジェクトの識別子
    unit_id: str
    #: 役職名
    title: str
    #: 所属先の管理者か
    leader: bool
    #: 所属が有効か
    active: NotRequired[bool]


#: 組織構成と利用者の所属一覧
class Workspace(TypedDict):
    #: 設定可能なメタデータ項目
    metadata_fields: list[MetadataField]
    #: 全体管理者か
    admin: bool
    #: 部署・プロジェクトの一覧
    units: list[Unit]
    #: 管理権限を持つ組織
    leads: list[str]
    #: 自分が所属する組織
    my_units: list[str]
    #: 利用者と組織の所属関係
    memberships: list[Affiliation]
    #: 参照できる利用者
    users: list[Person]
    #: 役職一覧
    titles: list[str]


#: プロジェクト別の呼び出し件数
class ByProject(TypedDict):
    #: 利用プロジェクトの識別子
    project: str
    #: 呼び出し件数
    calls: int


#: API別の呼び出し件数
class ByAPI(TypedDict):
    #: カタログ掲載APIの識別子
    asset_id: str
    #: API名
    name: str
    #: 呼び出し件数
    calls: int


#: 組織のAPI利用実績
class Usage(TypedDict):
    #: 部署・プロジェクトの識別子
    unit_id: str
    #: 対象組織に所属する利用者
    members: list[Affiliation]
    #: 呼び出し件数
    calls: int
    #: エラー応答件数
    errors: int
    #: プロジェクト別の利用実績
    by_project: list[ByProject]
    #: API別の利用実績
    by_api: list[ByAPI]


#: 発行済み認証情報の登録内容
class KeyMetadata(TypedDict):
    #: 認証方式
    mode: Literal[
        #: 従来方式
        "legacy",
        #: 短期トークン方式
        "bearer",
        #: 利用者を伴うアプリ認証
        "app",
        #: システム間認証
        "system",
    ]
    #: 希望するトークン有効期間（分）
    ttl_minutes: NotRequired[int]
    #: 発行から更新可能になるまでの時間（分）
    refresh_minutes: NotRequired[int]
    #: 対象のAPI操作
    operations: NotRequired[dict[str, list[str]]]
    #: 利用を許可する利用者
    users: NotRequired[list[str]]
    #: ポータルからトークンを取得できるか
    can_portal_exchange: NotRequired[bool]
    #: 認証情報の識別子
    id: str
    #: 認証情報の表示名
    name: str
    #: 利用プロジェクトの識別子
    project: str
    #: APIキーの利用範囲（個人・共有）
    kind: Literal[
        #: 個人用
        "personal",
        #: 共有
        "shared",
    ]
    #: 認証情報の発行者
    creator: str
    #: 対象APIの識別子一覧
    api_ids: list[str]
    #: 認証情報が失効済みか
    revoked: bool


#: 発行した従来方式のAPIキー
class IssuedKey(KeyMetadata):
    #: 発行時のみ表示するAPIキーの秘密値
    secret: str


#: 受信通知の明細
class Notice(TypedDict):
    #: 通知の識別子
    id: str
    #: 通知の件名
    title: str
    #: 通知本文
    body: str
    #: 通知先プロジェクトの識別子
    project: str
    #: 通知の送信者
    sender: str
    #: 通知の送信日時
    at: datetime
    #: この通知が未読か
    unread: bool


#: 受信通知一覧
class Inbox(Unread):
    #: 受信した通知の明細
    items: list[Notice]


#: API呼び出し履歴
class AccessLog(TypedDict):
    #: APIの呼び出し日時
    at: datetime
    #: リクエスト識別子
    request_id: str
    #: 呼び出し元の利用者・システム識別子
    actor: str
    #: 認証情報の識別子
    key_id: str | None
    #: 提供プロジェクトの識別子
    owner: str
    #: 利用プロジェクトの識別子
    project: str
    #: カタログ掲載APIの識別子
    asset_id: str
    #: 提供環境
    environment: str
    #: HTTPメソッド
    method: str
    #: 呼び出したAPI操作
    operation: str
    #: HTTPステータスコード
    status: int
    #: 応答時間（ミリ秒）
    duration_ms: int


#: 1回のAPI呼び出しの詳細
class AccessLogDetail(AccessLog):
    #: 呼び出し処理の開始日時
    started_at: datetime | None
    #: 応答結果が確定した日時
    responded_at: datetime | None
    #: 記録されたエラー理由のコード
    error_code: str | None


#: 集計区間ごとの呼び出し実績
class MetricPoint(TypedDict):
    #: 集計区間の開始日時
    at: datetime
    #: 呼び出し件数
    calls: int
    #: 成功応答件数
    success: int
    #: エラー応答件数
    errors: int
    #: アクセス拒否件数
    denied: int
    #: 最長応答時間（ミリ秒）
    max_ms: int
    #: 平均応答時間（ミリ秒）
    avg_ms: float


#: 期間別のAPI利用統計
class Metrics(TypedDict):
    #: 集計開始日時
    start: datetime
    #: 集計終了日時
    end: datetime
    #: 集計間隔（分）
    minutes: int
    #: 集計区間ごとの実績
    points: list[MetricPoint]


#: ダッシュボードの集計結果
class Dashboard(Unread):
    #: 公開中のAPI件数
    published: int
    #: 管理対象の掲載API件数
    inventory: int
    #: 審査待ちの利用申請件数
    pending: int
    #: 承認済みの利用申請件数
    approved: int
    #: 呼び出し件数
    calls: int
    #: エラー応答件数
    errors: int


#: 利用統計の集計対象
class Dimension(TypedDict):
    #: カタログ掲載APIの識別子
    asset_id: str
    #: API名
    name: str
    #: 利用プロジェクトの識別子
    project: str


#: 監視対象のAPI・プロジェクト・環境
class ManagementTarget(Dimension):
    #: 監視対象の識別子
    id: str
    #: 利用プロジェクトの表示名
    project_label: NotRequired[str]
    #: 提供環境
    environment: str


#: 短期アクセストークンと期限
class Token(TypedDict):
    #: アクセストークン
    access_token: str
    #: トークンの種類
    token_type: Literal[
        #: ベアラートークン
        "Bearer",
    ]
    #: 有効期限までの秒数
    expires_in: int
    #: 更新可能になるまでの秒数
    refresh_after: int
    #: 有効期限（UNIX秒）
    expires_at: int
    #: 更新可能になる時刻（UNIX秒）
    refresh_at: int


#: OAuthトークン交換の応答
class ExchangedToken(Token):
    #: 交換して発行したトークンの種類
    issued_token_type: str


#: OAuthトークン交換のエラー応答
class TokenExchangeError(TypedDict):
    #: エラーを識別するコード
    error: str
    #: 利用者向けのエラーの説明
    error_description: str


#: クライアント認証情報
class ClientCredential(TypedDict):
    #: クライアント識別子
    client_id: str
    #: クライアントシークレット
    client_secret: str


#: 発行した認証情報と短期トークン
class IssuedBearer(KeyMetadata, Token):
    pass


#: 発行した認証情報とクライアントシークレット
class IssuedClient(KeyMetadata, ClientCredential):
    pass


#: APIの利用者別操作権限
class OperationPolicy(TypedDict):
    #: 対象のAPI操作
    operations: list[str]
    #: 対象の利用者一覧
    members: list[MemberIdentity]
    #: 利用者ごとに許可されたAPI操作
    permissions: dict[str, list[str]]


#: 設定した有効期間上限と継承上限
class Limit(TypedDict):
    #: 上位の設定による有効期間上限（分）
    inherited_minutes: int
    #: トークンの有効期間上限（分）
    max_minutes: int | None


#: 認証情報の発行対象API
class CredentialAsset(TypedDict):
    #: カタログ掲載APIの識別子
    id: str
    #: API名
    name: str
    #: 対象のAPI操作
    operations: list[str]
    #: トークンの有効期間上限（分）
    max_minutes: int


#: 組織ごとのトークン有効期間上限
class UnitLimit(TypedDict):
    #: 有効期間上限を設定した組織名
    name: str
    #: 組織の有効期間上限（分）
    minutes: int


#: 認証情報の発行条件と選択肢
class CredentialOptions(TypedDict):
    #: 発行対象に選べるAPI
    assets: list[CredentialAsset]
    #: 対象の利用者一覧
    members: list[MemberIdentity]
    #: 組織別の有効期間上限
    limits: list[UnitLimit]
    #: トークンの有効期間上限（分）
    max_minutes: int
    #: 対象プロジェクトの管理権限があるか
    may_manage: bool


# FastAPIが生成する標準422応答の型。出力する項目と必須条件はFastAPIのスキーマに従う。
#: 入力エラーの項目別明細
class ValidationError(TypedDict):
    #: 入力エラーの発生箇所
    loc: list[str | int]
    #: 入力エラーの説明
    msg: str
    #: 入力エラーの分類コード
    type: str
    #: エラーになった入力値
    input: NotRequired[object]
    #: 入力エラーの補足情報
    ctx: NotRequired[dict[str, object]]


#: リクエスト入力エラー
class HTTPValidationError(TypedDict):
    #: 入力エラーの明細一覧
    detail: list[ValidationError]
