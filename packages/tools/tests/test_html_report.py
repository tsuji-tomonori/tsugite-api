# JUnitの結果と画像・CDKメタデータから生成するレポートを確認する。
import json
from xml.etree import ElementTree as ET

from packages.tools.testing import test_report


def test_html_report_tracks_missing_results_and_renders_artifacts(tmp_path, monkeypatch):
    """結果ファイルや画面が欠けたら不合格とし、そろった場合は画像・実行日時・リソースを表示する。"""
    monkeypatch.setattr(test_report, "OUT", tmp_path)
    monkeypatch.setattr(test_report, "ROOT", tmp_path)
    monkeypatch.setenv("GITHUB_SHA", "123456789abcdef")
    report = tmp_path / "test-report.html"
    assert not test_report.build()
    assert "AWS Emulatorの実行結果" in report.read_text()
    suite = ET.Element("testsuite", timestamp="2026-01-01T00:00:00+00:00")
    case = ET.SubElement(suite, "testcase", name="test_portal_view", time="0.1")
    props = ET.SubElement(case, "properties")
    for name, value in (
        ("case_description", "操作結果"),
        ("finding", "入力<確認>"),
        ("screenshot", "screenshots/page.png|実行画面"),
    ):
        ET.SubElement(props, "property", name=name, value=value)
    ET.ElementTree(suite).write(tmp_path / "junit.xml", encoding="utf-8")
    (tmp_path / "aws-emulator.xml").write_text("<testsuite/>")
    assert not test_report.build()
    assert "未取得：実行画面" in report.read_text()
    (tmp_path / "screenshots").mkdir()
    (tmp_path / "screenshots/page.png").write_bytes(b"test-image")
    template = tmp_path / "packages/infra/cdk.out/TsugiteApi.template.json"
    template.parent.mkdir(parents=True)
    meta = {"Component": "Gateway", "Application": "TsugiteAPI", "ManagedBy": "AWS-CDK"}
    template.write_text(
        json.dumps(
            {
                "Resources": {
                    "Example": {
                        "Type": "AWS::Example",
                        "Properties": {"Tags": [{"Key": k, "Value": v} for k, v in meta.items()]},
                        "Metadata": {"Tsugite": meta},
                    }
                }
            }
        )
    )
    assert test_report.build()
    html = report.read_text()
    for expected in (
        "2026年01月01日 09:00 JST",
        "成功 1件",
        "入力&lt;確認&gt;",
        "実行画面",
        "data:image/png;base64,",
        "APIゲートウェイ",
        "AWSタグ",
    ):
        assert expected in html
    for tag, label in (("failure", "失敗"), ("error", "エラー"), ("skipped", "スキップ")):
        status = ET.SubElement(case, tag)
        ET.ElementTree(suite).write(tmp_path / "junit.xml", encoding="utf-8")
        assert not test_report.build()
        assert label + " 1件" in report.read_text()
        case.remove(status)
