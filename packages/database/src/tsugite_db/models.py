import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def new_id() -> str:
    return uuid4().hex


def now() -> datetime:
    return datetime.now(UTC)


#: 運営への問い合わせ
class Inquiry(Base):
    """問い合わせと回答

    利用者から運営に送信された問い合わせと、管理者からの回答を1件ずつ保存します。
    """

    __tablename__ = "inquiries"

    #: 問い合わせの識別子
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    #: 問い合わせを送信した利用者の識別子
    subject: Mapped[str] = mapped_column(String(180))
    #: 問い合わせ本文
    question: Mapped[str] = mapped_column(Text)
    #: 管理者の回答本文
    answer: Mapped[str | None] = mapped_column(Text)
    #: 問い合わせ受付日時
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    #: 管理者の回答日時
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: 問い合わせ更新時の競合検出番号
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}


#: API呼び出し識別名
class AssetRoute(Base):
    """呼び出し用API識別名

    掲載APIごとに1件を保存し、掲載終了後も再利用を防ぐために保持します。
    """

    __tablename__ = "asset_routes"

    #: 掲載APIの識別子
    asset_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    #: 呼び出しURLで使う一意なAPI識別名
    slug: Mapped[str] = mapped_column(String(63), unique=True)


#: APIカタログ
class Asset(Base):
    """掲載API

    提供プロジェクトがカタログに登録したAPIを1件保存します。
    """

    __tablename__ = "assets"

    #: 掲載APIの識別子
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    route: Mapped[AssetRoute | None] = relationship(
        primaryjoin="Asset.id == foreign(AssetRoute.asset_id)", lazy="joined"
    )
    #: 提供プロジェクトの識別子
    owner: Mapped[str] = mapped_column(String(64))
    #: API名
    name: Mapped[str] = mapped_column(String(120))
    #: APIの用途・概要
    summary: Mapped[str] = mapped_column(Text)
    #: 接続先APIの基底パス
    base_path: Mapped[str | None] = mapped_column(String(300))
    #: 登録したOpenAPI仕様（JSON）
    spec: Mapped[str] = mapped_column(Text)
    #: 環境別の申請項目・利用規約・承認経路（JSON）
    offers: Mapped[str | None] = mapped_column(Text)
    #: 次の公開版の変更説明
    release_note: Mapped[str | None] = mapped_column(Text)
    #: 提供環境と接続先の対応（JSON）
    targets: Mapped[str] = mapped_column(Text)
    #: 公開範囲と承認条件（JSON）
    policy: Mapped[str | None] = mapped_column(Text)
    #: カタログから削除した日時
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: カタログで公開中か
    published: Mapped[bool] = mapped_column(default=False)
    #: 管理者による全環境の呼び出し停止
    suspended: Mapped[bool | None] = mapped_column()
    #: 更新時の競合検出に使う版番号
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}


#: API利用申請・利用権
class Access(Base):
    """環境別の利用申請・利用権

    API・利用プロジェクト・環境の組み合わせごとに、申請から承認・取消までの状態を保存します。個人申請では対象利用者も区別します。
    """

    __tablename__ = "access_rights"

    #: 利用権の識別子
    id: Mapped[str] = mapped_column(String(140), primary_key=True)
    #: 申請対象APIの識別子
    asset_id: Mapped[str] = mapped_column(String(32))
    #: 利用プロジェクトの識別子
    project: Mapped[str] = mapped_column(String(64))
    #: 利用を申請した環境
    environment: Mapped[str] = mapped_column(String(16))
    #: 申請した利用者の識別子
    applicant: Mapped[str | None] = mapped_column(String(180))
    #: 個人申請の対象利用者識別子
    subject: Mapped[str | None] = mapped_column(String(180))
    #: 審査・取消の理由
    decision_note: Mapped[str | None] = mapped_column(Text)
    #: 申請時の回答・利用条件・審査履歴（JSON）
    submission: Mapped[str | None] = mapped_column(Text)
    #: 現在の承認担当
    stage: Mapped[str | None] = mapped_column(String(80))

    @property
    def application(self) -> dict[str, Any]:
        return json.loads(self.submission) if self.submission else {}

    #: 利用申請の理由
    reason: Mapped[str] = mapped_column(Text)
    #: 利用申請の審査状態
    status: Mapped[str] = mapped_column(String(16))
    #: 更新時の競合検出に使う版番号
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}


