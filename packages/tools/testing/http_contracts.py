"""公開仕様に定めたHTTPステータスを、テストで実際に観測した応答と照合する。"""

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

REPORTS = Path("artifacts/http-contracts")
SAMPLES = Path("docs/generated/sample-api")
METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


def missing_responses(document, report):
    observed = {
        (endpoint["path"], method["method"].lower(), str(status))
        for endpoint in report["endpoints"]
        for method in endpoint["methods"]
        for status, count in method["response_codes"].items()
        if count > 0
    }
    expected = {
        (path, method, str(status))
        for path, item in document["paths"].items()
        for method, operation in item.items()
        if method in METHODS
        for status in operation["responses"]
    }
    if not expected:
        raise ValueError("公開仕様に検査対象の応答がありません")
    return sorted(expected - observed)


def measure(spec, target, *options):
    output = REPORTS / spec.stem
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            target,
            f"--coverage-spec={spec}",
            f"--coverage-output={output}",
            "--coverage-format=json",
            *options,
        ],
        check=True,
    )
    missing = missing_responses(
        yaml.safe_load(spec.read_text()), json.loads((output / "coverage.json").read_text())
    )
    if missing:
        raise SystemExit(
            "\n".join(
                f"{spec.stem}: {method.upper()} {path} → {status} 未検証"
                for path, method, status in missing
            )
        )


def main():
    os.environ["TSUGITE_DEMO"] = "1"
    from app.main import create_app
    from sample_api.main import PRODUCTS

    REPORTS.mkdir(parents=True, exist_ok=True)
    backend = REPORTS / "backend.json"
    backend.write_text(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2))
    measure(backend, "packages/backend/tests")
    for slug in PRODUCTS:
        measure(
            SAMPLES / f"{slug}.yaml",
            f"packages/sample_api/tests/test_http_contract.py::test_product_http_contract[{slug}]",
            f"--coverage-strip-prefix=/{slug}",
        )


if __name__ == "__main__":
    main()
