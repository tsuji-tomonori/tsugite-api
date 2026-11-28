# 個人の管理者権限を付与・剥奪する。
from app.apis.governance.members import administrator, member_event, portal_admins
from app.apis.governance.profiles import check_managed_identity, existing_account
from app.core.admin_roles import save_admins
from app.dependencies import DB, User
from app.schemas.errors import domain_errors
from app.schemas.members import AdminRole
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


#: 利用者の管理者ロールを更新する
@router.put("/members/{subject}/admin-role", responses={**domain_errors(403, 404, 409, 503)})
def update_admin_role(
    #: 対象利用者の識別子
    subject: str,
    data: AdminRole,
    request: Request,
    actor: User,
    db: DB,
) -> AdminRole:
    administrator(actor)
    check_managed_identity(subject, existing_account(db, subject))
    admins = portal_admins(db)
    if actor.subject not in admins:
        raise HTTPException(403, "管理者の権限が必要です")
    if data.admin == (subject in admins):
        return data
    if data.admin:
        admins.add(subject)
    else:
        if admins == {subject}:
            raise HTTPException(409, "先に別のユーザーへ管理者権限を付与してください")
        admins.remove(subject)
    save_admins(db, admins)
    member_event(db, request, actor, "admin.grant" if data.admin else "admin.revoke", subject, "")
    db.commit()
    return data
