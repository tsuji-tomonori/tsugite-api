"""View and edit the portal member's profile through the existing human session."""

import json

import boto3
from app.apis.governance.members import administrator, member_event, pool
from app.core.auth import DEMO_GROUPS
from app.core.config import local_demo
from app.core.member_profiles import NAME_FIELDS, directory_fields
from app.dependencies import DB, User
from app.schemas import outputs
from app.schemas.profiles import ProfileEdit
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, Request
from tsugite_db.models import Member, MemberProfile

router = APIRouter()


def existing_account(db, subject):
    account = db.get(Member, subject)
    if account and account.deleted:
        raise HTTPException(404, "利用者が見つかりません")
    return account


def check_managed_identity(subject, account):
    if local_demo():
        if account is None and subject not in DEMO_GROUPS:
            raise HTTPException(404, "利用者が見つかりません")
        return
    idp = boto3.client("cognito-idp")
    try:
        username = account.username if account else None
        if username is None:
            #: 利用者・グループの管理（Cognitoユーザープール） / 識別子で利用者を検索する
            matches = idp.list_users(UserPoolId=pool(), Filter="sub = " + json.dumps(subject))
            username = next((user["Username"] for user in matches.get("Users", [])), None)
        if username is None:
            raise HTTPException(404, "利用者が見つかりません")
        #: 利用者・グループの管理（Cognitoユーザープール） / 対象利用者の有効性を確認する
        target = idp.admin_get_user(UserPoolId=pool(), Username=username)
    except idp.exceptions.UserNotFoundException:
        raise HTTPException(404, "利用者が見つかりません") from None
    except BotoCoreError, ClientError:
        raise HTTPException(
            503, "利用者を確認できませんでした。時間をおいて再実行してください"
        ) from None
    if not target.get("Enabled") or not any(
        a["Name"] == "sub" and a["Value"] == subject for a in target.get("UserAttributes", [])
    ):
        raise HTTPException(404, "利用者が見つかりません")


def output(subject, profile, account):
    return {
        "subject": subject,
        **directory_fields(profile, account),
        "revision": profile.revision if profile else 0,
    }


def edit(db, request, actor, subject, account, data, action):
    request.state.target_subject_id = subject
    row = db.get(MemberProfile, subject)
    if data.revision != (row.revision if row else 0):
        raise HTTPException(409, "同時に更新されました。プロフィールを再読み込みしてください")
    changes = {
        field: getattr(data, field)
        for field in NAME_FIELDS
        if field in data.model_fields_set and getattr(data, field) != getattr(row, field, None)
    }
    if changes:
        if row is None:
            row = MemberProfile(subject=subject)
            db.add(row)
        for field, value in changes.items():
            setattr(row, field, value)
        member_event(db, request, actor, action, subject, ", ".join(changes))
        db.commit()
    return output(subject, row, account)


#: 本人の利用者プロフィールを取得する
@router.get("/me/profile", responses={200: {"model": outputs.MemberProfile}})
def my_profile(actor: User, db: DB):
    account = existing_account(db, actor.subject)
    return output(actor.subject, db.get(MemberProfile, actor.subject), account)


#: 本人の氏名と表示名を更新する
@router.patch("/me/profile", responses={200: {"model": outputs.MemberProfile}})
def update_my_profile(data: ProfileEdit, request: Request, actor: User, db: DB):
    account = existing_account(db, actor.subject)
    return edit(db, request, actor, actor.subject, account, data, "profile.self_update")


#: 管理者が指定した利用者のプロフィールを取得する
@router.get("/members/{subject}/profile", responses={200: {"model": outputs.MemberProfile}})
def managed_profile(
    #: 対象利用者の識別子
    subject: str,
    actor: User,
    db: DB,
):
    administrator(actor)
    account = existing_account(db, subject)
    check_managed_identity(subject, account)
    return output(subject, db.get(MemberProfile, subject), account)


#: 管理者が指定した利用者の氏名と表示名を更新する
@router.patch("/members/{subject}/profile", responses={200: {"model": outputs.MemberProfile}})
def update_managed_profile(
    #: 対象利用者の識別子
    subject: str,
    data: ProfileEdit,
    request: Request,
    actor: User,
    db: DB,
):
    administrator(actor)
    account = existing_account(db, subject)
    check_managed_identity(subject, account)
    return edit(db, request, actor, subject, account, data, "profile.admin_update")
