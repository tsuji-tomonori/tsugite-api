# API Gatewayから渡された認証情報を検証する。
"""HTTP API request authorizer. The backend rechecks the grant before dispatch."""

import os
import secrets

from fastapi import HTTPException
from sqlalchemy.orm import Session
from tsugite_db.models import AccessLog, Event
from tsugite_db.session import engine

from app.apis.gateway import authorize, invocation_asset, operation_template
from app.apis.governance.keys import invocation_actor
from app.core.credential_policy import check_operation
from app.core.diagnostics import InvocationTimer, OperationalRepair, asset_object, emit
from app.core.log_record import INVOKE_ROUTE
from app.core.workspace import attribute, private_project, retired_units


def handler(event, context):
    ctx = event.get("requestContext", {})
    fields = {
        "source": "authorizer",
        "method": ctx.get("http", {}).get("method", "GET"),
        "route": INVOKE_ROUTE,
        "request_id": ctx.get("requestId") or getattr(context, "aws_request_id", None),
        "screen": event.get("headers", {}).get("x-tsugite-screen"),
    }
    try:
        result = authorize_event(event, fields)
    except Exception as exc:
        fields.update(failed=True, reason=type(exc).__name__)
        emit("invoke.authorization", **fields)
        raise
    if not result["isAuthorized"]:
        fields.setdefault("reason", "authorization_denied")
        emit("invoke.authorization", status=403, **fields)
    return result


def authorize_event(event, fields):
    timer = InvocationTimer()
    headers = event.get("headers", {})
    if not secrets.compare_digest(headers.get("x-tsugite-origin", ""), os.environ["ORIGIN_SECRET"]):
        return {"isAuthorized": False}
    scheme, _, token = headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer":
        return {"isAuthorized": False}
    parts = event.get("rawPath", "").split("/", 6)
    if len(parts) < 6 or parts[1:3] != ["api", "invoke"]:
        return {"isAuthorized": False}
    key, environment, project = parts[3:6]
    with Session(engine()) as db:
        try:
            actor = invocation_actor(db, token, headers)
            fields["actor_id"] = actor.subject
        except HTTPException as exc:
            if exc.status_code >= 500:
                fields.update(failed=True, reason="authentication_service_error")
            return {"isAuthorized": False}
        project = retired_units(db).get(project, project)
        asset = None
        try:
            asset = invocation_asset(db, key)
            fields["asset_id"] = asset.id
            authorize(db, asset, project, environment, actor)
            method = event["requestContext"].get("http", {}).get("method", "GET").upper()
            pattern = (
                operation_template(asset_object(asset, "spec"), method, "/" + parts[6])
                if len(parts) > 6
                else None
            )
            fields["operation"] = pattern
            if pattern:
                check_operation(db, asset, actor, method + " " + pattern, project)
        except HTTPException as exc:
            if isinstance(exc, OperationalRepair):
                fields.update(exc.fields)
            elif exc.status_code >= 500:
                fields.update(failed=True, reason="authorization_service_error")
            if asset:
                db.add(
                    Event(
                        actor=actor.subject,
                        asset_id=asset.id,
                        owner=asset.owner,
                        project=project if project in actor.projects else "",
                        environment=environment[:16],
                        action="invoke.denied",
                        detail=str(exc.status_code),
                        request_id=event["requestContext"]["requestId"],
                    )
                )
                attributed = (
                    project
                    if project in actor.projects or project == private_project(actor.subject)
                    else ""
                )
                attribute(db, event["requestContext"]["requestId"], actor, attributed)
                db.add(
                    AccessLog(
                        key_id=actor.key_id or None,
                        request_id=event["requestContext"]["requestId"],
                        actor=actor.subject,
                        owner=asset.owner,
                        asset_id=asset.id,
                        project=project if project in actor.projects else "",
                        environment=environment[:16],
                        method=event["requestContext"].get("http", {}).get("method", ""),
                        operation=fields.get("operation") or "",
                        **timer.finish(
                            "authorizer",
                            fields["screen"],
                            403,
                            reason=fields.get("reason", "authorization_denied"),
                            action=fields.get("action"),
                            failed=fields.get("failed", False),
                        ),
                        status=403,
                    )
                )
                db.commit()
            return {"isAuthorized": False}
    return {"isAuthorized": True, "context": {"subject": actor.subject, "project": project}}
