# 商品ごとにFastAPIの実装からOpenAPI YAMLを生成する。
"""商品ごとにFastAPIの実装からOpenAPI YAMLを生成する。"""

from pathlib import Path

import yaml
from sample_api.main import PRODUCTS

OUTPUT = Path(__file__).resolve().parents[3] / "docs/generated/sample-api"


def generate(output=OUTPUT):
    output.mkdir(parents=True, exist_ok=True)
    for slug, app in PRODUCTS.items():
        (output / f"{slug}.yaml").write_text(
            yaml.safe_dump(app.openapi(), allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
    for path in output.glob("*.yaml"):
        if path.stem not in PRODUCTS:
            path.unlink()


if __name__ == "__main__":
    generate()
