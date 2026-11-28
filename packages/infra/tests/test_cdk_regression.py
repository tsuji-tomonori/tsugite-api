"""標準構成のリソース型と論理ID、スタック出力をスナップショットと照合する。"""

import csv
import json
from collections import Counter
from pathlib import Path

import pytest
from aws_cdk import App, AssetStaging, Environment
from aws_cdk.assertions import Template

from packages.infra.src import stack
from packages.infra.src.stack import CatalogStack
from packages.tools.ci.audit_infra import synthesize_report

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
        "Resources": {
            key: resource["Type"]
            for key, resource in template["Resources"].items()
            if resource["Metadata"]["Tsugite"]["Component"] != "Chat"
        },
        "ChatResources": dict(
            Counter(
                resource["Type"]
                for resource in template["Resources"].values()
                if resource["Metadata"]["Tsugite"]["Component"] == "Chat"
            )
        ),
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
        handlers = {
            "app.main.handler",
            "app.authorizer.handler",
            "app.migrate.handler",
            "chat_jobs.handler",
        }
        functions = {
            props["Handler"]: props
            for resource in resources.values()
            if resource["Type"] == "AWS::Lambda::Function"
            and (props := resource["Properties"]).get("Handler") in handlers
        }
        assert functions.keys() == handlers
        assert all(props["Runtime"] == "python3.15" for props in functions.values())
        layer_id = functions["app.main.handler"]["Layers"][0]["Ref"]
        assert all(props["Layers"] == [{"Ref": layer_id}] for props in functions.values())
        layer = resources[layer_id]
        assert layer["Type"] == "AWS::Lambda::LayerVersion"
        assert layer["Properties"]["CompatibleRuntimes"] == ["python3.15"]
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


def test_model_layer_changes_are_isolated(tmp_path):
    """関数コード、判定用の依存、重みを個別に更新し、他の配布物が変化しないことを確認する。"""

    def synth(name):
        AssetStaging.clear_asset_hash_cache()
        app = App(outdir=str(tmp_path / name))
        resources = Template.from_stack(CatalogStack(app, "TsugiteApi")).to_json()["Resources"]
        codes = {}
        layers = {}
        for resource in resources.values():
            if resource["Type"] != "AWS::Lambda::Function":
                continue
            props = resource["Properties"]
            role = props.get("Environment", {}).get("Variables", {}).get("MODEL_ROLE")
            if role:
                expected_runtime = "python3.14" if role == "decision" else "python3.15"
                refs = props["Layers"]
                assert len(refs) == (2 if role == "decision" else 1)
                assert ("MODEL_BUCKET" in props["Environment"]["Variables"]) == (role != "decision")
                codes[role] = props["Code"]
                layers[role] = []
                for ref in refs:
                    layer = resources[ref["Ref"]]
                    assert layer["Type"] == "AWS::Lambda::LayerVersion"
                    assert (
                        layer["Properties"]["CompatibleRuntimes"]
                        == [props["Runtime"]]
                        == [expected_runtime]
                    )
                    layers[role].append(layer["Properties"]["Content"])
        assert set(layers) == {"decision", "tool", "generate"}
        assert layers["tool"] == layers["generate"] != layers["decision"]
        return codes, layers

    codes, layers = synth("baseline")
    (stack.ROOT / "build/chat-decision/decision.py").write_text("# update\n", encoding="utf-8")
    new_codes, new_layers = synth("code")
    assert new_layers == layers
    assert new_codes["decision"] != codes["decision"]
    assert new_codes["tool"] == codes["tool"] and new_codes["generate"] == codes["generate"]
    (stack.ROOT / "build/decision-model-layer.zip").write_bytes(b"new model dependencies")
    final_codes, final_layers = synth("dependency")
    assert final_codes == new_codes
    assert final_layers["decision"][0] != layers["decision"][0]
    assert final_layers["decision"][1] == layers["decision"][1]
    assert final_layers["tool"] == layers["tool"]
    (stack.ROOT / "build/decision-weights-layer.zip").write_bytes(b"new weights")
    weight_codes, weight_layers = synth("weights")
    assert weight_codes == final_codes
    assert weight_layers["decision"][0] == final_layers["decision"][0]
    assert weight_layers["decision"][1] != final_layers["decision"][1]
    assert weight_layers["tool"] == final_layers["tool"]


def test_sample_functions_use_python_315(catalog_stack):
    """3環境のサンプルAPIがすべてPython 3.15で動作する構成になっている。"""
    Template.from_stack(catalog_stack).resource_properties_count_is(
        "AWS::Lambda::Function", {"Handler": "sample_api.main.handler", "Runtime": "python3.15"}, 3
    )


def test_schema_waits_for_chat_models(catalog_stack):
    """判定・ツール選択・生成の各関数の配備が完了してからDB移行を開始する。"""
    template = Template.from_stack(catalog_stack)
    functions = template.find_resources("AWS::Lambda::Function")
    model_ids = {
        logical_id
        for logical_id, function in functions.items()
        if "MODEL_ROLE" in function["Properties"].get("Environment", {}).get("Variables", {})
    }
    assert len(model_ids) == 3
    schema = template.to_json()["Resources"]["Schema"]
    assert model_ids.issubset(schema.get("DependsOn", []))
