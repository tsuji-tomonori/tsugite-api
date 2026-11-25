# メール補完はドライランで保存せず、確認したsubだけのメールを更新し氏名を保持する。
from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from tsugite_db.models import Base, Member, MemberProfile, now

from packages.tools.operations.sync_member_emails import sync


def record(subject, email=None, *, listed=True):
    attrs = [{"Name": "sub", "Value": subject}]
    if email is not None:
        attrs.append({"Name": "email", "Value": email})
    return {"Enabled": True, "Username": subject, "Attributes" if listed else "UserAttributes": attrs}


def test_sync_uses_verified_subject_and_preserves_names():
    """メール補完はドライランで保存せず、確認したsubだけのメールを更新し氏名を保持する。"""
    with create_engine("sqlite://").connect() as database:
        Base.metadata.create_all(database)
        with Session(database) as db:
            db.add(
                MemberProfile(
                    subject="active",
                    full_name="高橋 美咲",
                    email="old@example.test",
                    email_synced_at=now(),
                )
            )
            db.add(
                Member(subject="deleted", username="deleted", project="", role="external", deleted=True)
            )
            db.commit()
        idp = Mock()
        idp.get_paginator.return_value.paginate.return_value = [
            {
                "Users": [
                    record("active", "old-guess@example.test"),
                    record("deleted", "ignore@example.test"),
                ]
            },
            {"Users": [record("external"), record("mismatch", "keep-private@example.test")]},
        ]
        answers = {
            "active": record("active", "new@example.test", listed=False),
            "external": record("external", listed=False),
            "mismatch": record("different-subject", "keep-private@example.test", listed=False),
        }
        idp.admin_get_user.side_effect = lambda Username, **_: answers[Username]
        assert sync(idp, database, "pool") == {"changed": 3, "current": 0, "skipped": 1}
        idp.admin_get_user.assert_not_called()
        with Session(database) as db:
            assert db.get(MemberProfile, "active").email == "old@example.test"
        assert sync(idp, database, "pool", apply=True) == {"changed": 2, "current": 0, "skipped": 2}
        idp.get_paginator.return_value.paginate.return_value[0]["Users"][0] = record(
            "active", "new@example.test"
        )
        assert sync(idp, database, "pool", apply=True) == {"changed": 0, "current": 2, "skipped": 2}
        with Session(database) as db:
            active = db.get(MemberProfile, "active")
            assert (active.email, active.full_name, active.revision) == (
                "new@example.test",
                "高橋 美咲",
                2,
            )
            assert db.get(MemberProfile, "external").email_synced_at is not None
            assert db.get(MemberProfile, "deleted") is None
            assert db.get(MemberProfile, "mismatch") is None
