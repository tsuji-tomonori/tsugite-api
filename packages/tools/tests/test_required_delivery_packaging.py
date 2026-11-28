"""配布物の契約を、小さな入力ファイルと一時ディレクトリで検証する。"""

import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path
from unittest.mock import Mock
from zipfile import ZipFile

import boto3
import pytest
from botocore.exceptions import ClientError

from packages.tools.packaging import build_backend, build_chat, build_frontend


def put(root, name, content):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


DECISION_FILES = {"model.onnx": b"quantized-weights", "tokenizer.json": b'{"model":"fixture"}'}


def fixture_manifest():
    return {
        "decision": [
            {
                "name": name,
                "repo": "example/ruri",
                "revision": "pinned-version",
                "file": name,
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            for name, payload in DECISION_FILES.items()
        ],
        "tool": [],
        "generate": [],
    }


def curl_fixture(command, content):
    output_flag = next(flag for flag in ("-o", "--output") if flag in command)
    Path(command[command.index(output_flag) + 1]).write_bytes(content)


@pytest.fixture
def distribution_root(tmp_path, monkeypatch):
    models = tmp_path / "packages/model/src"
    for name in ("decision.py", "completion.py", "model_runtime.py"):
        put(models, name, name.encode())
    put(models, "manifest.json", json.dumps(fixture_manifest()).encode())
    put(tmp_path, "packages/model/licenses/ruri-Apache-2.0.txt", b"ruri fixture license")

    for path in (
        "packages/agent/src/agent/retrieval.py",
        "packages/sample_api/src/sample_api/handler.py",
        "packages/backend/src/app/main.py",
        "packages/backend/src/app/core/log_record.py",
        "packages/database/src/tsugite_db/models.py",
        "packages/database/migrations/versions/v007_inquiries.py",
        "packages/database/alembic.ini",
        "packages/frontend/src/web_app/content/guide_content.py",
        "packages/frontend/src/web_app/content/guide_search.py",
    ):
        put(tmp_path, path, Path(path).name.encode())
    monkeypatch.setattr(build_backend, "ROOT", tmp_path)
    monkeypatch.setattr(build_chat, "ROOT", tmp_path)
    monkeypatch.setattr(build_chat, "BUILD", tmp_path / "build")
    monkeypatch.setattr(build_chat, "MODELS", models)
    return tmp_path


def test_backend_build_includes_migrations_and_reproducible_layers(distribution_root, monkeypatch):
    """API配布物は移行とガイドを含み、固定依存から作る四つのLayerは再ビルドしても一致する。"""
    root = distribution_root
    versions = {}

    def uv(command, **options):
        assert options["check"]
        if "export" in command:
            assert "--locked" in command
            Path(command[command.index("-o") + 1]).write_text("example==1\n")
        else:
            assert "--require-hashes" in command
            requirements = Path(command[-1])
            assert requirements.read_text() == "example==1\n"
            versions[requirements.stem] = command[command.index("--python-version") + 1]
            destination = Path(command[command.index("--target") + 1])
            put(destination, "example/__init__.py", requirements.stem.encode())
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", uv)
    build_backend.build()
    out = root / "build"
    package = out / "lambda"
    for name in (
        "app/main.py",
        "alembic.ini",
        "migrations/versions/v007_inquiries.py",
        "tsugite_db/models.py",
        "agent/retrieval.py",
        "packages/frontend/src/web_app/content/guide_content.py",
    ):
        assert (package / name).read_bytes() == Path(name).name.encode()
    assert versions == {
        "runtime": "3.15",
        "sample-api": "3.15",
        "decision-model": "3.14",
        "model-sdk": "3.15",
    }
    archives = {}
    for name in versions:
        layer = out / f"{name}-layer.zip"
        with ZipFile(layer) as archive:
            assert archive.read("python/example/__init__.py") == name.encode()
        archives[layer] = layer.read_bytes()
    build_backend.build()
    for layer, original in archives.items():
        assert layer.read_bytes() == original


def test_model_package_pins_native_server_and_carries_its_license(distribution_root, monkeypatch):
    """ビルドは判定資材を専用Layerに収め、生成関数の配布物にはサーバーとそのライセンスを同梱する。"""
    root = distribution_root
    (root / "build").mkdir()
    for layer in ("decision-model", "model-sdk"):
        with ZipFile(root / "build" / f"{layer}-layer.zip", "w") as archive:
            archive.writestr("python/example.py", "")

    def build_command(args, **options):
        if args[0] == "curl":
            url = next(arg for arg in args if arg.startswith("https://"))
            assert "/resolve/pinned-version/" in url
            curl_fixture(args, DECISION_FILES[url.rsplit("/", 1)[-1]])
        elif "clone" in args:
            put(Path(args[-1]), "LICENSE", b"upstream license")
        elif "--build" in args:
            put(Path(args[args.index("--build") + 1]), "bin/llama-server", b"test server").chmod(0o755)
        return subprocess.CompletedProcess(args, 0, stdout=build_chat.LLAMA_COMMIT + "\n")

    monkeypatch.setattr(subprocess, "run", build_command)
    build_chat.build()
    decision = root / "build/chat-decision"
    generation = root / "build/chat-llm"
    assert (decision / "decision.py").read_bytes() == b"decision.py"
    assert (generation / "completion.py").read_bytes() == b"completion.py"
    assert (generation / "llama-server").read_bytes() == b"test server"
    assert any(
        path.read_bytes() == b"upstream license" for path in generation.iterdir() if path.is_file()
    )
    assert set(json.loads((generation / "manifest.json").read_text())) == {"tool", "generate"}
    with ZipFile(root / "build/decision-weights-layer.zip") as archive:
        assert archive.read("models/decision/LICENSE") == b"ruri fixture license"
        for name, payload in DECISION_FILES.items():
            assert archive.read("models/decision/" + name) == payload
    with ZipFile(root / "build/decision-model-layer.zip") as dependencies:
        assert not any(name.startswith("models/") for name in dependencies.namelist())


def test_model_package_rejects_unexpected_source_revision(distribution_root, monkeypatch):
    """取得したコミットが固定版と異なる場合は生成サーバーを配布物に含めない。"""
    runner = Mock(return_value=subprocess.CompletedProcess([], 0, stdout="0" * 40 + "\n"))
    monkeypatch.setattr(subprocess, "run", runner)
    with pytest.raises((RuntimeError, ValueError), match="(?i)llama|commit|revision"):
        build_chat.build()
    assert not (distribution_root / "build/chat-llm/llama-server").exists()
    assert all(call.args[0][0] != "cmake" for call in runner.call_args_list)


@pytest.fixture
def model_storage(distribution_root, monkeypatch):
    payload = b"quantized test fixture"
    version = hashlib.sha256(payload).hexdigest()
    models = distribution_root / "packages/model/src"
    manifest = fixture_manifest()
    for role in ("tool", "generate"):
        manifest[role] = [
            {
                "repo": f"example/{role}",
                "revision": "20250101",
                "file": "weights.gguf",
                "name": "model.gguf",
                "sha256": version,
            }
        ]
    (models / "manifest.json").write_text(json.dumps(manifest))
    sts, s3 = Mock(), Mock()
    sts.get_caller_identity.return_value = {
        "Account": "123456789012",
        "Arn": "arn:aws:sts::123456789012:assumed-role/test/build",
    }
    sts.assume_role.return_value = {
        "Credentials": {"AccessKeyId": "test", "SecretAccessKey": "test", "SessionToken": "test"},
    }
    monkeypatch.setenv("AWS_REGION", "ap-northeast-1")
    monkeypatch.setattr(boto3, "client", lambda name, **kwargs: {"sts": sts, "s3": s3}[name])
    absent = ClientError({"Error": {"Code": "404", "Message": "Not found"}}, "HeadObject")
    s3.head_object.side_effect = absent
    return s3, payload, version


def test_model_publisher_reuses_identical_uploaded_version(model_storage, monkeypatch):
    """生成用の2モデルだけをS3へ送り、各モデルが同一版なら次の配備で再取得・再送信を省く。"""
    s3, payload, version = model_storage
    fetched = set()
    uploads = {}

    def fetch(command, *, check):
        assert check
        url = next(arg for arg in command if arg.startswith("https://"))
        fetched.add(url)
        curl_fixture(command, payload)

    def upload(source, bucket, key, *, ExtraArgs):
        assert Path(source).read_bytes() == payload
        assert "ap-northeast-1" in bucket
        uploads[key] = {"ContentLength": len(payload), "Metadata": ExtraArgs["Metadata"]}

    fetch_weight = Mock(side_effect=fetch)
    s3.upload_file.side_effect = upload
    monkeypatch.setattr(subprocess, "run", fetch_weight)
    build_chat.publish()
    assert fetched == {
        f"https://huggingface.co/example/{role}/resolve/20250101/weights.gguf"
        for role in ("tool", "generate")
    }
    assert set(uploads) == {
        f"tsugite-chat-models/{role}/{version}/model.gguf" for role in ("tool", "generate")
    }
    s3.head_object.side_effect = lambda *, Bucket, Key: uploads[Key]
    s3.upload_file.reset_mock()
    fetch_weight.reset_mock()
    build_chat.publish()
    s3.upload_file.assert_not_called()
    fetch_weight.assert_not_called()


def test_model_publisher_rejects_damaged_weights(model_storage, monkeypatch):
    """ダウンロードした重みが公表済みチェックサムに一致しなければアップロードしない。"""
    s3, _, _ = model_storage

    def damaged(command, **options):
        curl_fixture(command, b"incomplete")

    monkeypatch.setattr(subprocess, "run", damaged)
    with pytest.raises((RuntimeError, ValueError), match="(?i)hash|checksum|sha256|一致"):
        build_chat.publish()
    s3.upload_file.assert_not_called()


def test_screen_assets_preserve_nested_imports_and_style_order(tmp_path):
    """階層化された画面と補助モジュールを同じパスで配信し、画面CSSを共通CSSの後に置く。"""
    source, dist = tmp_path / "web_app", tmp_path / "dist"
    put(source, "portal_pages/reports.py", b"from . import _format\n")
    put(source, "portal_pages/_format.py", b"# helper\n")
    put(source, "portal_pages/reports.css", b".reports { color: navy; }")
    put(dist, "ui.css", b".common { color: black; }\n")
    files = build_frontend.copy_app_modules(source, dist)
    build_frontend.bundle_styles(source, dist)
    for path in ("portal_pages/reports.py", "portal_pages/_format.py"):
        assert (dist / path).read_bytes() == (source / path).read_bytes()
        assert f"/{path}" in files
    assert (dist / "ui.css").read_text().index(".common") < (dist / "ui.css").read_text().index(
        ".reports"
    )


def test_frontend_build_serves_runtime_locally_and_reuses_verified_assets(tmp_path, monkeypatch):
    """SPAの設定・画面・ブラウザー実行環境を同じ配信元に配置し、再ビルドでは検証済み資材を使う。"""
    frontend = tmp_path / "packages/frontend"
    put(frontend, "public/index.html", b'<script src="/vendor/pyscript/core.js"></script>')
    put(frontend, "public/ui.css", b".common {}")
    put(frontend, "src/web_app/app.py", b"# app")
    put(frontend, "src/web_app/portal_pages/stock.py", b"# stock")
    put(tmp_path, "packages/backend/src/app/core/log_record.py", b"# log")
    put(tmp_path, "deploy/config/http.toml", b'api_prefix = "/internal-api"\n')
    dist = frontend / "dist"
    monkeypatch.setattr(build_frontend, "ROOT", tmp_path)
    monkeypatch.setattr(build_frontend, "DIST", dist)
    monkeypatch.setattr(build_frontend, "CACHE", tmp_path / "cache")
    entries = {
        "pyscript": ["dist/core.js"],
        "pyodide": ["pyodide.mjs", "pyodide.asm.wasm", "python_stdlib.zip"],
        "cloudscape-fonts": ["fonts.css", "fonts/open-sans.woff2"],
        "cloudscape": ["index.css"],
    }
    archives = {}
    bundles = {}
    for package, files in entries.items():
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:gz") as tar:
            for filename in files:
                content = f"fixture for {filename}".encode()
                item = tarfile.TarInfo("package/" + filename)
                item.size = len(content)
                tar.addfile(item, io.BytesIO(content))
        url = f"https://vendor.example.test/{package}.tgz"
        archives[url] = data.getvalue()
        bundles[package] = (url, hashlib.sha256(data.getvalue()).hexdigest())
    monkeypatch.setattr(build_frontend, "BUNDLES", bundles)

    def download(command, *, check):
        assert check
        url = next(url for url in archives if url in command)
        Path(command[command.index("-o") + 1]).write_bytes(archives[url])

    fetch = Mock(side_effect=download)
    monkeypatch.setattr(subprocess, "run", fetch)
    build_frontend.build()
    assert fetch.call_count == len(entries)
    config = json.loads((dist / "pyscript.json").read_bytes())
    assert (dist / config["interpreter"].lstrip("/")).is_file()
    assert "/portal_pages/stock.py" in config["files"]
    assert json.loads((dist / "entry.json").read_bytes()) == {"api_prefix": "/internal-api"}
    assert (dist / "vendor/pyscript/core.js").read_bytes() == b"fixture for dist/core.js"
    assert (dist / "vendor/pyodide/pyodide.asm.wasm").is_file()
    assert (dist / "vendor/puepy/LICENSE").stat().st_size > 0
    assert config["files"]["/vendor/segno/encoder.py"] == "./segno/encoder.py"
    assert (dist / "vendor/segno/LICENSE").stat().st_size > 0
    build_frontend.build()
    assert fetch.call_count == len(entries)


@pytest.mark.parametrize(
    "damaged",
    [
        pytest.param(
            "model.onnx",
            marks=pytest.mark.case_detail("判定モデルの重みが固定ハッシュと異なる場合は配布を止める"),
        ),
        pytest.param(
            "tokenizer.json",
            marks=pytest.mark.case_detail("トークナイザーだけが固定ハッシュと異なる場合も配布を止める"),
        ),
    ],
)
def test_decision_layer_rejects_each_damaged_input(distribution_root, monkeypatch, damaged):
    """判定用の重み・トークナイザーを個別に照合し、どちらかが破損していればLayerを完成させない。"""

    def fetch(command, *, check):
        assert check
        url = next(arg for arg in command if arg.startswith("https://"))
        name = url.rsplit("/", 1)[-1]
        curl_fixture(command, b"broken" if name == damaged else DECISION_FILES[name])

    monkeypatch.setattr(subprocess, "run", fetch)
    with pytest.raises((RuntimeError, ValueError), match="(?i)hash|checksum|sha256|一致"):
        build_chat.build_decision_weights()
    assert not (distribution_root / "build/decision-weights-layer.zip").exists()
