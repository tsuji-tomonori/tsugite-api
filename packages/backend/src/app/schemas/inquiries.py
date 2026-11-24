from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import Input


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
