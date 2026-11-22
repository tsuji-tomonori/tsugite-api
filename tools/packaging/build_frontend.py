"""Build a self-hosted PuePy distribution. Downloads are pinned by digest."""

import json
import shutil
import subprocess
import tarfile
import tomllib
from hashlib import sha256
from importlib.metadata import distribution
from importlib.util import find_spec
from pathlib import Path

from tinycss2 import parse_component_value_list

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "packages/frontend/dist"
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
    "cloudscape-fonts": (
        "https://registry.npmjs.org/@cloudscape-design/global-styles/-/global-styles-1.0.72.tgz",
        "2544913edab01735414143e23a596344da65f42733ca3129b0a1d3ac2b890510",
    ),
    "cloudscape": (
        "https://registry.npmjs.org/@cloudscape-design/design-tokens/-/design-tokens-3.0.119.tgz",
        "a71895b6c8a0e5f62a70b3969c4e8398d583a9568b83a544579b9be051bd7a48",
    ),
}


def cloudscape_tokens(css):
    """Read var() references, including references inside nested functions and fallbacks."""
    names = set()
    pending = parse_component_value_list(css, skip_comments=True)
    while pending:
        token = pending.pop()
        if token.type == "function":
            args = token.arguments
            if token.lower_name == "var":
                first = next((arg for arg in args if arg.type != "whitespace"), None)
                if first and first.type == "ident" and first.value.startswith("--cs-"):
                    names.add(first.value.removeprefix("--cs-"))
            pending.extend(args)
        elif token.type in {"() block", "[] block", "{} block"}:
            pending.extend(token.content)
    return sorted(names)


def write_theme(definitions):
    """Resolve only the official tokens that the Python portal's stylesheet consumes."""
    names = cloudscape_tokens((DIST / "ui.css").read_text(encoding="utf-8"))
    tables = {"light": [], "dark": []}
    for name in names:
        value = definitions["tokens"][name]["$value"]
        for mode, table in tables.items():
            resolved = value if isinstance(value, str) else value.get(mode, value.get("comfortable"))
            if not isinstance(resolved, str):
                raise ValueError(f"Cloudscape token has no value for {name}/{mode}")
            table.append(f"  --cs-{name}: {resolved};")
    light = "\n".join(tables["light"])
    dark = "\n".join(tables["dark"])
    (DIST / "cloudscape.css").write_text(
        f":root {{color-scheme:light;\n{light}\n}}\n"
        f':root[data-mode="dark"] {{color-scheme:dark;\n{dark}\n}}\n'
        f'@media(prefers-color-scheme:dark) {{ :root:not([data-mode="light"]) {{color-scheme:dark;\n{dark}\n}} }}\n'
    )


def build():
    CACHE.mkdir(parents=True, exist_ok=True)
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(ROOT / "packages/frontend/public", DIST)
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
                if name == "cloudscape" and path.name == "index-visual-refresh.json":
                    with tar.extractfile(member) as file:
                        write_theme(json.load(file))
                selected = (
                    name == "pyscript"
                    and path.parent == Path("package/dist")
                    or name == "pyodide"
                    and path.suffix in {".js", ".mjs", ".wasm", ".json", ".zip"}
                    or name == "cloudscape"
                    and path.name == "NOTICE"
                    or name == "cloudscape-fonts"
                    and path.name in ("fonts.css", "NOTICE", "THIRD-PARTY-LICENSES.txt")
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
    wheel = distribution("puepy")
    for file in wheel.files or ():
        if file.name.upper() == "LICENSE":
            shutil.copy(wheel.locate_file(file), DIST / "vendor/puepy/LICENSE")
    for src in sorted((ROOT / "packages/frontend/src/web_app").glob("*.py")):
        shutil.copy(src, DIST / src.name)
        if src.name != "app.py":
            files["/" + src.name] = "./" + src.name
    (DIST / "pyscript.json").write_text(
        json.dumps({"interpreter": "/vendor/pyodide/pyodide.mjs", "files": files})
    )
    cfg = tomllib.loads((ROOT / "deploy/config/http.toml").read_text())
    (DIST / "entry.json").write_text(json.dumps(cfg))


if __name__ == "__main__":
    build()
