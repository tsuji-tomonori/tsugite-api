# 合成したFastAPIの公開仕様で、和名・制約・参照・設計不備の位置を検証する。
from typing import Annotated

import pytest
from app.design_names import PortalAPI, localize
from app.schemas import outputs
from fastapi import Depends, FastAPI, Path, Query


def report_limit(
    #: 表示件数の上限
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
):
    return limit


def report_routes(app):
    #: 部署別に所属と件数を確認する
    @app.get("/departments/{key}", response_model=list[outputs.Usage])
    def department(
        #: 対象部署の識別子
        key: Annotated[str, Path(min_length=1)],
        limit: Annotated[int, Depends(report_limit)],
    ):
        return []

    #: プロジェクト別に所属と件数を確認する
    @app.get("/projects/{key}", response_model=dict[str, outputs.Usage])
    def project(
        #: 対象プロジェクトの識別子
        key: str,
    ):
        return {}

    return app


def test_portal_schema_localizes_operation_and_parameter_by_context():
    """同名のパス引数を操作ごとに和名化し、依存から受ける検索件数の範囲と既定値を保持する。"""
    schema = report_routes(PortalAPI()).openapi()
    projects = schema["paths"]["/projects/{key}"]["get"]
    departments = schema["paths"]["/departments/{key}"]["get"]
    assert projects["summary"] == "プロジェクト別に所属と件数を確認する"
    assert departments["summary"] == "部署別に所属と件数を確認する"
    for operation, title in ((projects, "対象プロジェクトの識別子"), (departments, "対象部署の識別子")):
        identifier = next(p for p in operation["parameters"] if p["name"] == "key")
        assert identifier["x-ja-name"] == identifier["schema"]["title"] == title
        assert identifier["required"] and identifier["in"] == "path"
    limit = next(p for p in departments["parameters"] if p["name"] == "limit")
    assert limit["x-ja-name"] == "表示件数の上限"
    assert limit["in"] == "query" and not limit["required"]
    assert (limit["schema"]["minimum"], limit["schema"]["maximum"], limit["schema"]["default"]) == (
        1,
        20,
        5,
    )


def test_localized_schema_preserves_arrays_maps_responses_and_required_fields():
    """和名を適用しても配列と辞書の返却型・共通モデル参照・必須フィールドは元の仕様と一致する。"""
    app = report_routes(FastAPI())
    raw = app.openapi()
    expected = list(raw["components"]["schemas"]["Usage"]["required"])
    localize(raw, app.routes, strict=True)
    components = raw["components"]["schemas"]
    usage = components["Usage"]
    assert usage["title"] == "組織のAPI利用実績"
    assert usage["required"] == expected
    prop = usage["properties"]["members"]
    assert prop["title"] == "対象組織に所属する利用者"
    assert prop["items"] == {"$ref": "#/components/schemas/Affiliation"}
    for path, container, inner in (
        ("/departments/{key}", "array", "items"),
        ("/projects/{key}", "object", "additionalProperties"),
    ):
        responses = raw["paths"][path]["get"]["responses"]
        schema = responses["200"]["content"]["application/json"]["schema"]
        assert schema["type"] == container
        assert schema[inner] == {"$ref": "#/components/schemas/Usage"}
        assert responses["422"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/HTTPValidationError"
        )


@pytest.mark.parametrize(
    ("schema", "location"),
    [
        pytest.param(
            {"paths": {"/untitled": {"get": {"operationId": "untitled"}}}},
            "GET /untitled",
            marks=pytest.mark.case_detail("和名を取得できない操作にはHTTPメソッドとパスを示す"),
        ),
        pytest.param(
            {"paths": {}, "components": {"schemas": {"UnregisteredReport": {"type": "object"}}}},
            "UnregisteredReport",
            marks=pytest.mark.case_detail("和名のない新規モデルにはモデル名を示す"),
        ),
        pytest.param(
            {
                "paths": {},
                "components": {
                    "schemas": {"Usage": {"properties": {"external_count": {"type": "integer"}}}}
                },
            },
            "Usage.external_count",
            marks=pytest.mark.case_detail("新しい項目だけの和名が不足した場合はモデル名と項目名を示す"),
        ),
    ],
)
def test_strict_design_check_identifies_the_missing_name(schema, location):
    """厳格な設計チェックは和名を取得できない定義の位置を開発者に報告する。"""
    with pytest.raises(ValueError, match="和名") as exc:
        localize(schema, strict=True)
    assert location in str(exc.value)


def test_missing_query_label_identifies_the_route_and_parameter():
    """操作に和名があっても、引数の和名がなければその引数を含めて生成エラーを報告する。"""
    app = FastAPI()

    #: 利用件数を検索する
    @app.get("/usage")
    def read(unknown_filter: str):
        return {}

    with pytest.raises(ValueError, match="unknown_filter") as exc:
        localize(app.openapi(), app.routes, strict=True)
    assert "/usage" in str(exc.value)
