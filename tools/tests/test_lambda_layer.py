import hashlib
from zipfile import ZipFile

from tools.build_backend import sync_layer


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