#: 監査履歴
class Event(Base):
    """監査イベント

    API登録、利用申請、審査、呼び出しなどで記録された操作を1件保存します。
    """

    __tablename__ = "audit_events"

    #: 監査イベントの識別子
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    #: 監査対象の操作日時
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    #: 操作した利用者・システムの識別子
    actor: Mapped[str] = mapped_column(String(180))
    #: 操作に関係するプロジェクト・組織
    project: Mapped[str] = mapped_column(String(64))
    #: 提供プロジェクトの識別子
    owner: Mapped[str] = mapped_column(String(64))
    #: 対象APIの識別子
    asset_id: Mapped[str] = mapped_column(String(32))
    #: 操作対象の環境
    environment: Mapped[str] = mapped_column(String(16))
    #: 監査対象の操作種別
    action: Mapped[str] = mapped_column(String(32))
    #: 監査記録の補足内容
    detail: Mapped[str] = mapped_column(Text)
    #: 操作をたどるためのリクエスト識別子
    request_id: Mapped[str] = mapped_column(String(40))


#: ポータル利用者
class Member(Base):
    """利用者アカウント

    ポータルで管理する利用者1人のアカウント情報を保存します。
    """

    __tablename__ = "portal_members"
    #: 利用者の識別子
    subject: Mapped[str] = mapped_column(String(180), primary_key=True)
    #: ログイン名
    username: Mapped[str] = mapped_column(String(180))
    #: 登録時の所属プロジェクト
    project: Mapped[str] = mapped_column(String(64))
    #: 登録時の役割
    role: Mapped[str] = mapped_column(String(16))
    #: 削除済みか
    deleted: Mapped[bool] = mapped_column(default=False)


#: 通知
class Notice(Base):
    """配信通知

    宛先を指定して送信した通知メッセージを1件保存します。
    """

    __tablename__ = "notices"
    #: 通知の識別子
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    #: 通知の送信日時
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    #: 通知の送信者
    sender: Mapped[str] = mapped_column(String(180))
    #: 通知先プロジェクト
    project: Mapped[str] = mapped_column(String(64))
    #: 通知に関連するAPIの識別子
    asset_id: Mapped[str] = mapped_column(String(32))
    #: 通知の件名
    title: Mapped[str] = mapped_column(String(160))
    #: 通知本文
    body: Mapped[str] = mapped_column(Text)


#: 通知の既読履歴
class NoticeRead(Base):
    """利用者別の既読記録

    ある利用者がある通知を既読にしたことを1件保存します。
    """

    __tablename__ = "notice_reads"
    #: 既読にした通知の識別子
    notice_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    #: 既読にした利用者の識別子
    subject: Mapped[str] = mapped_column(String(180), primary_key=True)


#: API呼び出し履歴
class AccessLog(Base):
    """API呼び出し記録

    転送APIが記録した1リクエストの呼び出し元、対象、応答結果を保存します。
    """

    __tablename__ = "invocation_logs"
    #: 呼び出しのリクエスト識別子
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    #: APIの呼び出し日時
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    #: 呼び出し元の利用者・システム識別子
    actor: Mapped[str] = mapped_column(String(180))
    #: 提供プロジェクトの識別子
    owner: Mapped[str] = mapped_column(String(64))
    #: 呼び出し元プロジェクトの識別子
    project: Mapped[str] = mapped_column(String(64))
    #: 呼び出したAPIの識別子
    asset_id: Mapped[str] = mapped_column(String(32))
    #: 呼び出した環境
    environment: Mapped[str] = mapped_column(String(16))
    #: 利用した認証情報の識別子
    key_id: Mapped[str | None] = mapped_column(String(32))
    #: HTTPメソッド
    method: Mapped[str] = mapped_column(String(16))
    #: 呼び出したAPI操作
    operation: Mapped[str] = mapped_column(Text)
    #: HTTPステータスコード
    status: Mapped[int]
    #: 応答時間（ミリ秒）
    duration_ms: Mapped[int]
    #: 呼び出し時のログ重要度・発生画面・運用作業
    diagnostics: Mapped[str | None] = mapped_column(Text)


#: API呼び出し件数の監視設定
class AlertRule(Base):
    """環境別の呼び出し件数監視ルール

    API・利用プロジェクト・環境ごとに、通知・停止の条件と現在の集計件数を保存します。
    """

    __tablename__ = "alert_rules"
    #: 監視ルールの識別子
    id: Mapped[str] = mapped_column(String(140), primary_key=True)
    #: 監視するAPIの識別子
    asset_id: Mapped[str] = mapped_column(String(32))
    #: 監視する利用プロジェクト
    project: Mapped[str] = mapped_column(String(64))
    #: 監視する提供環境
    environment: Mapped[str] = mapped_column(String(16))
    #: 通知・停止の基準件数
    threshold: Mapped[int]
    #: 呼び出し件数の集計区間（分）
    minutes: Mapped[int]
    #: 上限到達後の呼び出しを停止するか
    stop: Mapped[bool]
    #: 監視ルールが有効か
    enabled: Mapped[bool]
    #: 現在の集計区間の番号
    window: Mapped[int] = mapped_column(default=-1)
    #: 現在の集計区間の呼び出し件数
    calls: Mapped[int] = mapped_column(default=0)


