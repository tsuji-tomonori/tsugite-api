import json
import re
from time import monotonic
from typing import Annotated

from app.apis.catalog.common import DB, event, record, right_id
from app.apis.governance.alerts import admit
from app.apis.governance.keys import invoker
from app.apis.schemas import Env
from app.core.auth import Actor, check_member
from app.core.config import targets
from app.core.credential_policy import check_operation
from app.core.openapi import path_items
from app.core.workspace import allowed_audience, attribute, private_project, stopped
from app.integrations.upstream import MAX_BODY, dispatch
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from tsugite_db.models import Access, AccessLog, PortalKey

router = APIRouter()


def operation_template(spec: dict, method: str, path: str) -> str | None:
    parts = path.split("/")[1:]
    if any(p in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_~.\-]*", p) for p in parts):
        return None
    # Prefer a literal OpenAPI path over a templated path.
    patterns = dict(path_items(spec))
    if path in patterns:
        return path if method.lower() in patterns[path] else None
    for template, ops in patterns.items():
        segments = template.split("/")[1:]
        if len(segments) == len(parts) and all(
            s == p or (p and re.fullmatch(r"\{[^{}]+\}", s)) for s, p in zip(segments, parts)
        ):
            return template if method.lower() in ops else None
    return None


def allowed_path(spec: dict, method: str, path: str) -> bool:
    return operation_template(spec, method, path) is not None


def authorize(db, key, project, environment, actor):
    check_member(db, actor)
    asset = record(db, key)
    if asset.suspended:
        raise HTTPException(403, "管理者がこのAPIへのアクセスを一時停止しています")
    grant = db.get(Access, right_id(key, project, environment))
    if actor.key_id:
        k = db.get(PortalKey, actor.key_id)
        scopes = json.loads(k.scopes) if k else []
        if not k or k.revoked or k.project != project or (scopes and key not in scopes):
            raise HTTPException(403, "このAPIはキーの対象外です")
    permitted = grant is not None and grant.status == "approved"
    if not permitted and not actor.machine and not actor.key_shared:
        own = db.get(Access, right_id(key, project, environment, actor.subject))
        permitted = own is not None and own.status == "approved"
    if (
        not permitted
        or (
            project not in actor.projects
            and (actor.machine or project != private_project(actor.subject))
        )
        or not allowed_audience(asset, actor)
        or stopped(db, actor, project)
    ):
        raise HTTPException(403, "この環境での利用が許可されていません")
    return asset


#: 接続先APIに{method}リクエストを転送する
@router.api_route(
    "/invoke/{key}/{environment}/{project}/{tail:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
    openapi_extra={
        "x-design-proxy": True,
        "description": "転送先に登録されたOpenAPIの操作に従います。短期アクセストークン（tst_）、共有キー、またはCognitoアクセストークンをBearerで渡します。短期トークンには追加のキーヘッダーを併用できません。本人限定キーを使う場合は本人のトークンとX-API-Key、ポータルで選択したキーを使う場合は本人のトークンとX-Tsugite-Key-Idを渡します。",
        "parameters": [
            {
                "in": "header",
                "name": key,
                "required": False,
                "schema": {"type": "string"},
                "description": desc,
            }
            for key, desc in [
                #: APIキーの秘密値
                ("X-API-Key", "キーの秘密値。X-Tsugite-Key-Idと排他。"),
                #: ポータルで選んだ認証情報の識別子
                ("X-Tsugite-Key-Id", "ポータルで選択したキーのID。X-API-Keyと排他。"),
                #: 送信するデータの形式
                ("Content-Type", "転送ボディのメディアタイプ。省略時はapplication/json。"),
            ]
        ],
    },
)
async def invoke(
    #: 呼び出すAPIの識別子
    key: str,
    #: 提供環境
    environment: Env,
    #: 利用プロジェクトの識別子
    project: str,
    #: 転送先の操作パス
    tail: str,
    request: Request,
    actor: Annotated[Actor, Depends(invoker)],
    db: DB,
):
    started = monotonic()
    asset = record(db, key)
    member_project = (
        project if project in actor.projects or project == private_project(actor.subject) else ""
    )

    def log_result(status):
        attribute(db, request.state.request_id, actor, member_project)
        db.add(
            AccessLog(
                request_id=request.state.request_id,
                actor=actor.subject,
                owner=asset.owner,
                asset_id=key,
                project=member_project,
                environment=environment,
                key_id=actor.key_id or None,
                method=request.method,
                operation=getattr(request.state, "operation", "") or "",
                status=status,
                duration_ms=round((monotonic() - started) * 1000),
            )
        )

    try:
        authorize(db, key, project, environment, actor)
        path = "/" + tail
        request.state.operation = operation_template(json.loads(asset.spec), request.method, path)
        if request.state.operation is None:
            raise HTTPException(404, "OpenAPIに定義されていない操作です")
        check_operation(db, asset, actor, request.method + " " + request.state.operation, project)
        binding = targets().get(json.loads(asset.targets).get(environment))
        if not binding or (binding.owner, binding.environment) != (asset.owner, environment):
            raise HTTPException(503, "接続先を利用できません")
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY:
                raise HTTPException(413, "送信サイズが上限を超えました")
        headers = {
            "content-type": request.headers.get("content-type", "application/json"),
            "x-tsugite-project": project,
            "x-tsugite-subject": actor.subject,
            "x-request-id": request.state.request_id,
        }
        admit(db, request, actor, asset, project, environment)
        event(db, request, actor, asset, "invoke.start", project, environment, request.method)
        db.commit()
        result = await run_in_threadpool(
            dispatch,
            binding,
            request.method,
            (asset.base_path or "") + path,
            request.url.query,
            bytes(body),
            headers,
        )
    except HTTPException as exc:
        event(
            db,
            request,
            actor,
            asset,
            "invoke.denied" if exc.status_code in (403, 429) else "invoke.error",
            member_project,
            environment,
            str(exc.status_code),
        )
        log_result(exc.status_code)
        db.commit()
        raise
    except Exception as exc:
        db.rollback()
        event(db, request, actor, asset, "invoke.error", member_project, environment, "502")
        log_result(502)
        db.commit()
        raise HTTPException(502, "接続先と通信できませんでした") from exc
    log_result(result.status_code)
    event(db, request, actor, asset, "invoke.end", project, environment, str(result.status_code))
    db.commit()
    return result
