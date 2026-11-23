import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from app.apis import outputs
from app.apis.catalog.common import DB, User
from app.apis.governance.directory import manages, unit_condition
from app.apis.governance.notifications import unread
from app.core.diagnostics import exported_invocation
from app.core.log_visibility import led_calls
from app.core.workspace import allowed_audience, private_project, project_label, units
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, or_, select, true
from sqlalchemy.orm import load_only
from sqlalchemy.sql.elements import ColumnElement
from tsugite_db.models import Access, AccessLog, Asset

router = APIRouter()
LOG_FIELDS = (
    "at",
    "request_id",
    "actor",
    "key_id",
    "owner",
    "project",
    "asset_id",
    "environment",
    "method",
    "operation",
    "status",
    "duration_ms",
)


def visible(stmt, actor, db=None, unit=""):
    if unit:
        tree = units(db)
        if not manages(actor, tree, unit):
            raise HTTPException(403, "担当範囲のリーダー権限が必要です")
        return stmt.where(unit_condition(tree, unit))
    if actor.admin or actor.auditor:
        return stmt
    return stmt.where(
        or_(
            AccessLog.owner.in_(actor.owners),
            AccessLog.project.in_(actor.projects | {private_project(actor.subject)}),
        )
    )


def log_condition(
    actor: User,
    db: DB,
    #: 本人のアクセスログまたは権限内の監査履歴
    scope: Literal["personal", "audit"] = "personal",
    #: 監査対象の部署・プロジェクト識別子
    unit: str = "",
):
    if scope == "personal":
        if unit:
            raise HTTPException(403, "部署・プロジェクトの指定には監査履歴を使用してください")
        return AccessLog.actor == actor.subject
    global_access = actor.admin or actor.auditor
    if not global_access and not actor.leads:
        raise HTTPException(403, "監査履歴を閲覧する権限がありません")
    tree = units(db)
    condition = true() if global_access else led_calls(tree, actor.leads)
    if unit:
        if unit not in tree or not (global_access or manages(actor, tree, unit)):
            raise HTTPException(403, "指定された範囲の監査権限がありません")
        return condition & unit_condition(tree, unit)
    return condition


LogCondition = Annotated[ColumnElement[bool], Depends(log_condition)]


def interval(
    #: 集計開始日時
    start: datetime | None = None,
    #: 集計終了日時
    end: datetime | None = None,
    #: 対象APIの識別子
    asset_id: str = "",
    #: 利用プロジェクトの識別子
    project: str = "",
    #: 提供環境
    environment: str = "",
    #: 検索するHTTPステータスコード
    status: int = Query(0, ge=0, le=599),
):
    end = end or datetime.now(UTC)
    start = start or end - timedelta(hours=24)
    if not start.tzinfo or not end.tzinfo or not timedelta(0) < end - start <= timedelta(days=31):
        raise HTTPException(422, "タイムゾーン付きで31日以内の期間を指定してください")
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    stm = select(AccessLog).where(AccessLog.at >= start, AccessLog.at < end)
    for column, value in (
        (AccessLog.asset_id, asset_id),
        (AccessLog.project, project),
        (AccessLog.environment, environment),
        (AccessLog.status, status),
    ):
        if value:
            stm = stm.where(column == value)
    return start, end, stm


Range = Annotated[tuple, Depends(interval)]


def log_data(row):
    result = {k: getattr(row, k) for k in LOG_FIELDS}
    result["at"] = (
        row.at.replace(tzinfo=UTC).isoformat() if row.at.tzinfo is None else row.at.isoformat()
    )
    return result


#: API呼び出し履歴を検索する
@router.get("/access-logs", responses={200: {"model": list[outputs.AccessLog]}})
def access_logs(
    condition: LogCondition,
    db: DB,
    period: Range,
    #: 一度に取得する履歴の件数
    limit: int = Query(50, ge=1, le=50),
    #: 先頭から読み飛ばす件数
    offset: int = Query(0, ge=0),
    #: リクエスト識別子
    request_id: str = "",
):
    stmt = period[2].where(condition)
    if request_id:
        stmt = stmt.where(AccessLog.request_id == request_id)
    return [
        log_data(r)
        for r in db.scalars(
            stmt.order_by(AccessLog.at.desc(), AccessLog.request_id).offset(offset).limit(limit)
        )
    ]