#: 組織階層
class DirectoryTree(Base):
    """組織構成の保存記録

    部署とプロジェクトの階層全体を1つの構成として保存します。
    """

    __tablename__ = "directory_tree"
    #: 組織構成の識別子
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    #: 部署・プロジェクトの階層データ（JSON）
    units: Mapped[str] = mapped_column(Text)
    #: 更新時の競合検出に使う版番号
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}


#: 利用者の組織所属
class Affiliation(Base):
    """組織別の所属記録

    利用者1人と所属先1組織の組み合わせごとに、役職と管理権限を保存します。
    """

    __tablename__ = "affiliations"
    #: 所属する利用者の識別子
    subject: Mapped[str] = mapped_column(String(180), primary_key=True)
    #: 所属先の部署・プロジェクト識別子
    unit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    #: 所属先での役職名
    title: Mapped[str] = mapped_column(String(120))
    #: 所属先の管理権限があるか
    leader: Mapped[bool]
    #: 所属が有効か
    active: Mapped[bool]


#: 短期トークンの発行状態
class CredentialLease(Base):
    """短期トークンの再利用・更新記録

    発行経路・認証情報・利用者の組み合わせごとに、発行済みトークンを再利用できる期間を記録します。
    """

    __tablename__ = "credential_leases"
    #: 発行経路・認証情報・利用者から作る識別子
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    #: トークン発行時刻（UNIX秒）
    issued: Mapped[int]
    #: トークン有効期限（UNIX秒）
    expires: Mapped[int]
    #: トークンを更新できる時刻（UNIX秒）
    refresh_at: Mapped[int]
    #: 発行したトークンを区別する一意値
    nonce: Mapped[str] = mapped_column(String(32))
    #: 発行時の認証情報の版番号
    generation: Mapped[int]
    #: 更新時の競合検出に使う版番号
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}


#: 認証情報の利用制限
class CredentialRule(Base):
    """対象別の有効期間・操作制限

    対象のAPI、組織、またはAPIと利用者の組み合わせに対する制限を1件保存します。
    """

    __tablename__ = "credential_rules"
    #: 制限の適用対象を表す識別子
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    #: トークン有効期間の上限（分）
    limit_minutes: Mapped[int | None]
    #: 利用を許可するAPI操作（JSON）
    ops: Mapped[str | None] = mapped_column(Text)
    #: 更新時の競合検出に使う版番号
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}


#: API認証情報
class PortalKey(Base):
    """発行済みのAPI認証情報

    発行した認証情報ごとに利用範囲、所有者、秘密値の照合情報、失効状態を保存します。
    """

    __tablename__ = "api_keys"
    #: 認証情報の識別子
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    #: 認証方式
    mode: Mapped[str | None] = mapped_column(String(10))
    #: 有効期間・利用者・操作の制限（JSON）
    config: Mapped[str | None] = mapped_column(Text)
    #: 認証情報の発行時刻（UNIX秒）
    created: Mapped[int | None]
    #: 秘密値を照合するためのハッシュ値
    digest: Mapped[str] = mapped_column(String(64))
    #: 認証情報を利用するプロジェクト
    project: Mapped[str] = mapped_column(String(64))
    #: 認証情報を発行した利用者の識別子
    creator: Mapped[str] = mapped_column(String(180))
    #: 認証情報の表示名
    name: Mapped[str] = mapped_column(String(120))
    #: 認証情報の利用範囲（個人・共有）
    kind: Mapped[str] = mapped_column(String(12))
    #: 利用対象APIの識別子一覧（JSON）
    scopes: Mapped[str] = mapped_column(Text)
    #: 認証情報が失効済みか
    revoked: Mapped[bool] = mapped_column(default=False)
    #: 認証情報の版番号
    revision: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": revision}


#: API呼び出しと組織の対応
class LogUnit(Base):
    """呼び出しの組織別集計対象

    呼び出し1件をどの組織の利用実績に含めるか、リクエストと組織の組み合わせで保存します。
    """

    __tablename__ = "invocation_units"
    #: 呼び出しのリクエスト識別子
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    #: 利用実績を集計する組織の識別子
    unit_id: Mapped[str] = mapped_column(String(64), primary_key=True)


#: 商品別API仕様の公開履歴
class SpecRelease(Base):
    """商品API仕様の公開版

    商品ごとに公開したAPI仕様の1版を保存します。商品識別子と公開版番号の組み合わせで1件を特定します。
    """

    __tablename__ = "spec_releases"
    #: 公開した商品の識別子
    asset_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    #: 商品内の公開版番号
    number: Mapped[int] = mapped_column(primary_key=True)
    #: 仕様を公開した日時
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    #: 保存したOpenAPI文書の内容を識別するハッシュ値
    digest: Mapped[str] = mapped_column(String(64))
    #: 操作・構成要素と内容のハッシュ値の対応（JSON）
    manifest: Mapped[str] = mapped_column(Text)
    #: 公開時の変更内容と版情報（JSON）
    summary: Mapped[str] = mapped_column(Text)
