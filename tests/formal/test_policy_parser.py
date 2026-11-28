"""固定版Quintの実際の構文木で、注釈と文字列リテラルを区別する。"""

from packages.tools.design.formal_changes import model_declarations


def test_quint_parser_preserves_literals_and_ignores_comments():
    """コメントと整形でモデル差分が発生せず、コメント記号を含む文字列の変更は検出できる。"""
    source = 'module review { val state = "approved // ok" }'
    annotated = 'module review {\n  /// 表示用の説明\n  val state /* 状態 */ = "approved // ok"\n}'
    expected = model_declarations(source, "review")
    assert model_declarations(annotated, "review") == expected
    assert model_declarations(annotated.replace("// ok", "// pending"), "review") != expected
