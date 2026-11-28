"""標準属性と管理者が登録した属性を定義し、標準属性のキーを業務上の役割にも使う。"""

import json

from tsugite_db.models import DirectoryTree

PROJECT = "project"
DEPARTMENT = "department"
BUILTIN_FIELDS = {
    DEPARTMENT: {"key": DEPARTMENT, "label": "部署", "builtin": True, "public_values": True},
    PROJECT: {"key": PROJECT, "label": "プロジェクト", "builtin": True, "public_values": False},
}


def metadata_fields(db):
    row = db.get(DirectoryTree, "metadata")
    custom = json.loads(row.units) if row else {}
    return {**custom, **BUILTIN_FIELDS}


def parent_kind(kind):
    return DEPARTMENT if kind in BUILTIN_FIELDS else kind
