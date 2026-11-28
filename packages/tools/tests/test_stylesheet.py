"""テーマ生成はCSSの文字列とコメントを除外し、入れ子の変数と代替値を取得する。"""

from packages.tools.packaging.build_frontend import cloudscape_tokens


def test_stylesheet_uses_only_variable_references():
    """テーマ生成はCSSの文字列とコメントを除外し、入れ子の変数と代替値を取得する。"""
    css = """
        /* var(--cs-comment) */
        .card {
            content: "var(--cs-text)";
            color: VAR( --cs-color, var(--cs-fallback) );
            width: calc(2 * var(--cs-width));
            margin: var(--local);
        }
    """
    assert cloudscape_tokens(css) == ["color", "fallback", "width"]
