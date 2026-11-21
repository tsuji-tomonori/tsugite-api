"""継手APIの起動・検証・AWS配備。リポジトリ直下のTaskfileから実行する。"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from build_backend import build as backend
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
        from tsugite_db.models import Base

        out = Path("artifacts")
        out.mkdir(exist_ok=True)
        schema = {
            table.name: [
                {
                    "column": c.name,
                    "type": str(c.type),
                    "nullable": c.nullable,
                    "primary_key": c.primary_key,
                }
                for c in table.columns
            ]
            for table in Base.metadata.sorted_tables
        }
        for name, data in (("openapi", create_app().openapi()), ("tables", schema)):
            (out / (name + ".json")).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    else:
        frontend()
        backend()
        if args.command != "build":
            context = ["-c", "bindings=" + str(args.bindings.resolve())] if args.bindings else []
            subprocess.run(
                ["npx", "--yes", "--package", "aws-cdk@2.1149.0", "cdk", args.command, *context],
                cwd=ROOT / "packages/infra",
                check=True,
            )


if __name__ == "__main__":
    main()
