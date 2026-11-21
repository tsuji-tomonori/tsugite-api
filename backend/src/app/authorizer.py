"""HTTP API request authorizer. The backend rechecks the grant before dispatch."""

import os
import secrets

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.apis.gateway import authorize
from app.core.auth import identify
from app.db.models import Asset, Event
from app.db.session import engine


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
    try:
        actor = identify(token)
    except HTTPException:
        return {"isAuthorized": False}
    with Session(engine()) as db:
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
                db.commit()
            return {"isAuthorized": False}
    return {"isAuthorized": True, "context": {"subject": actor.subject, "project": project}}
