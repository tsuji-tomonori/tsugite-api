import json
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.apis.catalog import DB, event, record, right_id
from app.apis.schemas import Env
from app.core.auth import Actor, current
from app.core.config import targets
from app.db.models import Access
from app.integrations.upstream import MAX_BODY, dispatch

router=APIRouter()


def allowed_path(spec: dict,method: str,path: str) -> bool:
    parts=path.split("/")[1:]
    if any(p in {".",".."} or not re.fullmatch(r"[A-Za-z0-9_~.\-]*",p) for p in parts):
        return False
    # Prefer a literal OpenAPI path over a templated path.
    patterns=spec["paths"]
    if path in patterns:
        return method.lower() in patterns[path]
    for template,ops in patterns.items():
        segments=template.split("/")[1:]
        if len(segments)==len(parts) and all(s==p or (p and re.fullmatch(r"\{[^{}]+\}",s)) for s,p in zip(segments,parts)):
            return method.lower() in ops
    return False


def authorize(db,key,project,environment,actor):
    asset=record(db,key)
    grant=db.get(Access,right_id(key,project,environment))
    if project not in actor.projects or grant is None or grant.status!="approved":
        raise HTTPException(403,"この環境での利用が承認されていません")
    return asset


@router.api_route("/invoke/{key}/{environment}/{project}/{tail:path}",methods=["GET","POST","PUT","PATCH","DELETE"],include_in_schema=False)
async def invoke(key: str,environment: Env,project: str,tail: str,request: Request,
                 actor: Annotated[Actor,Depends(current)],db: DB):
    asset=record(db,key)
    member_project=project if project in actor.projects else ""
    try:
        authorize(db,key,project,environment,actor)
        path="/"+tail
        if not allowed_path(json.loads(asset.spec),request.method,path):
            raise HTTPException(404,"OpenAPIに定義されていない操作です")
        binding=targets().get(json.loads(asset.targets).get(environment))
        if not binding or (binding.owner,binding.environment)!=(asset.owner,environment):
            raise HTTPException(503,"接続先を利用できません")
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>MAX_BODY:
                raise HTTPException(413,"送信サイズが上限を超えました")
        headers={"content-type":request.headers.get("content-type","application/json"),
                 "x-tsugite-project":project,"x-tsugite-subject":actor.subject,
                 "x-request-id":request.state.request_id}
        event(db,request,actor,asset,"invoke.start",project,environment,request.method)
        db.commit()
        result=await run_in_threadpool(dispatch,binding,request.method,(asset.base_path or "")+path,request.url.query,bytes(body),headers)
    except HTTPException as exc:
        event(db,request,actor,asset,"invoke.denied" if exc.status_code==403 else "invoke.error",
              member_project,environment,str(exc.status_code))
        db.commit()
        raise
    except Exception as exc:
        db.rollback()
        event(db,request,actor,asset,"invoke.error",member_project,environment,"502")
        db.commit()
        raise HTTPException(502,"接続先と通信できませんでした") from exc
    event(db,request,actor,asset,"invoke.end",project,environment,str(result.status_code))
    db.commit()
    return result
