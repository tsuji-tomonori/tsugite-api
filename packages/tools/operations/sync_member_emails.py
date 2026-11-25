# Cognitoのメール属性をsubjectで照合し、所属一覧の表示用メールに反映する。
"""Cognitoのメール属性をsubjectで照合し、所属一覧の表示用メールに反映する。"""

import argparse
import os
from collections import Counter

import boto3
from app.core.config import settings
from app.core.member_profiles import set_directory_email
from sqlalchemy.orm import Session
from tsugite_db.models import Member, MemberProfile
from tsugite_db.session import engine


def attributes(record, key):
    return {field["Name"]: field["Value"] for field in record.get(key, [])}


def needs_sync(profile, email):
    return profile is None or profile.email_synced_at is None or profile.email != email


def sync(idp, database, pool_id, *, apply=False):
    counts = Counter(changed=0, current=0, skipped=0)
    pages = idp.get_paginator("list_users").paginate(UserPoolId=pool_id)
    for page in pages:
        for user in page.get("Users", []):
            observed = attributes(user, "Attributes")
            subject = observed.get("sub")
            if not subject or not user.get("Enabled"):
                counts["skipped"] += 1
                continue
            with Session(database) as db:
                member = db.get(Member, subject)
                profile = db.get(MemberProfile, subject)
                if member and member.deleted:
                    counts["skipped"] += 1
                    continue
                if not needs_sync(profile, observed.get("email") or None):
                    counts["current"] += 1
                    continue
            if not apply:
                counts["changed"] += 1
                continue
            try:
                confirmed = idp.admin_get_user(UserPoolId=pool_id, Username=user["Username"])
            except idp.exceptions.UserNotFoundException:
                counts["skipped"] += 1
                continue
            actual = attributes(confirmed, "UserAttributes")
            if not confirmed.get("Enabled") or actual.get("sub") != subject:
                counts["skipped"] += 1
                continue
            with Session(database) as db:
                member = db.get(Member, subject)
                if member and member.deleted:
                    counts["skipped"] += 1
                    continue
                profile = db.get(MemberProfile, subject)
                if profile is None:
                    profile = MemberProfile(subject=subject)
                    db.add(profile)
                if set_directory_email(profile, actual.get("email") or None):
                    db.commit()
                    counts["changed"] += 1
                else:
                    counts["current"] += 1
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="確認した差分を保存する。既定では件数だけを表示する"
    )
    args = parser.parse_args()
    if not os.getenv("DSQL_HOST") or not (pool_id := settings().get("pool_id")):
        parser.error("対象のDSQLとポータルのユーザープールを設定してください")
    counts = sync(boto3.client("cognito-idp"), engine(), pool_id, apply=args.apply)
    changed = "反映" if args.apply else "反映候補"
    print(
        f"{changed} {counts['changed']}件、差分なし {counts['current']}件、対象外 {counts['skipped']}件"
    )


if __name__ == "__main__":
    main()
