# デモポータルのOpenAPIから、利用者が読む操作名と入出力の和名を確かめる。
def test_demo_openapi_has_japanese_operation_and_input_labels(portal):
    """デモのOpenAPIは利用者招待の操作と入力項目を公開設計書と同じ和名で説明する。"""
    document = portal.app.openapi()
    operation = document["paths"]["/api/members"]["post"]
    invitation = document["components"]["schemas"]["Invitation"]
    assert operation.get("summary") == "ポータルに利用者を招待する"
    assert invitation["title"] == "ポータル利用者の招待内容"
    assert invitation["properties"]["email"]["title"] == "招待先メールアドレス"
    assert invitation["properties"]["project"]["title"] == "招待先プロジェクトの識別子"
    assert "role" not in invitation["properties"]
    response = operation["responses"]["201"]["content"]["application/json"]["schema"]
    schema_name = response["$ref"].rsplit("/", 1)[1]
    person = document["components"]["schemas"][schema_name]
    assert person["title"] == "利用者の識別情報"
    assert person["properties"]["full_name"]["title"] == "氏名"
    assert person["properties"]["display_name"]["title"] == "表示名"
