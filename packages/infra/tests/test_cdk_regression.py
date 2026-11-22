import csv
import json
from collections import Counter
from pathlib import Path

import pytest
from aws_cdk import App, AssetStaging, Environment
from aws_cdk.assertions import Template
from src.infra_app import stack
from src.infra_app.stack import CatalogStack

from tools.ci.audit_infra import synthesize_report

HERE = Path(__file__).resolve().parent


@pytest.fixture
def catalog_stack(tmp_path):
    return CatalogStack(
        App(outdir=str(tmp_path / "out")),
        "TsugiteApi",
        env=Environment(account="111111111111", region="ap-northeast-1"),
        analytics_reporting=False,
    )


def test_cloudformation_structure_matches_snapshot(catalog_stack):
    """標準構成のリソース型と論理ID、スタック出力をスナップショットと照合する。"""
    template = Template.from_stack(catalog_stack).to_json()
    actual = {
        "Resources": {key: resource["Type"] for key, resource in template["Resources"].items()},
        "Outputs": template["Outputs"],
    }
    expected = json.loads((HERE / "cloudformation_snapshot.json").read_text(encoding="utf-8"))
    assert actual == expected


def test_cdk_nag_detects_no_new_findings(tmp_path):
    """AWS Solutionsの全ルールを実行し、記録済み以外の指摘がないことを確認する。"""
    report = synthesize_report(tmp_path / "out")
    with report.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    assert rows and any(row["Compliance"] == "Compliant" for row in rows)
    findings = Counter(
        f"{row['Rule ID']} {row['Resource ID']}" for row in rows if row["Compliance"] == "Non-Compliant"
    )
    known = json.loads((HERE / "cdk_nag_baseline.json").read_text(encoding="utf-8"))
    unexpected = findings - Counter(known)
    assert not unexpected, "CDK Nagの新規指摘\n" + "\n".join(
        f"{finding} × {count}" for finding, count in sorted(unexpected.items())
    )


def test_backend_layer_changes_only_with_dependencies(tmp_path):
    """ロジック変更で関数だけが更新され、依存変更で共有Layerだけが更新される。"""

    def synth(name):
        AssetStaging.clear_asset_hash_cache()
        app = App(outdir=str(tmp_path / name))
        resources = Template.from_stack(CatalogStack(app, "TsugiteApi")).to_json()["Resources"]
        handlers = {"app.main.handler", "app.authorizer.handler", "app.migrate.handler"}
        functions = {
            props["Handler"]: props
            for resource in resources.values()
            if resource["Type"] == "AWS::Lambda::Function"
            and (props := resource["Properties"]).get("Handler") in handlers
        }
        assert functions.keys() == handlers
        layer_id = functions["app.main.handler"]["Layers"][0]["Ref"]
        assert all(props["Layers"] == [{"Ref": layer_id}] for props in functions.values())
        layer = resources[layer_id]
        assert layer["Type"] == "AWS::Lambda::LayerVersion"
        assert layer["Properties"]["CompatibleRuntimes"] == ["python3.14"]
        return layer, functions["app.main.handler"]["Code"]

    baseline_layer, baseline_code = synth("baseline")
    code = stack.ROOT / "build/lambda/handler.py"
    code.write_text("print('logic update')\n", encoding="utf-8")
    layer, updated_code = synth("code-update")
    assert layer == baseline_layer
    assert updated_code != baseline_code
    (stack.ROOT / "build/runtime-layer.zip").write_bytes(b"updated dependencies")
    updated_layer, code = synth("dependency-update")
    assert updated_layer["Properties"]["Content"] != baseline_layer["Properties"]["Content"]
    assert code == updated_code
