from time import time
from typing import Literal

from app.apis import outputs
from app.apis.catalog.common import DB, User, event, record, right_id
from app.apis.schemas import Env, Input
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from sqlalchemy import case, or_, select, update
from tsugite_db.models import Access, AlertRule, Asset, Notice

router = APIRouter()


class Rule(Input):
    asset_id: str
    project: str
    environment: Env
    threshold: int = Field(ge=1, le=100000000)
    minutes: Literal[1, 5, 15, 60, 1440]
    stop: bool
    enabled: bool = True


class RuleResult(Rule):
    name: str
    calls: int


@router.put("/alerts", responses={200: {"model": outputs.Identifier}})
def save_rule(data: Rule, request: Request, actor: User, db: DB):
    asset = record(db, data.asset_id)
    if not actor.admin and asset.owner not in actor.owners:
        raise HTTPException(403)
    key = right_id(asset.id, data.project, data.environment)
    if not db.scalar(
        select(Access.id)
        .where(
            Access.asset_id == asset.id,
            Access.project == data.project,
            Access.environment == data.environment,
        )
        .limit(1)
    ):
        raise HTTPException(422, "対象の利用申請がありません")
    row = db.get(AlertRule, key)
    if not row:
        row = AlertRule(id=key)
        db.add(row)
    for field, value in data.model_dump().items():
        setattr(row, field, value)
    row.calls, row.window = 0, -1
    event(
        db,
        request,
        actor,
        asset,
        "alert.configure",
        data.project,
        data.environment,
        f"{data.minutes}分 / {data.threshold}件 / " + ("停止" if data.stop else "通知")
        if data.enabled
        else "ルール無効",
    )
    db.commit()
    return {"id": key}


@router.get("/alerts", responses={200: {"model": list[RuleResult]}})
def rules(actor: User, db: DB):
    stmt = (
        select(AlertRule, Asset.name)
        .join(Asset, Asset.id == AlertRule.asset_id)
        .where(Asset.removed_at.is_(None))
    )
    if not actor.admin:
        stmt = stmt.where(or_(Asset.owner.in_(actor.owners), AlertRule.project.in_(actor.projects)))
    return [
        {
            **{k: getattr(rule, k) for k in Rule.model_fields},
            "name": name,
            "calls": rule.calls if rule.window == int(time()) // (60 * rule.minutes) else 0,
        }
        for rule, name in db.execute(stmt.order_by(Asset.name, AlertRule.project))
    ]


def admit(db, request, actor, asset, project, env):
    key = right_id(asset.id, project, env)
    rule = db.get(AlertRule, key)
    if not rule or not rule.enabled:
        return
    window = int(time()) // (60 * rule.minutes)
    # Reserve the call before forwarding. Concurrent callers cannot both reserve the last admission.
    stmt = (
        update(AlertRule)
        .where(
            AlertRule.id == key,
            AlertRule.enabled.is_(True),
            AlertRule.minutes == rule.minutes,
            AlertRule.threshold == rule.threshold,
            AlertRule.stop == rule.stop,
            or_(
                AlertRule.window != window,
                AlertRule.calls < AlertRule.threshold,
                AlertRule.stop.is_(False),
            ),
        )
        .values(window=window, calls=case((AlertRule.window != window, 1), else_=AlertRule.calls + 1))
        .returning(AlertRule.calls)
        .execution_options(synchronize_session=False)
    )
    calls = db.scalar(stmt)
    if calls is None:
        raise HTTPException(429, "この期間の利用上限に達しました")
    if calls == rule.threshold:
        note = f"{asset.name}（{env}）が{rule.minutes}分間の上限{calls}件に達しました。" + (
            "次の集計期間まで利用を停止します。" if rule.stop else "引き続き利用できます。"
        )
        db.add(
            Notice(
                sender="継手API", project=project, asset_id=asset.id, title="利用件数アラート", body=note
            )
        )
        event(db, request, actor, asset, "alert.trigger", project, env, note)
