# フロントエンドの画面開発

画面の表示、操作、データ取得、メニューの設定は `src/web_app/portal_pages/` の機能別ファイルにまとめます。たとえば利用状況は `dashboard.py`、ユーザー管理は `members.py` で変更できます。カタログと提供一覧など、同じ画面を条件違いで表示する場合は同じファイルを使います。

## 新しい画面を追加する

たとえば、次の内容を `portal_pages/reports.py` に保存すると、`#/reports` に画面ができ、ワークスペースのメニューにも表示されます。

```python
from puepy import t
from screen_registry import Screen


def view():
    t.p("表示するレポートを選んでください。")


SCREENS = (Screen("reports", "レポート", view, group="ワークスペース", order=75),)
```

- APIからデータを取得する画面では `async def load_reports(page)` を定義し、`Screen` の `load_data` に渡します。`page` は遷移先のパスです。既存の `portal_navigation.load` を操作後に呼ぶと、現在の画面を再取得します。
- `group` を省略した画面はURLから開けます。`api/` のように末尾がスラッシュのルートは、その後にIDが続く詳細画面を受け持ちます。`visible` はメニュー表示の条件です。アクセス権限はAPI側で検査します。
- 画面専用のCSSは隣に `reports.css` として置き、画面固有のクラスで適用範囲を絞ります。ビルドがPythonファイルの階層を保って配布し、CSSを共通スタイルの後ろにまとめます。
- 画面内の処理をさらに分けたいときは、同じディレクトリに `_reports_format.py` のような補助モジュールを置けます。先頭が `_` のファイルは画面の自動登録から除外されます。
- 画面固有のテストは `tests/test_reports.py` に置きます。`app.py` は起動処理、`portal_shell.py` は全画面共通のレイアウトを担当します。
