from typing import Literal

import boto3
from app.apis import outputs
from app.apis.catalog.common import DB, User
from app.apis.schemas import Input
from app.core.auth import DEMO_GROUPS
from app.core.config import local_demo, settings
from app.core.workspace import configured_projects, units
from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from tsugite_db.models import Event, Member, new_id

router = APIRouter()


def projects(db=None):
    if db is not None:
        return sorted(k for k, u in units(db).items() if u["kind"] == "project")
    return sorted(configured_projects())


class Invitation(Input):
    email: str = Field(pattern=r"^[^\s@/]+@[^\s@/]+\.[^\s@/]+$", max_length=150)
    project: str
    role: Literal["consumer", "provider"]


def administrator(actor):
    if not actor.admin:
        raise HTTPException(403, "管理者の権限が必要です")


def member_event(db, request, actor, action, username):
    db.add(
        Event(
            actor=actor.subject,
            owner="",
            project="",
            asset_id="",
            environment="",
            action=action,
            detail=username,
            request_id=request.state.request_id,
        )
    )


def pool():
    return settings()["pool_id"]


@router.get("/members", responses={200: {"model": outputs.MemberPage}})
def list_members(actor: User, db: DB, cursor: str = "", limit: int = Query(40, ge=1, le=60)):
    administrator(actor)
    if local_demo():
        rows = [
            {"subject": key, "username": key, "role": key}
            for key in DEMO_GROUPS
            if not db.get(Member, key)
        ]
        rows.extend(
            {"subject": m.subject, "username": m.username, "role": m.role, "project": m.project}
            for m in db.scalars(select(Member).where(Member.deleted.is_(False)))
        )
        return {"items": rows, "next": "", "projects": projects(db)}
    idp = boto3.client("cognito-idp")
    page = idp.list_users(
        UserPoolId=pool(), Limit=limit, **({"PaginationToken": cursor} if cursor else {})
    )
    rows = []
    for user in page.get("Users", []):
        attrs = {a["Name"]: a["Value"] for a in user["Attributes"]}
        sub = attrs["sub"]
        entry = db.get(Member, sub)
        rows.append(
            {
                "subject": sub,
                "username": user["Username"],
                "role": entry.role if entry else "Cognito",
                "project": entry.project if entry else "",
                "deleted": bool(entry and entry.deleted),
            }
        )
    return {"items": rows, "next": page.get("PaginationToken", ""), "projects": projects(db)}


@router.post("/members", status_code=201, responses={201: {"model": outputs.Person}})
def invite(data: Invitation, request: Request, actor: User, db: DB):
    administrator(actor)
    if data.project not in projects(db):
        raise HTTPException(422, "有効なプロジェクトを選んでください")
    username = data.email.lower()
    if db.scalar(select(Member.subject).where(Member.username == username, Member.deleted.is_(False))):
        raise HTTPException(409, "登録済みです")
    subject = new_id()
    if not local_demo():
        idp = boto3.client("cognito-idp")
        try:
            user = idp.admin_create_user(
                UserPoolId=pool(),
                Username=username,
                UserAttributes=[{"Name": "email", "Value": username}],
                DesiredDeliveryMediums=["EMAIL"],
            )["User"]
        except idp.exceptions.UsernameExistsException as exc:
            raise HTTPException(409, "登録済みです") from exc
        try:
            subject = next(a["Value"] for a in user["Attributes"] if a["Name"] == "sub")
            if data.project in projects():
                idp.admin_add_user_to_group(
                    UserPoolId=pool(),
                    Username=username,
                    GroupName=("own-" if data.role == "provider" else "use-") + data.project,
                )
        except Exception:
            idp.admin_delete_user(UserPoolId=pool(), Username=username)
            raise
    db.add(Member(subject=subject, username=username, project=data.project, role=data.role))
    member_event(db, request, actor, "member.add", username)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        if not local_demo() and not db.get(Member, subject):
            boto3.client("cognito-idp").admin_delete_user(UserPoolId=pool(), Username=username)
        raise
    return {"subject": subject, "username": username}


@router.delete("/members/{subject}", responses={200: {"model": outputs.Deleted}})
def remove_member(subject: str, username: str, request: Request, actor: User, db: DB):
    administrator(actor)
    if subject == actor.subject:
        raise HTTPException(409, "自分自身は削除できません")
    row = db.get(Member, subject)
    if row and row.username != username:
        raise HTTPException(409)
    idp = None if local_demo() else boto3.client("cognito-idp")
    if idp is None:
        if not row and (subject != username or subject not in DEMO_GROUPS):
            raise HTTPException(404)
    else:
        try:
            user = idp.admin_get_user(UserPoolId=pool(), Username=username)
        except idp.exceptions.UserNotFoundException:
            if row and row.deleted:
                return {"deleted": True}
            raise HTTPException(404) from None
        if not any(a["Name"] == "sub" and a["Value"] == subject for a in user["UserAttributes"]):
            raise HTTPException(409, "利用者の識別子が変わっています")
    if not row:
        row = Member(subject=subject, username=username, project="", role="external")
        db.add(row)
    if not row.deleted:
        row.deleted = True
        member_event(db, request, actor, "member.delete", username)
        db.commit()
    if idp is not None:
        try:
            idp.admin_delete_user(UserPoolId=pool(), Username=username)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "UserNotFoundException":
                raise HTTPException(
                    503, "ポータル利用を停止しました。Cognitoの削除を再実行してください"
                ) from exc
    return {"deleted": True}
