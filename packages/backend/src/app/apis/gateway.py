# 利用権を確認し上流APIの操作を呼び出す。
import json
import re
from typing import Annotated

from app.apis.catalog.common import DB, event, record, right_id
from app.apis.governance.alerts import admit
from app.apis.governance.keys import invoker
from app.apis.schemas import Env
from app.core.auth import Actor, check_member
from app.core.credential_policy import check_operation
from app.core.diagnostics import InvocationTimer, OperationalRepair, asset_object
from app.core.openapi import path_items
from app.core.workspace import (
    allowed_audience,
    attribute,
    private_project,
    retired_units,
    stopped,
    workspace_targets,
)
from app.integrations.upstream import MAX_BODY, dispatch
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool
from tsugite_db.models import Access, AccessLog, AssetRoute, PortalKey

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


def invocation_asset(db, key):
    asset_id = db.scalar(select(AssetRoute.asset_id).where(AssetRoute.slug == key))
    return record(db, asset_id or key)


def authorize(db, asset, project, environment, actor):
    check_member(db, actor)
    if not actor.key_id and not actor.machine:
        raise HTTPException(403, "APIの呼び出しには有効な認証情報が必要です")
    if asset.suspended:
        raise HTTPException(403, "管理者がこのAPIへのアクセスを一時停止しています")
    grant = db.get(Access, right_id(asset.id, project, environment))
    if actor.key_id:
        k = db.get(PortalKey, actor.key_id)
        scopes = json.loads(k.scopes) if k else []
        if not k or k.revoked or k.project != project or (scopes and asset.id not in scopes):
            raise HTTPException(403, "このAPIはキーの対象外です")
    permitted = grant is not None and grant.status == "approved"
    if not permitted and not actor.machine and not actor.key_shared:
        own = db.get(Access, right_id(asset.id, project, environment, actor.subject))
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


#: 接続先APIに{method}リクエストを転送する
@router.api_route(
    "/invoke/{key}/{environment}/{project}/{tail:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
    openapi_extra={
        "x-design-proxy": True,
        "description": "転送先に登録されたOpenAPIの操作に従います。短期アクセストークン（tst_）、共有キー、または登録済みマシンクライアントのCognitoアクセストークンをBearerで渡します。短期トークンには追加のキーヘッダーを併用できません。本人限定キーを使う場合は本人のトークンとX-API-Key、ポータルで選択したキーを使う場合は本人のトークンとX-Tsugite-Key-Idを渡します。",
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
    #: 呼び出すAPIの識別名または従来の識別子
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
    timer = InvocationTimer()
    asset = invocation_asset(db, key)
    project = retired_units(db).get(project, project)
    member_project = (
        project if project in actor.projects or project == private_project(actor.subject) else ""
    )

    def log_result(status, **fields):
        attribute(db, request.state.request_id, actor, member_project)
        db.add(
            AccessLog(
                request_id=request.state.request_id,
                actor=actor.subject,
                owner=asset.owner,
                asset_id=asset.id,
                project=member_project,
                environment=environment,
                key_id=actor.key_id or None,
                method=request.method,
                operation=getattr(request.state, "operation", "") or "",
                status=status,
                **timer.finish("api", request.headers.get("x-tsugite-screen"), status, **fields),
            )
        )

    try:
        authorize(db, asset, project, environment, actor)
        path = "/" + tail
        request.state.operation = operation_template(asset_object(asset, "spec"), request.method, path)
        if request.state.operation is None:
            raise HTTPException(404, "OpenAPIに定義されていない操作です")
        check_operation(db, asset, actor, request.method + " " + request.state.operation, project)
        target_name = asset_object(asset, "targets").get(environment)
        binding = workspace_targets(db).get(target_name) if isinstance(target_name, str) else None
        if not binding or (binding.owner, binding.environment) != (asset.owner, environment):
            raise OperationalRepair(
                "invalid_target_binding",
                "対象APIのassets.targetsと配備済み接続先の所有者・環境を照合し、正しい接続設定を復元する。対象環境で呼び出しを確認する。",
                asset_id=asset.id,
                detail="接続先を利用できません",
            )
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
        log_result(exc.status_code, **(exc.fields if isinstance(exc, OperationalRepair) else {}))
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