#: リクエスト識別子からAPI呼び出しの詳細を取得する
@router.get("/access-logs/detail", responses={200: {"model": outputs.AccessLogDetail}})
def access_log_detail(
    condition: LogCondition,
    db: DB,
    #: リクエスト識別子
    request_id: str,
):
    stmt = select(AccessLog).where(condition)
    row = db.scalar(stmt.where(AccessLog.request_id == request_id))
    if row is None:
        raise HTTPException(404, "アクセスログが見つかりません")
    data = log_data(row)
    record = exported_invocation(row, data)
    return {
        **data,
        "started_at": record.get("started_at"),
        "responded_at": record.get("responded_at"),
        "error_code": record["reason"] if row.status >= 400 else None,
    }


#: API呼び出し履歴をファイルに出力する
@router.get(
    "/access-logs/download",
    response_class=Response,
    responses={
        200: {
            "description": "アクセスログ（1行1件のJSON）",
            "content": {"application/x-ndjson": {"schema": {"type": "string"}}},
            "headers": {
                #: ダウンロード時の保存方法・ファイル名
                "Content-Disposition": {
                    "schema": {"type": "string"},
                    "description": "保存用のファイル名",
                },
                #: 次のページの開始位置
                "X-Next-Cursor": {"schema": {"type": "string"}, "description": "次ページがある場合のみ"},
            },
        }
    },
)
def download(
    condition: LogCondition,
    db: DB,
    period: Range,
    #: リクエスト識別子
    request_id: str = "",
    #: 次のページの開始位置
    cursor: str = "",
):
    stmt = period[2].where(condition)
    if request_id:
        stmt = stmt.where(AccessLog.request_id == request_id)
    if cursor:
        try:
            stamp, key = cursor.split("|", 1)
            at = datetime.fromisoformat(stamp)
        except ValueError as exc:
            raise HTTPException(422, "無効なカーソルです") from exc
        stmt = stmt.where(or_(AccessLog.at > at, (AccessLog.at == at) & (AccessLog.request_id > key)))
    records = list(db.scalars(stmt.order_by(AccessLog.at, AccessLog.request_id).limit(251)))
    headers = {"Content-Disposition": 'attachment; filename="access-log.jsonl"'}
    if len(records) > 250:
        last = records[249]
        headers["X-Next-Cursor"] = last.at.isoformat() + "|" + last.request_id
    return Response(
        "".join(
            json.dumps(exported_invocation(row, log_data(row)), ensure_ascii=False) + "\n"
            for row in records[:250]
        ),
        media_type="application/x-ndjson",
        headers=headers,
    )


def metric_rows(db, stmt):
    # DSQLではサーバー側カーソルを使えないため、一意なリクエストIDを境に分割する。
    page_size = 500
    ordered = (
        stmt.with_only_columns(
            AccessLog.request_id, AccessLog.at, AccessLog.status, AccessLog.duration_ms
        )
        .order_by(AccessLog.request_id)
        .limit(page_size)
    )
    page = ordered
    while True:
        rows = db.execute(page).all()
        yield from rows
        if len(rows) < page_size:
            return
        page = ordered.where(AccessLog.request_id > rows[-1].request_id)


