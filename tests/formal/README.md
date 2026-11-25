# 要件から実装を検証する

要件原本の「決めた方針」から参照される業務ケースをQuintで定義する。各モジュールの `init` と `step` は有限の状態遷移、`safe` は全到達状態で成立すべき条件、末尾が `Test` の `run` は実装でも必ず再生する具体的な操作列を表す。モデルの有限範囲は各ファイル内の値・前提条件で確認できる。

リポジトリ直下で次を実行する。Node.js 22・Java 21・プロジェクトのPythonとuvを使用する。初回はQuintのTLA+変換・TLCの配布物を取得する。

```sh
npm ci --prefix tests/formal --ignore-scripts --no-audit
bash tests/formal/check.sh
```

モデルを意図的に変えた場合は次のコマンドで期待状態を再生成する。差分と対応する要件原本を一緒にレビューする。

```sh
python3 tests/formal/generate.py --quint tests/formal/node_modules/.bin/quint --write
```

TLCは有限モデルの到達状態を検査する。別の工程で、Quintが出力したITFの日時・内部番号を取り除き、テスト用の操作と期待値をcases.jsonに保存する。Pythonの再生テストは業務関数またはFastAPIを呼び、観測結果を比較する。拒否時の転送有無は接続先の呼び出し回数でも確かめる。単体テストで扱う参照モデルと境界は各テストのfixtureに記述する。

Verifyのformal-verification成果物に用語・方針・再生テストの対応表（coverage.md）、TLCログ、再生JUnit、操作列を保存する。要件原本の受入テストは既存の要件別証跡にも掲載される。名前付きの再生ケース数とTLCの到達状態数は別の指標として扱う。
