"""ポータルの通知を配信・取得する。"""

from app.apis.governance.members import projects
from app.core.catalog import event, record
from app.core.workspace import private_project
from app.dependencies import DB, User
from app.schemas import outputs
from app.schemas.base import database_time
from app.schemas.errors import domain_errors
from app.schemas.notifications import Message
from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from tsugite_db.models import Access, Event, Notice, NoticeRead

router = APIRouter()


def mailbox(actor):
    return or_(
        Notice.project == "*",
        Notice.project.in_(actor.projects | {private_project(actor.subject)}),
        Notice.sender == actor.subject,
    )


def unread_query(actor):
    return ~exists().where(NoticeRead.notice_id == Notice.id, NoticeRead.subject == actor.subject)


def unread(db, actor):
    return db.scalar(select(func.count(Notice.id)).where(mailbox(actor), unread_query(actor))) or 0


#: 受信した通知を一覧する
@router.get("/notifications", responses={200: {"model": outputs.Inbox}})
def inbox(
    actor: User,
    db: DB,
    #: 先頭から読み飛ばす件数
    offset: int = Query(0, ge=0),
):
    records = db.execute(
        select(Notice, unread_query(actor))
        .where(mailbox(actor))
        .order_by(Notice.at.desc(), Notice.id.desc())
        .offset(offset)
        .limit(30)
    )
    return {
        "unread": unread(db, actor),
        "items": [
            {
                "id": n.id,
                "title": n.title,
                "body": n.body,
                "project": n.project,
                "sender": n.sender,
                "at": database_time(n.at),
                "unread": is_new,
            }
            for n, is_new in records
        ],
    }


#: 未読の通知件数を取得する
@router.get("/notifications/count", responses={200: {"model": outputs.Unread}})
def badge(actor: User, db: DB):
    return {"unread": unread(db, actor)}


#: 利用者に通知を送る
@router.post(
    "/notifications",
    status_code=201,
    responses={
        **domain_errors(403),
        201: {"model": outputs.Identifier, "description": "送信した通知の識別子（id）"},
    },
)
def send(data: Message, request: Request, actor: User, db: DB):
    if not actor.admin and not actor.owners:
        raise HTTPException(403)
    if actor.admin:
        if data.project != "*" and data.project not in projects(db):
            raise HTTPException(422, "送信先プロジェクトを確認してください")
        db.add(
            Event(
                actor=actor.subject,
                owner="",
                project=data.project,
                asset_id="",
                environment="",
                action="notify",
                detail=data.title,
                request_id=request.state.request_id,
            )
        )
    else:
        asset = record(db, data.asset_id)
        if asset.owner not in actor.owners or not db.scalar(
            select(Access.id).where(Access.asset_id == asset.id, Access.project == data.project).limit(1)
        ):
            raise HTTPException(403, "提供中のAPIに申請したプロジェクトを選んでください")
        event(db, request, actor, asset, "notify", data.project, detail=data.title)
    n = Notice(
        sender=actor.subject,
        title=data.title,
        body=data.body,
        project=data.project,
        asset_id=data.asset_id,
    )
    db.add(n)
    db.commit()
    return {"id": n.id}


#: 通知を既読にする
@router.put("/notifications/{key}/read", responses={**domain_errors(404), 200: {"model": outputs.Read}})
def mark_read(
    #: 既読にする通知の識別子
    key: str,
    actor: User,
    db: DB,
):
    if not db.scalar(select(Notice.id).where(Notice.id == key, mailbox(actor))):
        raise HTTPException(404)
    if not db.get(NoticeRead, (key, actor.subject)):
        db.add(NoticeRead(notice_id=key, subject=actor.subject))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if not db.get(NoticeRead, (key, actor.subject)):
                raise
    return {"read": True}
