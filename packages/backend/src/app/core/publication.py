"""公開申請と利用申請に共通する承認担当の判定。"""

import json

import boto3
from app.core.auth import DEMO_GROUPS
from app.core.config import local_demo, settings
from app.core.workspace import units
from app.schemas.catalog import PublicationPolicy
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException
from sqlalchemy import select
from tsugite_db.models import DirectoryTree, Member


def publication_policy(db):
    row = db.get(DirectoryTree, "publication")
    return (
        PublicationPolicy(**json.loads(row.units), revision=row.revision) if row else PublicationPolicy()
    )


def resolve_person(db, subject):
    member = db.get(Member, subject)
    if member is None and "@" in subject:
        member = db.scalar(
            select(Member).where(Member.username == subject.lower(), Member.deleted.is_(False))
        )
    if member and not member.deleted:
        return member.subject
    if member is None and local_demo() and subject in DEMO_GROUPS:
        return subject
    if member is None and not local_demo():
        # ポータルで招待されていない既存のCognitoアカウントも、承認時は不変のsubで照合する。
        idp = boto3.client("cognito-idp")
        field = "email" if "@" in subject else "sub"
        try:
            #: 利用者・グループの管理（Cognitoユーザープール） / 指名した利用者の識別子と有効状態を確認
            pages = idp.get_paginator("list_users").paginate(
                UserPoolId=settings()["pool_id"], Filter=field + " = " + json.dumps(subject)
            )
            candidates = {
                attr["Value"]
                for page in pages
                for user in page["Users"]
                if user.get("Enabled")
                for attr in user["Attributes"]
                if attr["Name"] == "sub"
            }
        except (BotoCoreError, ClientError) as exc:
            raise HTTPException(503, "利用者の登録状況を確認できませんでした") from exc
        if len(candidates) == 1:
            confirmed = candidates.pop()
            account = db.get(Member, confirmed)
            if not account or not account.deleted:
                return confirmed
    raise HTTPException(422, "有効な利用者を指定してください")


def validate_steps(db, steps):
    tree = units(db)
    resolved = []
    for step in steps:
        if step.startswith("unit/") and tree.get(step[5:], {}).get("kind") not in {
            "department",
            "project",
        }:
            raise HTTPException(422, "承認先の部署またはプロジェクトを確認してください")
        if step.startswith("person/"):
            step = "person/" + resolve_person(db, step[7:])
            if len(step) > 80:
                raise HTTPException(422, "承認者の識別子が長すぎます")
        resolved.append(step)
    return resolved


def assigned(step, actor, owner, departments):
    if step == "admin":
        return actor.admin
    if step == "project_leader":
        return owner in actor.leads
    if step == "provider":
        return owner in actor.owners
    if step == "department":
        return bool(actor.leads.intersection(departments))
    if step.startswith("unit/"):
        return step[5:] in actor.leads
    return step == "person/" + actor.subject


def reviewer(asset, actor):
    if not asset.publication_request:
        return False
    pending = json.loads(asset.publication_request)
    return actor.subject != pending["applicant"] and assigned(
        pending["remaining"][0], actor, asset.owner, pending["departments"]
    )
