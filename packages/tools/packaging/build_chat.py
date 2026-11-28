"""モデル用Lambdaの配布物を作り、モデルの重みをCDKのアセット用バケットへ直接格納する。"""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[3]
MODELS = ROOT / "packages/model/src"
BUILD = ROOT / "build"
LLAMA_RELEASE = "b12246"
LLAMA_COMMIT = "78ffbaa18533c2ed51eab2ef5ae0702330efc3e9"


def stage():
    for label, entry in (("decision", "decision.py"), ("llm", "completion.py")):
        target = BUILD / ("chat-" + label)
        if target.resolve().parent != BUILD.resolve():
            raise ValueError(f"Unexpected build directory: {target}")
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        for name in (entry, "model_runtime.py"):
            shutil.copy2(MODELS / name, target)
        if label == "llm":
            manifest = json.loads((MODELS / "manifest.json").read_text())
            (target / "manifest.json").write_text(
                json.dumps({role: manifest[role] for role in ("tool", "generate")}), encoding="utf-8"
            )
        shutil.copy2(ROOT / "packages/backend/src/app/core/log_record.py", target)


def build():
    stage()
    decision = BUILD / "chat-decision"
    llm = BUILD / "chat-llm"
    source = BUILD / ("llama.cpp-" + LLAMA_RELEASE)
    if not source.exists():
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                LLAMA_RELEASE,
                "https://github.com/ggml-org/llama.cpp.git",
                str(source),
            ],
            check=True,
        )
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != LLAMA_COMMIT:
        raise ValueError("Unexpected llama.cpp revision")
    out = BUILD / "llama-native"
    subprocess.run(
        [
            "cmake",
            "-S",
            str(source),
            "-B",
            str(out),
            "-DCMAKE_BUILD_TYPE=Release",
            "-DCMAKE_EXE_LINKER_FLAGS=-static",
            "-DBUILD_SHARED_LIBS=OFF",
            "-DGGML_NATIVE=OFF",
            "-DGGML_OPENMP=OFF",
            "-DGGML_LLAMAFILE=OFF",
            "-DLLAMA_OPENSSL=OFF",
            "-DLLAMA_BUILD_TESTS=OFF",
            "-DLLAMA_BUILD_SERVER=ON",
            "-DLLAMA_BUILD_UI=OFF",
            "-DLLAMA_USE_PREBUILT_UI=OFF",
        ],
        check=True,
    )
    subprocess.run(
        ["cmake", "--build", str(out), "--target", "llama-server", "--parallel", "2"], check=True
    )
    shutil.copy2(out / "bin/llama-server", llm)
    shutil.copy2(source / "LICENSE", llm / "llama.cpp-LICENSE")
    subprocess.run([str(llm / "llama-server"), "--version"], check=True)
    build_decision_weights()
    check_package_size(decision, ["decision-model-layer.zip", "decision-weights-layer.zip"])
    check_package_size(llm, ["model-sdk-layer.zip"])


def check_package_size(target, layers):
    size = sum(path.stat().st_size for path in target.rglob("*") if path.is_file())
    for layer in layers:
        with ZipFile(BUILD / layer) as archive:
            size += sum(entry.file_size for entry in archive.infolist())
    print(f"{target.name} with layers: {size:,} bytes uncompressed")
    if size >= 250 * 1024**2:
        raise ValueError(f"{target.name} with its layers exceeds the Lambda package limit")


def download(item, dest):
    def digest(path):
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    if dest.exists() and digest(dest) == item["sha256"]:
        return
    url = f"https://huggingface.co/{item['repo']}/resolve/{item['revision']}/{item['file']}"
    with TemporaryDirectory(dir=dest.parent) as directory:
        temp = Path(directory) / dest.name
        subprocess.run(
            ["curl", "--fail", "--location", "--retry", "3", "-o", str(temp), url], check=True
        )
        if digest(temp) != item["sha256"]:
            raise ValueError(f"Model checksum mismatch: {item['repo']}/{item['file']}")
        temp.replace(dest)


def build_decision_weights():
    items = json.loads((MODELS / "manifest.json").read_text(encoding="utf-8"))["decision"]
    storage = BUILD / "model-weights"
    storage.mkdir(parents=True, exist_ok=True)
    files = {"LICENSE": MODELS.parent / "licenses/ruri-Apache-2.0.txt"}
    for item in items:
        path = storage / f"decision-{item['name']}"
        download(item, path)
        files[item["name"]] = path
    with TemporaryDirectory(dir=BUILD) as directory:
        archive = Path(directory) / "decision-weights-layer.zip"
        with ZipFile(archive, "w") as layer:
            for name, path in sorted(files.items()):
                info = ZipInfo(f"models/decision/{name}")
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                layer.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED)
        archive.replace(BUILD / archive.name)


def publish():
    import boto3
    from botocore.exceptions import ClientError

    sts = boto3.client("sts")
    identity = sts.get_caller_identity()
    account = identity["Account"]
    region = os.getenv("AWS_REGION") or boto3.Session().region_name
    if not region:
        raise ValueError("AWS_REGION is required")
    partition = identity["Arn"].split(":")[1]
    credentials = sts.assume_role(
        RoleArn=f"arn:{partition}:iam::{account}:role/cdk-hnb659fds-file-publishing-role-{account}-{region}",
        RoleSessionName="tsugite-chat-models",
    )["Credentials"]
    s3 = boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
    )
    bucket = f"cdk-hnb659fds-assets-{account}-{region}"
    artifacts = json.loads((MODELS / "manifest.json").read_text(encoding="utf-8"))
    storage = BUILD / "model-weights"
    storage.mkdir(parents=True, exist_ok=True)
    for role in ("tool", "generate"):
        for item in artifacts[role]:
            tag = item.get("sha256", item["revision"])
            key = f"tsugite-chat-models/{role}/{tag}/{item['name']}"
            try:
                if s3.head_object(Bucket=bucket, Key=key)["Metadata"].get("source") == tag:
                    continue
            except ClientError as exc:
                if exc.response["Error"]["Code"] not in ("403", "404", "NoSuchKey"):
                    raise
            dest = storage / f"{role}-{item['name']}"
            download(item, dest)
            s3.upload_file(str(dest), bucket, key, ExtraArgs={"Metadata": {"source": tag}})
