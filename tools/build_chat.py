"""Package native model functions and upload model weights directly to the CDK asset bucket."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "agent/models"
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
        for name in (entry, "runtime.py", "manifest.json"):
            shutil.copy2(MODELS / name, target)


def build():
    stage()
    decision = BUILD / "chat-decision"
    llm = BUILD / "chat-llm"
    subprocess.run(
        [
            "uv", "pip", "install", "--python-version", "3.14", "--python-platform",
            "x86_64-manylinux_2_34", "--only-binary", ":all:", "--target", str(decision),
            "onnxruntime==1.32.0", "numpy==2.4.0", "tokenizers==0.22.2",
        ],
        check=True,
    )
    source = BUILD / ("llama.cpp-" + LLAMA_RELEASE)
    if not source.exists():
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", LLAMA_RELEASE,
             "https://github.com/ggml-org/llama.cpp.git", str(source)],
            check=True,
        )
    head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if head != LLAMA_COMMIT:
        raise ValueError("Unexpected llama.cpp revision")
    out = BUILD / "llama-native"
    subprocess.run(
        [
            "cmake", "-S", str(source), "-B", str(out), "-DCMAKE_BUILD_TYPE=Release",
            "-DCMAKE_EXE_LINKER_FLAGS=-static", "-DBUILD_SHARED_LIBS=OFF",
            "-DGGML_NATIVE=OFF", "-DGGML_OPENMP=OFF", "-DGGML_LLAMAFILE=OFF",
            "-DLLAMA_OPENSSL=OFF", "-DLLAMA_BUILD_TESTS=OFF", "-DLLAMA_BUILD_SERVER=ON",
            "-DLLAMA_BUILD_UI=OFF", "-DLLAMA_USE_PREBUILT_UI=OFF",
        ],
        check=True,
    )
    subprocess.run(["cmake", "--build", str(out), "--target", "llama-server", "--parallel", "2"], check=True)
    shutil.copy2(out / "bin/llama-server", llm)
    shutil.copy2(source / "LICENSE", llm / "llama.cpp-LICENSE")
    subprocess.run([str(llm / "llama-server"), "--version"], check=True)
    for target in (decision, llm):
        if sum(path.stat().st_size for path in target.rglob("*") if path.is_file()) > 250 * 1024**2:
            raise ValueError(f"{target.name} exceeds the Lambda uncompressed package limit")


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
        "s3", region_name=region, aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"], aws_session_token=credentials["SessionToken"],
    )
    bucket = f"cdk-hnb659fds-assets-{account}-{region}"
    artifacts = json.loads((MODELS / "manifest.json").read_text(encoding="utf-8"))
    storage = BUILD / "model-weights"
    storage.mkdir(parents=True, exist_ok=True)
    for role, files in artifacts.items():
        for item in files:
            tag = item.get("sha256", item["revision"])
            key = f"tsugite-chat-models/{role}/{tag}/{item['name']}"
            try:
                if s3.head_object(Bucket=bucket, Key=key)["Metadata"].get("source") == tag:
                    continue
            except ClientError as exc:
                if exc.response["Error"]["Code"] not in ("403", "404", "NoSuchKey"):
                    raise
            dest = storage / f"{role}-{item['name']}"
            temporary = dest.with_suffix(".part")
            base = f"https://huggingface.co/{item['repo']}/resolve/{item['revision']}/"
            try:
                subprocess.run(
                    ["curl", "--fail", "--location", "--retry", "3", "--output", str(temporary),
                     base + item["file"]],
                    check=True,
                )
                if "sha256" in item:
                    with temporary.open("rb") as stream:
                        if hashlib.file_digest(stream, "sha256").hexdigest() != tag:
                            raise ValueError(f"Model checksum mismatch: {item['repo']}/{item['file']}")
                temporary.replace(dest)
                s3.upload_file(str(dest), bucket, key, ExtraArgs={"Metadata": {"source": tag}})
            finally:
                temporary.unlink(missing_ok=True)
