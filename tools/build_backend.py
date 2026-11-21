"""Package locked Linux wheels for the Lambda runtime without Docker."""
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def build():
    dest=ROOT/"build/lambda"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    requirements=ROOT/"build/runtime.txt"
    subprocess.run(["uv","export","--locked","--package","tsugite-backend","--no-dev","--no-emit-workspace",
                    "--no-header","-o",str(requirements)],cwd=ROOT,stdout=subprocess.DEVNULL,check=True)
    subprocess.run(["uv","pip","install","--target",str(dest),"--python-version","3.14",
                    "--python-platform","x86_64-manylinux_2_34","--only-binary",":all:","--require-hashes",
                    "-r",str(requirements)],check=True)
    shutil.copytree(ROOT/"backend/src/app",dest/"app",ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT/"backend/migrations",dest/"migrations",ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT/"backend/alembic.ini",dest)
    for path in dest.rglob("__pycache__"):
        shutil.rmtree(path)


if __name__=="__main__":
    build()
