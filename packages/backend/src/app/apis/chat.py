import os
from threading import Lock
from typing import Literal
from uuid import UUID

from app.apis.catalog.catalog.router import visible_collection
from app.apis.catalog.common import DB, User, listing
from app.apis.schemas import Input, Listing
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from agent import jobs
from agent.retrieval import NO_MATCH, ask, manual_sources

router = APIRouter()
_local: dict[str, dict] = {}
_lock = Lock()


#: チャットへの質問
class ChatQuestion(Input):
    #: チャットの受付識別子
    job_id: UUID
    #: 質問本文
    question: str = Field(min_length=2, max_length=400)


#: チャットの受付結果
class ChatReceipt(BaseModel):
    #: チャットの受付識別子
    job_id: UUID


#: 操作ガイドの検索結果
class ChatGuide(BaseModel):
    #: ガイドの識別子
    id: str
    #: ガイド名
    title: str
    #: 操作手順
    steps: list[str]
    #: 操作後の状態
    result: str


#: チャットの回答
class ChatResult(BaseModel):
    #: 回答の種類
    kind: Literal[
        #: 回答を作成中
        "pending",
        #: 商品検索
        "catalog",
        #: 操作ガイド
        "manual",
        #: 問い合わせ
        "contact",
        #: 該当なし
        "empty",
        #: 対象外
        "outside",
        #: 処理エラー
        "error",
    ]
    #: 回答本文
    answer: str = ""
    #: おすすめのAPI商品
    products: list[Listing] = Field(default_factory=list)
    #: 該当する操作ガイド
    guides: list[ChatGuide] = Field(default_factory=list)


#: チャットの質問を受け付ける
@router.post("/chat", response_model=ChatReceipt, status_code=202)
def start_chat(data: ChatQuestion, actor: User, db: DB, request: Request):
    question = data.question.strip()
    if len(question) < 2:
        raise HTTPException(422, "質問を入力してください")
    if os.getenv("CHAT_WORKER"):
        try:
            jobs.submit(
                question,
                actor,
                data.job_id,
                request.state.request_id,
                request.headers.get("x-tsugite-screen"),
            )
        except jobs.RateLimited as exc:
            raise HTTPException(429, "数秒待ってから送信してください") from exc
        except (BotoCoreError, ClientError) as exc:
            raise HTTPException(503, "チャットに接続できませんでした") from exc
    else:
        key = jobs.key_for(actor.subject, data.job_id)

        def model(role, data):
            return jobs.models(
                role,
                data,
                actor_id=actor.subject,
                request_id=request.state.request_id,
                screen=request.headers.get("x-tsugite-screen"),
            )

        result = ask(question, lambda: visible_collection(db, actor, spec=True), actor, model)
        with _lock:
            if len(_local) >= 200:
                _local.pop(next(iter(_local)))
            _local.setdefault(key, result)
    return ChatReceipt(job_id=data.job_id)


#: チャットの回答を取得する
@router.get("/chat", response_model=ChatResult)
def chat_result(
    #: チャットの受付識別子
    job_id: UUID,
    actor: User,
    db: DB,
):
    if os.getenv("CHAT_WORKER"):
        result = jobs.status(actor.subject, job_id)
    else:
        with _lock:
            result = _local.get(jobs.key_for(actor.subject, job_id))
    if result is None:
        raise HTTPException(404, "チャットの回答が見つかりません")
    if not result:
        return ChatResult(kind="pending")
    keys = result.get("keys", [])
    products = []
    guides = []
    if result["kind"] == "catalog":
        visible = {asset.id: asset for asset in visible_collection(db, actor, keys=keys)}
        products = [listing(visible[key]) for key in keys if key in visible]
    elif result["kind"] == "manual":
        sources = manual_sources(actor)
        guides = [
            ChatGuide(id=g.id, title=g.title, steps=list(g.steps), result=g.result)
            for key in keys
            if (g := sources.get(key))
        ]
    if keys and not (products or guides):
        return ChatResult(kind="empty", answer=NO_MATCH)
    answer = result["answer"]
    focus = result.get("focus")
    if guides and isinstance(focus, list) and len(focus) == 2:
        source, step = focus
        primary = next((guide for guide in guides if guide.id == source), guides[0])
        excerpts = [*primary.steps, primary.result]
        index = step if type(step) is int and 0 <= step < len(excerpts) else 0
        answer = excerpts[index]
    return ChatResult.model_validate(
        {"kind": result["kind"], "answer": answer, "products": products, "guides": guides}
    )
