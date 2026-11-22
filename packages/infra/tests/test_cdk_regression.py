import csv
import json
from collections import Counter
from pathlib import Path

import pytest
from aws_cdk import App, Aspects, Environment
from aws_cdk.assertions import Template
from cdk_nag import AwsSolutionsChecks
from src.infra_app.stack import CatalogStack

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
            key: resource["Type"] for key, resource in template["Resources"].items()
            if resource["Metadata"]["Tsugite"]["Component"] != "Chat"
        },
        "ChatResources": dict(Counter(
            resource["Type"] for resource in template["Resources"].values()
            if resource["Metadata"]["Tsugite"]["Component"] == "Chat"
        )),
        "Outputs": template["Outputs"],
    }
    expected = json.loads((HERE / "cloudformation_snapshot.json").read_text(encoding="utf-8"))
    assert actual == expected


def test_cdk_nag_detects_no_new_findings(catalog_stack, tmp_path):
    """AWS Solutionsの全ルールを実行し、記録済み以外の指摘がないことを確認する。"""
    app = catalog_stack.node.root
    Aspects.of(app).add(AwsSolutionsChecks(verbose=True))
    app.synth()
    report = tmp_path / "out" / "AwsSolutions-TsugiteApi-NagReport.csv"
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
