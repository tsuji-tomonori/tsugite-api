# フロントエンドの画面開発

`src/web_app/pages/` の各ディレクトリが一つの画面です。たとえば `access_logs/` は本人のアクセスログ一覧、`audit_log_detail/` は管理対象の呼び出し一件、`project_monitor/` はプロジェクトのモニタリングを担当します。

| 場所 | 置くもの |
| --- | --- |
| `pages/<画面名>/` | 部品の組み合わせ、URL、タイトル、メニューの権限と順番。画面専用の読み込み処理やCSSも同じ場所に置く |
| `components/` | 表、フォーム、グラフ、ガイドの画面例などの表示部品と、複数画面にまたがる部品のCSS |
| `apis/` | 業務別のAPI操作、送信パスとHTTPメソッド、認証、HTTPエラー処理 |
| `actions/` | ボタン操作、状態更新、複数画面で使う読み込み処理 |
| `routing/` | 画面の自動登録、URLの解決、画面遷移 |
| `runtime/` | セッション、画面状態、ブラウザーとの連携、共通のレイアウト |
| `content/` | ガイド本文・検索、表示名、整形処理 |
| `public/` | HTMLの入口、アイコン、ポータル全体のスタイル |

## 画面を追加する

`pages/reports/__init__.py` で表示部品を選び、画面を登録します。

```python
# レポート画面の検索欄とルートを定義する。
from components.controls import field
from routing.screen_registry import Screen


def view() -> None:
    """レポートを選ぶための入力欄を表示する。"""
    field("レポート名", "report-name")


SCREENS = (Screen("reports", "レポート", view, group="ワークスペース", order=75),)
```

画面を開いたときにデータが必要なら、同じディレクトリの `data.py` などに `async def load_reports(page: str) -> None` を定義し、`Screen` の `load_data` に渡します。APIの操作は `apis/` から呼び出します。画面専用のCSSはビルド時に自動で取り込まれます。

`group` を省略した画面はURLから直接開けます。末尾が `/` のルートはその後にIDなどが続くURLを受け持ちます。複数のルートが一致すると、最も具体的なパスを使います。ログイン画面は認証前に共通レイアウトから表示します。

Pythonの実装と型定義の先頭には、ファイルの責務を日本語のモジュールdocstring（`"""説明"""`）で一度だけ書きます。CSS・HTML・SVGでは先頭のコメントに書きます。関数には引数と戻り値の型を付け、公開関数には役割を示す日本語のdocstringを添えます。`task types` は画面・部品・API処理とフロントエンドの単体テストをmypyのstrict設定で検査します。