#: 時間帯別の呼び出し件数と応答時間を集計する
@router.get("/metrics", responses={200: {"model": outputs.Metrics}})
def metrics(
    actor: User,
    db: DB,
    period: Range,
    #: 集計間隔（分）
    minutes: Literal["1", "5", "15", "60", "1440"] = "60",
    #: 集計対象の部署・プロジェクト識別子
    unit: str = "",
):
    start, end, stmt = period
    seconds = int(minutes) * 60
    first = int(start.timestamp()) // seconds
    last = (int((end - timedelta(microseconds=1)).timestamp())) // seconds
    if last - first > 1500:
        raise HTTPException(422, "期間を短くするか集計間隔を長くしてください")
    buckets: list[dict] = [
        dict(
            at=datetime.fromtimestamp(n * seconds, UTC).isoformat(),
            calls=0,
            success=0,
            errors=0,
            denied=0,
            elapsed=0,
            max_ms=0,
        )
        for n in range(first, last + 1)
    ]
    for row in metric_rows(db, visible(stmt, actor, db, unit)):
        at, status, latency = row.at, row.status, row.duration_ms
        bucket = buckets[int(at.replace(tzinfo=UTC).timestamp()) // seconds - first]
        bucket["calls"] += 1
        bucket["success"] += int(200 <= status < 300)
        bucket["errors"] += int(status >= 400)
        bucket["denied"] += int(status in (401, 403, 429))
        bucket["elapsed"] += latency
        bucket["max_ms"] = max(bucket["max_ms"], latency)
    for bucket in buckets:
        bucket["avg_ms"] = round(bucket.pop("elapsed") / bucket["calls"], 1) if bucket["calls"] else 0
        bucket.pop("elapsed", None)
    return {"start": start, "end": end, "minutes": int(minutes), "points": buckets}


#: ダッシュボードの件数を集計する
@router.get("/dashboard", responses={200: {"model": outputs.Dashboard}})
def dashboard(actor: User, db: DB):
    assets = select(func.count(Asset.id)).where(Asset.removed_at.is_(None))
    rights = (
        select(func.count(Access.id))
        .join(Asset, Asset.id == Access.asset_id)
        .where(Asset.removed_at.is_(None))
    )
    if not actor.admin and not actor.auditor:
        rights = rights.where(
            or_(
                Asset.owner.in_(actor.owners),
                Access.subject == actor.subject,
                Access.subject.is_(None) & Access.project.in_(actor.projects),
            )
        )
    calls = visible(
        select(func.count(AccessLog.request_id)).where(
            AccessLog.at >= datetime.now(UTC) - timedelta(days=1)
        ),
        actor,
    )
    return {
        "published": sum(
            1
            for a in db.scalars(
                select(Asset)
                .options(load_only(Asset.owner, Asset.policy))
                .where(Asset.removed_at.is_(None), Asset.published.is_(True))
            )
            if allowed_audience(a, actor)
        ),
        "inventory": db.scalar(assets if actor.admin else assets.where(Asset.owner.in_(actor.owners))),
        "pending": db.scalar(rights.where(Access.status == "pending")),
        "approved": db.scalar(rights.where(Access.status == "approved")),
        "calls": db.scalar(calls),
        "errors": db.scalar(calls.where(AccessLog.status >= 400)),
        "unread": unread(db, actor),
    }


#: 監視対象に指定できるAPIの利用先を一覧する
@router.get("/management-targets", responses={200: {"model": list[outputs.ManagementTarget]}})
def management_targets(actor: User, db: DB):
    stmt = (
        select(Access, Asset.name)
        .join(Asset, Asset.id == Access.asset_id)
        .where(Asset.removed_at.is_(None))
    )
    if not actor.admin:
        stmt = stmt.where(Asset.owner.in_(actor.owners))
    tree = units(db)
    return [
        {
            "id": "/".join((r.asset_id, r.project, r.environment)),
            "asset_id": r.asset_id,
            "name": name,
            "project": r.project,
            "project_label": project_label(tree, r.project),
            "environment": r.environment,
        }
        for r, name in db.execute(stmt.order_by(Asset.name, Access.project, Access.environment))
    ]


def dimension_rows(db, stmt):
    stmt = (
        stmt.with_only_columns(AccessLog.asset_id, Asset.name, AccessLog.project)
        .join(Asset, Asset.id == AccessLog.asset_id)
        .distinct()
    )
    return [{"asset_id": r.asset_id, "name": r.name, "project": r.project} for r in db.execute(stmt)]


#: 利用統計を絞り込めるAPIとプロジェクトを一覧する
@router.get("/metric-dimensions", responses={200: {"model": list[outputs.Dimension]}})
def dimensions(
    actor: User,
    db: DB,
    #: 集計対象の部署・プロジェクト識別子
    unit: str = "",
):
    return dimension_rows(db, visible(select(AccessLog), actor, db, unit))


#: 閲覧できるアクセスログのAPIと利用プロジェクトを一覧する
@router.get("/access-logs/dimensions", responses={200: {"model": list[outputs.Dimension]}})
def log_dimensions(condition: LogCondition, db: DB):
    return dimension_rows(db, select(AccessLog).where(condition))
