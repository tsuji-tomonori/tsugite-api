"""継手APIの起動・検証・AWS配備。リポジトリ直下のTaskfileから実行する。"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from build_backend import build as backend
from build_chat import build as chat
from build_chat import publish as publish_models
from build_frontend import build as frontend

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    local = commands.add_parser("demo", help="DBを更新し、127.0.0.1でローカルポータルを開く")
    local.add_argument("--port", type=int, default=8000)
    commands.add_parser("build", help="SPAとLambda向け配布物を作る")
    commands.add_parser("contracts", help="OpenAPIとテーブル定義をartifactsへ生成する")
    for name in ("synth", "deploy"):
        cmd = commands.add_parser(
            name, help="AWS CDKの" + ("合成" if name == "synth" else "配備とDB移行")
        )
        cmd.add_argument("--bindings", type=Path, help="プロジェクトと接続先を指定するJSONファイル")
        if name == "deploy":
            cmd.add_argument(
                "--require-approval",
                choices=("never", "any-change", "broadening"),
                help="CDKがデプロイ時に対話で承認を求める条件",
            )
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.command == "demo":
        os.environ["TSUGITE_DEMO"] = "1"
        frontend()
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "packages/database/alembic.ini", "upgrade", "head"],
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(args.port),
            ],
            check=True,
        )
    elif args.command == "contracts":
        from app.main import create_app
        from tsugite_db.design_names import design_tables, table_names

        out = Path("artifacts")
        out.mkdir(exist_ok=True)
        names = table_names()
        schema = {
            table.name: [
                {
                    "column": c.name,
                    "column_name_ja": names[table.name]["columns"][c.name],
                    "table_name_ja": names[table.name]["table"],
                    "record_name_ja": names[table.name]["record"],
                    "type": str(c.type),
                    "nullable": c.nullable,
                    "primary_key": c.primary_key,
                }
                for c in table.columns
            ]
            for table, _ in design_tables()
        }
        for name, data in (("openapi", create_app().openapi()), ("tables", schema)):
            (out / (name + ".json")).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    else:
        frontend()
        backend()
        chat()
        if args.command == "deploy":
            publish_models()
        if args.command != "build":
            cdk_args = ["-c", "bindings=" + str(args.bindings.resolve())] if args.bindings else []
            if args.command == "deploy" and args.require_approval:
                cdk_args.extend(["--require-approval", args.require_approval])
            subprocess.run(
                ["npx", "--yes", "--package", "aws-cdk@2.1149.0", "cdk", args.command, *cdk_args],
                cwd=ROOT / "packages/infra",
                check=True,
            )


if __name__ == "__main__":
    main()
