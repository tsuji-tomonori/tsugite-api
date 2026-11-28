"""チャットの質問を受け付けて結果を返す。"""

import os
from threading import Lock
from uuid import UUID

from app.core import chat_jobs as jobs
from app.core.catalog import listing
from app.core.catalog_visibility import visible_collection
from app.core.chat_search import NO_MATCH, ask, manual_sources
from app.dependencies import DB, User
from app.schemas.chat import ChatGuide, ChatQuestion, ChatReceipt, ChatResult
from app.schemas.errors import domain_errors
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()
_local: dict[str, dict] = {}
_lock = Lock()


#: チャットの質問を受け付ける
@router.post("/chat", responses=domain_errors(429, 503), response_model=ChatReceipt, status_code=202)
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
@router.get("/chat", responses=domain_errors(404), response_model=ChatResult)
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
