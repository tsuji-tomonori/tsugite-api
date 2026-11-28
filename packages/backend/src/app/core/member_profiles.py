"""アカウントの権限とは独立して、利用者のプロフィールを読み書きする。"""

import re
from collections.abc import Iterable
from itertools import batched

from sqlalchemy import select
from tsugite_db.models import Member, MemberProfile, now

INVITATION_EMAIL = r"^[^\s@/]+@[^\s@/]+\.[^\s@/]+$"
NAME_FIELDS = ("full_name", "display_name")


def directory_fields(row, account=None):
    if account and account.deleted:
        return dict(email=None, full_name=None, display_name=None)
    email = row.email if row else None
    if (
        (row is None or row.email_synced_at is None)
        and account
        and account.role in {"consumer", "provider", ""}
        and re.fullmatch(INVITATION_EMAIL, account.username)
    ):
        email = account.username
    return dict(
        email=email,
        full_name=row.full_name if row else None,
        display_name=row.display_name if row else None,
    )


def directory_profiles(db, subjects: Iterable[str]):
    return {
        row.subject: row
        for batch in batched(set(subjects), 500)
        for row in db.scalars(select(MemberProfile).where(MemberProfile.subject.in_(batch)))
    }


def directory_accounts(db, subjects: Iterable[str]):
    return {
        row.subject: row
        for batch in batched(set(subjects), 500)
        for row in db.scalars(select(Member).where(Member.subject.in_(batch)))
    }


def forget_profile(db, subject):
    row = db.get(MemberProfile, subject)
    if row is None:
        db.add(MemberProfile(subject=subject))
    else:
        for field in (*NAME_FIELDS, "email", "email_synced_at"):
            setattr(row, field, None)
        # Write even an empty profile to conflict with concurrent edits by this subject.
        row.revision += 1


def set_directory_email(row, email):
    if row.email_synced_at is not None and row.email == email:
        return False
    row.email, row.email_synced_at = email, now()
    return True
