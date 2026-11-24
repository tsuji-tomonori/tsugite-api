# 問い合わせと返信を受け付ける。
from datetime import datetime
from uuid import UUID

from app.apis.catalog.common import DB, User
from app.apis.schemas import Input
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from tsugite_db.models import Inquiry, now

router = APIRouter()


#: 運営への問い合わせ内容
class InquirySubmission(Input):
    #: 問い合わせの識別子
    inquiry_id: UUID
    #: 問い合わせ本文
    question: str = Field(min_length=2, max_length=2000)


#: 問い合わせへの回答
class InquiryReply(Input):
    #: 回答本文
    answer: str = Field(min_length=2, max_length=2000)


#: 問い合わせの受付・回答履歴
class InquiryRecord(BaseModel):
    #: 問い合わせの識別子
    inquiry_id: str
    #: 問い合わせ本文
    question: str
    #: 回答本文
    answer: str | None
    #: 問い合わせ受付日時
    at: datetime
    #: 回答日時
    answered_at: datetime | None


def result(row):
    return InquiryRecord(
        inquiry_id=row.id,
        question=row.question,
        answer=row.answer,
        at=row.at,
        answered_at=row.answered_at,
    )


#: 運営への問い合わせを送信する
@router.post("/inquiries", response_model=InquiryRecord, status_code=201)
def submit_inquiry(data: InquirySubmission, actor: User, db: DB):
    question = data.question.strip()
    if len(question) < 2:
        raise HTTPException(422, "問い合わせ内容を入力してください")
    key = data.inquiry_id.hex
    row = db.get(Inquiry, key)
    if row is None:
        row = Inquiry(id=key, subject=actor.subject, question=question)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            row = db.get(Inquiry, key)
            if row is None:
                raise
    if row.subject != actor.subject or row.question != question:
        raise HTTPException(409, "問い合わせ内容を確認してください")
    return result(row)


#: 問い合わせ履歴を取得する
@router.get("/inquiries", response_model=list[InquiryRecord])
def get_inquiries(
    actor: User,
    db: DB,
    #: すべての利用者の問い合わせを表示するか
    incoming: bool = False,
    #: 先頭から読み飛ばす件数
    offset: int = Query(0, ge=0),
):
    query = select(Inquiry)
    if incoming:
        if not actor.admin:
            raise HTTPException(403)
    else:
        query = query.where(Inquiry.subject == actor.subject)
    return [
        result(row)
        for row in db.scalars(
            query.order_by(Inquiry.at.desc(), Inquiry.id.desc()).offset(offset).limit(21)
        )
    ]


#: 問い合わせに回答する
@router.put("/inquiries/{inquiry_id}/reply", response_model=InquiryRecord)
def reply_to_inquiry(
    #: 問い合わせの識別子
    inquiry_id: UUID,
    data: InquiryReply,
    request: Request,
    actor: User,
    db: DB,
):
    if not actor.admin:
        raise HTTPException(403)
    row = db.get(Inquiry, inquiry_id.hex)
    if row is None:
        raise HTTPException(404)
    request.state.target_subject_id = row.subject
    answer = data.answer.strip()
    if len(answer) < 2:
        raise HTTPException(422, "回答を入力してください")
    if row.answer is not None:
        if row.answer != answer:
            raise HTTPException(409, "すでに回答済みです")
        return result(row)
    row.answer, row.answered_at = answer, now()
    db.commit()
    return result(row)
