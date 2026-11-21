"""Build a self-hosted PuePy distribution. Downloads are pinned by digest."""

import json
import shutil
import subprocess
import tarfile
import tomllib
from hashlib import sha256
from importlib.util import find_spec
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend/dist"
CACHE = ROOT / "build/vendor"
BUNDLES = {
    "pyscript": (
        "https://registry.npmjs.org/@pyscript/core/-/core-0.5.7.tgz",
        "fc4de6cccd05a17b36a0b02ea4b458c97415d0ce6796574b3a06d169c831bda1",
    ),
    "pyodide": (
        "https://registry.npmjs.org/pyodide/-/pyodide-0.27.7.tgz",
        "89d5d952675eb08e11286e52c7238f1248ce71726e896db9703e73bef23dc343",
    ),
    "tabler": (
        "https://registry.npmjs.org/@tabler/core/-/core-1.2.0.tgz",
        "ecd3fc94e0b4cb6cac420b28fe94bac27c84ce74a54f0d4818444d41b74ef01d",
    ),
}


def build():
    CACHE.mkdir(parents=True, exist_ok=True)
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(ROOT / "frontend/public", DIST)
    for name, (url, digest) in BUNDLES.items():
        archive = CACHE / (name + ".tgz")
        if not archive.exists() or sha256(archive.read_bytes()).hexdigest() != digest:
            subprocess.run(["curl", "-fsSL", "--retry", "3", url, "-o", str(archive)], check=True)
        if sha256(archive.read_bytes()).hexdigest() != digest:
            raise ValueError(f"配布物のハッシュが一致しません: {name}")
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                path = Path(member.name)
                if not member.isfile() or path.name.endswith(".map"):
                    continue
                selected = (
                    name == "pyscript"
                    and path.parent == Path("package/dist")
                    or name == "pyodide"
                    and path.suffix in {".js", ".mjs", ".wasm", ".json", ".zip"}
                    or name == "tabler"
                    and path.name == "tabler.min.css"
                )
                if selected or path.name.lower().startswith("license") and len(path.parts) == 2:
                    dest = DIST / "vendor" / name / path.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with dest.open("wb") as file:
                        shutil.copyfileobj(tar.extractfile(member), file)
    pyroot = Path(find_spec("puepy").origin).parent
    files = {}
    for src in sorted(pyroot.glob("*.py")):
        dest = DIST / "vendor/puepy" / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dest)
        files["/vendor/puepy/" + src.name] = "./puepy/" + src.name
    for src in sorted((ROOT / "frontend/src/web_app").glob("*.py")):
        shutil.copy(src, DIST / src.name)
        if src.name != "app.py":
            files["/" + src.name] = "./" + src.name
    (DIST / "pyscript.json").write_text(
        json.dumps({"interpreter": "/vendor/pyodide/pyodide.mjs", "files": files})
    )
    cfg = tomllib.loads((ROOT / "contracts/http.toml").read_text())
    (DIST / "entry.json").write_text(json.dumps(cfg))


if __name__ == "__main__":
    build()
