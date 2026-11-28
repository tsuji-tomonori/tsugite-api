"""CDロールで、配備済みポータルの最初の管理者を招待する。"""

import argparse
import json
import os
import subprocess
from uuid import UUID


def aws(*args):
    # CLI の応答には個人情報が含まれるため、必要な値だけ呼び出し元に返す。
    result = subprocess.run(
        ["aws", *args, "--output", "json", "--no-cli-pager"],
        check=False,
        stdout=subprocess.PIPE,
        encoding="utf-8",
    )
    if result.returncode:
        raise SystemExit(f"AWS CLI の {args[1]} が失敗しました（終了コード {result.returncode}）。")
    return json.loads(result.stdout) if result.stdout.strip() else None


def pool_id():
    stack = aws("cloudformation", "describe-stacks", "--stack-name", "TsugiteApi")["Stacks"][0]
    return next(
        output["OutputValue"] for output in stack["Outputs"] if output["OutputKey"] == "UserPoolId"
    )


def has_admin(pool):
    result = aws(
        "cognito-idp",
        "list-users-in-group",
        "--user-pool-id",
        pool,
        "--group-name",
        "admin",
        "--max-items",
        "1",
    )
    return bool(result["Users"])


def invite(email):
    pool = pool_id()
    if has_admin(pool):
        print("管理者が登録済みのため、初回招待を終了しました。")
        return
    if not email or email != email.strip() or email.count("@") != 1:
        raise SystemExit("main Environment の BOOTSTRAP_ADMIN_EMAIL に招待先を設定してください。")
    user = aws(
        "cognito-idp",
        "admin-create-user",
        "--user-pool-id",
        pool,
        "--username",
        email.lower(),
        "--user-attributes",
        json.dumps([{"Name": "email", "Value": email}]),
        "--desired-delivery-mediums",
        "EMAIL",
    )["User"]
    subject = UUID(next(attr["Value"] for attr in user["Attributes"] if attr["Name"] == "sub"))
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        print(f"pool={pool}\nsubject={subject}", file=output)


def grant(pool, subject, email):
    if pool != pool_id():
        raise SystemExit("招待後にユーザープールが変更されました。")
    if has_admin(pool):
        print("管理者が登録済みのため、権限の付与を終了しました。")
        return
    user = aws("cognito-idp", "admin-get-user", "--user-pool-id", pool, "--username", email.lower())
    if not any(attr == {"Name": "sub", "Value": subject} for attr in user["UserAttributes"]):
        raise SystemExit("招待したユーザーと現在のユーザーの識別子が一致しません。")
    aws(
        "cognito-idp",
        "admin-add-user-to-group",
        "--user-pool-id",
        pool,
        "--username",
        email.lower(),
        "--group-name",
        "admin",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("invite", "grant"))
    if parser.parse_args().operation == "invite":
        invite(os.environ["BOOTSTRAP_ADMIN_EMAIL"])
    else:
        grant(
            os.environ["INVITED_POOL"],
            os.environ["INVITED_SUBJECT"],
            os.environ["BOOTSTRAP_ADMIN_EMAIL"],
        )
