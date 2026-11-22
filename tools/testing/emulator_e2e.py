"""Start one isolated AWS Emulator, run the AWS E2E suite, then dispose of it."""

import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen


def main():
    binary = shutil.which(os.getenv("AWS_EMULATOR_BINARY", "aws-emulator"))
    if not binary:
        sys.exit("AWS Emulator をインストールしてください。")
    subprocess.run([binary, "--version"], check=True)
    with tempfile.TemporaryDirectory(prefix="tsugite-emulator-") as folder:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        endpoint = f"https://127.0.0.1:{port}"
        profile = Path(folder) / ".aws" / "emulator" / str(port)
        ca = str(profile / "ca.pem")
        env = {k: v for k, v in os.environ.items() if not k.startswith(("AWS_", "EMULATOR_"))}
        for key in (
            "DATABASE_URL",
            "DSQL_HOST",
            "DSQL_USER",
            "HUB_SETTINGS_FILE",
            "HUB_SETTINGS_PARAMETER",
            "TSUGITE_DEMO",
        ):
            env.pop(key, None)
        env.update(HOME=folder, NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
        process = subprocess.Popen(
            [binary, "--telemetry", "off", "--auth", "on", "-p", str(port)], env=env
        )
        try:
            for _ in range(150):
                if process.poll() is not None:
                    raise RuntimeError("AWS Emulator が起動中に終了しました")
                try:
                    with urlopen(
                        endpoint + "/__admin/health",
                        timeout=1,
                        context=ssl.create_default_context(cafile=ca),
                    ) as r:
                        if r.status == 200 and (profile / "emulator_credentials").is_file():
                            break
                except OSError:
                    pass
                time.sleep(0.1)
            else:
                raise TimeoutError("AWS Emulator が起動しませんでした")
            env.update(
                HOME=str(Path.home()),
                AWS_ENDPOINT_URL=endpoint,
                AWS_CONFIG_FILE=str(profile / "config"),
                AWS_SHARED_CREDENTIALS_FILE=str(profile / "emulator_credentials"),
                AWS_EC2_METADATA_DISABLED="true",
                AWS_CA_BUNDLE=ca,
                SSL_CERT_FILE=ca,
                AWS_DEFAULT_REGION="us-east-1",
            )
            return subprocess.call(
                [sys.executable, "-m", "pytest", "-q", "tests/e2e/aws", *sys.argv[1:]], env=env
            )
        finally:
            process.terminate()
            process.wait(timeout=15)


if __name__ == "__main__":
    sys.exit(main())
