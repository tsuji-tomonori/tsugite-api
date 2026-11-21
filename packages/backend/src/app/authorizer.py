"""HTTP API request authorizer. The backend rechecks the grant before dispatch."""

import os
import secrets

from fastapi import HTTPException
from sqlalchemy.orm import Session
from tsugite_db.models import AccessLog, Asset, Event
from tsugite_db.session import engine

from app.apis.gateway import authorize
from app.apis.governance.keys import invocation_actor
from app.core.workspace import attribute, private_project


def handler(event, context):
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
        except HTTPException:
            return {"isAuthorized": False}
        try:
            authorize(db, key, project, environment, actor)
        except HTTPException as exc:
            asset = db.get(Asset, key)
            if asset:
                db.add(
                    Event(
                        actor=actor.subject,
                        asset_id=key,
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
                        asset_id=key,
                        project=project if project in actor.projects else "",
                        environment=environment[:16],
                        method=event["requestContext"].get("http", {}).get("method", ""),
                        operation="",
                        status=403,
                        duration_ms=0,
                    )
                )
                db.commit()
            return {"isAuthorized": False}
    return {"isAuthorized": True, "context": {"subject": actor.subject, "project": project}}
