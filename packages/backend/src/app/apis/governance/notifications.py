from app.apis import outputs
from app.apis.catalog.common import DB, User, event, record
from app.apis.governance.members import projects
from app.apis.schemas import Input
from app.core.workspace import private_project
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field
from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from tsugite_db.models import Access, Event, Notice, NoticeRead

router = APIRouter()


class Message(Input):
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=3000)
    project: str = Field(min_length=1, max_length=64)
    asset_id: str = ""


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


@router.get("/notifications", responses={200: {"model": outputs.Inbox}})
def inbox(actor: User, db: DB, offset: int = Query(0, ge=0)):
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
                "at": n.at,
                "unread": is_new,
            }
            for n, is_new in records
        ],
    }


@router.get("/notifications/count", responses={200: {"model": outputs.Unread}})
def badge(actor: User, db: DB):
    return {"unread": unread(db, actor)}


@router.post("/notifications", status_code=201, responses={201: {"model": outputs.Identifier}})
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


@router.put("/notifications/{key}/read", responses={200: {"model": outputs.Read}})
def mark_read(key: str, actor: User, db: DB):
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
