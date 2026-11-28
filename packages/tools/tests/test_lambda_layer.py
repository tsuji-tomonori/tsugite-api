"""同じ依存を別の場所で同期してもLayerが一致し、依存を更新したときだけ内容が変わる。"""

import hashlib
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from packages.tools.packaging import build_backend, build_chat
from packages.tools.packaging.build_backend import sync_layer


def locked_wheel(directory, version):
    name = f"layer_probe-{version}"
    wheel = directory / f"{name}-py3-none-any.whl"
    metadata = f"{name}.dist-info"
    files = {
        "layer_probe.py": f"VERSION = '{version}'\n",
        f"{metadata}/WHEEL": "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{metadata}/METADATA": f"Metadata-Version: 2.1\nName: layer-probe\nVersion: {version}\n",
        f"{metadata}/entry_points.txt": "[console_scripts]\nprobe = layer_probe:main\n",
    }
    files[f"{metadata}/RECORD"] = "".join(f"{path},,\n" for path in [*files, f"{metadata}/RECORD"])
    with ZipFile(wheel, "w") as package:
        for path, content in files.items():
            package.writestr(path, content)
    requirements = directory / "requirements.txt"
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    requirements.write_text(f"{wheel.name} --hash=sha256:{digest}\n", encoding="utf-8")
    return requirements


def test_layer_rebuild_is_reproducible(tmp_path, monkeypatch):
    """同じ依存を別の場所で同期してもLayerが一致し、依存を更新したときだけ内容が変わる。"""
    monkeypatch.setenv("UV_OFFLINE", "1")
    monkeypatch.setenv("UV_COMPILE_BYTECODE", "1")
    requirements = locked_wheel(tmp_path, "1.0")
    first = tmp_path / "runtime.zip"
    second = tmp_path / "other" / "runtime.zip"
    second.parent.mkdir()
    sync_layer(requirements, first)
    sync_layer(requirements, second)
    assert first.read_bytes() == second.read_bytes()
    with ZipFile(first) as layer:
        names = layer.namelist()
        assert "python/layer_probe.py" in names
        assert all(
            name.startswith(("python/layer_probe.py", "python/layer_probe-1.0.dist-info/"))
            for name in names
        )
        assert not any(
            name.endswith(("uv_cache.json", "INSTALLER", "direct_url.json", ".pyc")) for name in names
        )
    sync_layer(locked_wheel(tmp_path, "2.0"), second)
    assert first.read_bytes() != second.read_bytes()


def test_each_lambda_layer_exports_its_locked_dependencies(tmp_path, monkeypatch):
    """各Layerが対応する依存群をロックから取り出し、正しいPythonの版で同期する。"""
    monkeypatch.setattr(build_backend, "ROOT", tmp_path)
    exports = {}
    installs = {}

    def export(args, **kwargs):
        assert args[:3] == ["uv", "export", "--locked"]
        assert "--no-emit-workspace" in args and "--no-hashes" not in args
        assert kwargs["check"] and kwargs["cwd"] == tmp_path
        exports[args[-1]] = args[3 : args.index("--no-emit-workspace")]

    def install(requirements, archive, python_version):
        installs[archive.name] = (exports[str(requirements)], python_version)

    monkeypatch.setattr(build_backend.subprocess, "run", export)
    monkeypatch.setattr(build_backend, "sync_layer", install)
    build_backend.build_layers()
    assert installs == {
        "runtime-layer.zip": (["--package", "tsugite-backend", "--no-dev"], "3.15"),
        "sample-api-layer.zip": (["--package", "tsugite-sample-api", "--no-dev"], "3.15"),
        "decision-model-layer.zip": (
            ["--project", "packages/model/decision-model", "--no-dev"],
            "3.14",
        ),
        "model-sdk-layer.zip": (["--package", "tsugite-model", "--no-dev"], "3.15"),
    }


def test_model_package_limit_includes_all_uncompressed_layers(tmp_path, monkeypatch):
    """関数と2層の展開後サイズを合算し、上限の1バイト手前まで配備を許可する。"""
    monkeypatch.setattr(build_chat, "BUILD", tmp_path)
    target = tmp_path / "code"
    target.mkdir()
    layers = ["dependencies.zip", "weights.zip"]
    for name in layers:
        with ZipFile(tmp_path / name, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("content", bytes(1024))
    with (target / "handler").open("wb") as code:
        code.truncate(250 * 1024**2 - 2049)
        build_chat.check_package_size(target, layers)
        code.truncate(250 * 1024**2 - 2048)
        with pytest.raises(ValueError, match="package limit"):
            build_chat.check_package_size(target, layers)
