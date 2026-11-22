import json

import pytest

from tools.design.infrastructure import generate


def test_component_parameter_sheet(tmp_path):
    """各リソースを所属別に掲載し、配列・参照・埋め込みJSONを項目ごとの行に展開する。"""
    template = tmp_path / "TsugiteApi.template.json"
    out = tmp_path / "docs"
    resources = {
        "OriginalId": {
            "Type": "AWS::SSM::Parameter",
            "Metadata": {"Tsugite": {"Component": "Bindings"}},
            "Properties": {
                "Value": {
                    "Fn::Join": ["", ['{"targets":[{"arn":"', {"Fn::GetAtt": ["Fn", "Arn"]}, '"}]}']]
                },
                "Text": '{"prefix":"a|b","enabled":false,"empty":[]}',
                "Unknown": {"Fn::If": ["HasTarget", {"Ref": "Target"}, "none"]},
            },
            "DeletionPolicy": "Retain",
        },
        "Helper": {
            "Type": "Custom::Helper",
            "Metadata": {"Tsugite": {"Component": "Portal"}},
        },
    }
    template.write_text(json.dumps({"Resources": resources}))
    generate(template, out)
    index = (out / "README.md").read_text(encoding="utf-8")
    sheet = (out / "component-Bindings.md").read_text(encoding="utf-8")
    assert "2コンポーネント、2リソース" in index
    assert "[OriginalId](#originalid)" in sheet and "Custom::Helper" not in sheet
    assert "| `Properties.Value.targets[0].arn` | `${GetAtt:Fn.Arn}` |" in sheet
    assert "| `Properties.Unknown.Fn::If[1]` | `${Ref:Target}` |" in sheet
    assert "| `Properties.Text.enabled` | `false` |" in sheet
    assert "| `Properties.Text.empty` | `（空の配列）` |" in sheet
    assert "| `Properties.Text.prefix` | <code>a&#124;b</code> |" in sheet
    assert "| `DeletionPolicy` | `Retain` |" in sheet
    assert "### Helper" in (out / "component-Portal.md").read_text(encoding="utf-8")

    expected = {p.name: p.read_bytes() for p in out.iterdir()}
    generate(template, out)
    assert expected == {p.name: p.read_bytes() for p in out.iterdir()}
    del resources["Helper"]
    template.write_text(json.dumps({"Resources": resources}))
    (out / "component-notes.md").write_text("# 作業メモ", encoding="utf-8")
    generate(template, out)
    assert not (out / "component-Portal.md").exists()
    assert (out / "component-notes.md").exists()


def test_missing_component_identifies_resource(tmp_path):
    """所属が欠けたリソースは論理IDを示して生成を止める。"""
    template = tmp_path / "stack.template.json"
    template.write_text('{"Resources":{"Orphan":{"Type":"Custom::Helper"}}}')
    with pytest.raises(ValueError, match="Orphan"):
        generate(template, tmp_path / "docs")
