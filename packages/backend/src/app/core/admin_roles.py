"""初回割り当てから引き継いだ管理者の名簿を版管理する。"""

import json

from tsugite_db.models import DirectoryTree


def role_record(db):
    # 認可と変更で同じ版を使い、並行した権限変更・ユーザー削除を競合として扱う。
    if "admin_roles" not in db.info:
        db.info["admin_roles"] = db.get(DirectoryTree, "admin_roles")
    return db.info["admin_roles"]


def assigned_admins(db) -> set[str] | None:
    record = role_record(db)
    subjects = json.loads(record.units) if record else None
    return set(subjects) if subjects is not None else None


def save_admins(db, subjects: set[str] | None):
    payload = json.dumps(sorted(subjects) if subjects is not None else None)
    record = role_record(db)
    if record is None:
        record = DirectoryTree(id="admin_roles", units=payload)
        db.add(record)
        db.info["admin_roles"] = record
    else:
        record.units = payload
        record.revision += 1
