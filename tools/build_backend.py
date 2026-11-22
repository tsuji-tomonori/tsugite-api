"""Package locked Linux wheels for the Lambda runtime without Docker."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    dest = ROOT / "build/lambda"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    requirements = ROOT / "build/runtime.txt"
    versions = requirements.with_name("runtime-versions.txt")
    subprocess.run(
        [
            "uv",
            "export",
            "--locked",
            "--package",
            "tsugite-backend",
            "--no-dev",
            "--no-emit-workspace",
            "--no-header",
            "--no-hashes",
            "-o",
            str(versions),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        check=True,
    )
    subprocess.run(
        [
            "uv",
            "pip",
            "compile",
            str(versions),
            "--python-version",
            "3.15",
            "--python-platform",
            "x86_64-manylinux_2_34",
            "--only-binary",
            ":all:",
            "--generate-hashes",
            "--output-file",
            str(requirements),
        ],
        check=True,
    )
    subprocess.run(
        [
            "uv",
            "pip",
            "--no-config",
            "install",
            "--target",
            str(dest),
            "--python-version",
            "3.15",
            "--python-platform",
            "x86_64-manylinux_2_34",
            "--only-binary",
            ":all:",
            "--require-hashes",
            "-r",
            str(requirements),
        ],
        check=True,
    )
    shutil.copytree(
        ROOT / "packages/backend/src/app", dest / "app", ignore=shutil.ignore_patterns("__pycache__")
    )
    shutil.copytree(
        ROOT / "packages/database/migrations",
        dest / "migrations",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copytree(
        ROOT / "packages/database/src/tsugite_db",
        dest / "tsugite_db",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copy(ROOT / "packages/database/alembic.ini", dest)
    shutil.copytree(
        ROOT / "agent",
        dest / "agent",
        ignore=shutil.ignore_patterns("__pycache__", "models", "README.md"),
    )
    guide_path = Path("packages/frontend/src/web_app")
    (dest / guide_path).mkdir(parents=True)
    for name in ("guide_content.py", "guide_search.py"):
        shutil.copy(ROOT / guide_path / name, dest / guide_path / name)
    for path in dest.rglob("__pycache__"):
        shutil.rmtree(path)


if __name__ == "__main__":
    build()
