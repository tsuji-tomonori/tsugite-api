# ロックした依存からバックエンドのLambda配布物を作る。
"""Package locked Linux wheels for the Lambda runtime without Docker."""

import csv
import io
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[3]


def sync_layer(requirements, archive, python_version="3.14"):
    """Sync hash-locked Lambda wheels and publish a reproducible python/ archive."""
    with TemporaryDirectory(dir=archive.parent) as directory:
        stage = Path(directory)
        target = stage / "python"
        subprocess.run(
            [
                "uv",
                "pip",
                "sync",
                "--no-config",
                "--no-cache",
                "--no-installer-metadata",
                "--link-mode",
                "copy",
                "--only-binary",
                ":all:",
                "--require-hashes",
                "--python-platform",
                "x86_64-manylinux_2_34",
                "--python-version",
                python_version,
                "--target",
                str(target.resolve()),
                str(requirements.resolve()),
            ],
            cwd=requirements.parent,
            env={**os.environ, "UV_COMPILE_BYTECODE": "0"},
            check=True,
        )
        output = stage / archive.name
        with ZipFile(output, "w") as layer:
            files = {
                path.relative_to(target).as_posix(): path
                for path in target.rglob("*")
                if path.is_file()
                and path.relative_to(target).parts[0]
                not in {"bin", "Scripts", ".lock", ".gitignore", "CACHEDIR.TAG"}
                and "__pycache__" not in path.relative_to(target).parts
                and path.suffix not in {".pyc", ".pyo"}
            }
            for name, path in sorted(files.items()):
                data = path.read_bytes()
                if path.name == "RECORD" and path.parent.suffix == ".dist-info":
                    # Generated console scripts have host-specific paths and hashes.
                    rows = csv.reader(io.StringIO(data.decode("utf-8")))
                    normalized = io.StringIO()
                    csv.writer(normalized, lineterminator="\n").writerows(
                        sorted(row for row in rows if row[0] in files)
                    )
                    data = normalized.getvalue().encode("utf-8")
                entry = ZipInfo("python/" + name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = 0o100755 << 16
                layer.writestr(entry, data, compress_type=ZIP_DEFLATED)
        os.replace(output, archive)


def build_layers():
    """Export each Lambda's runtime dependencies directly from the shared uv.lock."""
    build_dir = ROOT / "build"
    build_dir.mkdir(exist_ok=True)
    for name, python_version, selection in (
        ("runtime", "3.15", ["--package", "tsugite-backend", "--no-dev"]),
        ("decision-model", "3.14", ["--only-group", "decision-model"]),
        ("model-sdk", "3.14", ["--only-group", "model-sdk"]),
    ):
        requirements = build_dir / f"{name}.txt"
        subprocess.run(
            [
                "uv",
                "export",
                "--locked",
                *selection,
                "--no-emit-workspace",
                "--no-header",
                "-o",
                str(requirements),
            ],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            check=True,
        )
        sync_layer(requirements, build_dir / f"{name}-layer.zip", python_version)


def build():
    build_layers()
    dest = ROOT / "build/lambda"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
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
        ROOT / "packages/agent/src/agent",
        dest / "agent",
        ignore=shutil.ignore_patterns("__pycache__", "models"),
    )
    guide_path = Path("packages/frontend/src/web_app")
    (dest / guide_path).mkdir(parents=True)
    for name in ("guide_content.py", "guide_search.py"):
        shutil.copy(ROOT / guide_path / name, dest / guide_path / name)
    for path in dest.rglob("__pycache__"):
        shutil.rmtree(path)


if __name__ == "__main__":
    build()
