# 利用者の所属や権限を管理する。
import boto3
from app.core.auth import DEMO_GROUPS
from app.core.config import local_demo, settings
from app.core.diagnostics import OperationalRepair
from app.core.member_profiles import (
    NAME_FIELDS,
    directory_accounts,
    directory_fields,
    directory_profiles,
    forget_profile,
    set_directory_email,
)
from app.core.workspace import configured_projects, retired_units, units
from app.dependencies import DB, User
from app.schemas import outputs
from app.schemas.members import Invitation
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from tsugite_db.models import Event, Member, MemberProfile, new_id

router = APIRouter()


def projects(db=None):
    if db is not None:
        return sorted(k for k, u in units(db).items() if u["kind"] == "project")
    return sorted(configured_projects())


def administrator(actor):
    if not actor.admin:
        raise HTTPException(403, "管理者の権限が必要です")


def member_event(db, request, actor, action, subject, detail):
    db.add(
        Event(
            actor=actor.subject,
            target_subject=subject,
            owner="",
            project="",
            asset_id="",
            environment="",
            action=action,
            detail=detail,
            request_id=request.state.request_id,
        )
    )


def pool():
    return settings()["pool_id"]


#: ポータルの利用者を一覧する
@router.get("/members", responses={200: {"model": outputs.MemberPage}})
def list_members(
    actor: User,
    db: DB,
    #: 次のページの開始位置
    cursor: str = "",
    #: 取得件数の上限
    limit: int = Query(40, ge=1, le=60),
):
    administrator(actor)
    retired = retired_units(db)
    if local_demo():
        accounts = {m.subject: m for m in db.scalars(select(Member))}
        rows = [
            {"subject": key, "username": key, "role": key} for key in DEMO_GROUPS if key not in accounts
        ]
        rows.extend(
            {
                "subject": m.subject,
                "username": m.username,
                "role": m.role,
                "project": retired.get(m.project, m.project),
            }
            for m in accounts.values()
            if not m.deleted
        )
        next_cursor = ""
    else:
        try:
            idp = boto3.client("cognito-idp")
            #: 利用者・グループの管理（Cognitoユーザープール） / 利用者の一覧を取得
            page = idp.list_users(
                UserPoolId=pool(), Limit=limit, **({"PaginationToken": cursor} if cursor else {})
            )
        except ClientError, BotoCoreError:
            raise HTTPException(
                503, "利用者を確認できませんでした。時間をおいて再実行してください"
            ) from None
        users = {
            attrs["sub"]: user["Username"]
            for user in page.get("Users", [])
            if (attrs := {a["Name"]: a["Value"] for a in user["Attributes"]}).get("sub")
        }
        accounts = directory_accounts(db, users)
        rows = []
        for subject, username in users.items():
            entry = accounts.get(subject)
            rows.append(
                {
                    "subject": subject,
                    "username": username,
                    "role": entry.role if entry else "Cognito",
                    "project": retired.get(entry.project, entry.project) if entry else "",
                    "deleted": bool(entry and entry.deleted),
                }
            )
        next_cursor = page.get("PaginationToken", "")
    profiles = directory_profiles(db, (row["subject"] for row in rows))
    items = [
        {**row, **directory_fields(profiles.get(row["subject"]), accounts.get(row["subject"]))}
        for row in rows
    ]
    return {"items": items, "next": next_cursor, "projects": projects(db)}


def undo_invitation(username):
    try:
        idp = boto3.client("cognito-idp")
        #: 利用者・グループの管理（Cognitoユーザープール） / 招待に失敗した利用者を削除
        idp.admin_delete_user(UserPoolId=pool(), Username=username)
    except (BotoCoreError, ClientError) as exc:
        if isinstance(exc, ClientError) and exc.response["Error"]["Code"] == "UserNotFoundException":
            return
        raise OperationalRepair(
            "member_invitation_incomplete",
            "対象のCognito利用者とportal_membersの登録状態を照合する。招待失敗で残った利用者を確認して取り消し、再度招待する。",
        ) from exc


#: ポータルに利用者を招待する
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
            #: 利用者・グループの管理（Cognitoユーザープール） / 利用者を作成
            user = idp.admin_create_user(
                UserPoolId=pool(),
                Username=username,
                UserAttributes=[{"Name": "email", "Value": username}],
                DesiredDeliveryMediums=["EMAIL"],
            )["User"]
        except idp.exceptions.UsernameExistsException as exc:
            raise HTTPException(409, "登録済みです") from exc
        except (idp.exceptions.InternalErrorException, idp.exceptions.TooManyRequestsException):
            raise HTTPException(503, "招待サービスが一時的に利用できません。時間をおいて再実行してください") from None
        try:
            subject = next(a["Value"] for a in user["Attributes"] if a["Name"] == "sub")
            request.state.target_subject_id = subject
            if data.project in projects():
                #: 利用者・グループの管理（Cognitoユーザープール） / 利用者をグループに追加
                idp.admin_add_user_to_group(
                    UserPoolId=pool(),
                    Username=username,
                    GroupName=("own-" if data.role == "provider" else "use-") + data.project,
                )
        except Exception:
            #: 利用者・グループの管理（Cognitoユーザープール） / 利用者を削除
            undo_invitation(username)
            raise
    request.state.target_subject_id = subject
    db.add(Member(subject=subject, username=username, project=data.project, role=data.role))
    profile = MemberProfile(subject=subject, full_name=data.full_name, display_name=data.display_name)
    set_directory_email(profile, username)
    db.add(profile)
    member_event(db, request, actor, "member.add", subject, username)
    changed = [field for field in NAME_FIELDS if getattr(data, field) is not None]
    if changed:
        member_event(db, request, actor, "profile.invite_set", subject, ", ".join(changed))
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        if not local_demo() and not db.get(Member, subject):
            #: 利用者・グループの管理（Cognitoユーザープール） / 利用者を削除
            undo_invitation(username)
        raise
    return {"subject": subject, "username": username, **directory_fields(profile)}


#: ポータルの利用者を削除する
@router.delete("/members/{subject}", responses={200: {"model": outputs.Deleted}})
def remove_member(
    #: 対象利用者の識別子
    subject: str,
    #: 削除する利用者のログイン名
    username: str,
    request: Request,
    actor: User,
    db: DB,
):
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
            #: 利用者・グループの管理（Cognitoユーザープール） / 利用者の登録情報を取得
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
        forget_profile(db, subject)
        member_event(db, request, actor, "member.delete", subject, username)
        db.commit()
    if idp is not None:
        try:
            #: 利用者・グループの管理（Cognitoユーザープール） / 利用者を削除
            idp.admin_delete_user(UserPoolId=pool(), Username=username)
        except (ClientError, BotoCoreError) as exc:
            if (
                not isinstance(exc, ClientError)
                or exc.response["Error"]["Code"] != "UserNotFoundException"
            ):
                raise OperationalRepair(
                    "member_deletion_incomplete",
                    "対象利用者のsubとポータルの停止状態を照合し、ユーザー管理画面から同じ利用者の削除を再実行する。Cognito側でも削除されたことを確認する。",
                    detail="ポータル利用を停止しました。Cognitoの削除を再実行してください",
                ) from exc
    return {"deleted": True}
