"""呼び出し主体と、呼び出し時に記録した組織の帰属から閲覧範囲を求める。"""

from sqlalchemy import or_, select
from tsugite_db.models import AccessLog, LogUnit


def led_calls(tree, leads):
    projects = [key for key in leads if tree.get(key, {}).get("kind") == "project"]
    departments = [key for key in leads if tree.get(key, {}).get("kind") == "department"]
    return or_(
        AccessLog.project.in_(projects),
        AccessLog.request_id.in_(select(LogUnit.request_id).where(LogUnit.unit_id.in_(departments))),
    )
