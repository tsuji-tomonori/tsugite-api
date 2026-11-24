# 開発完了の定義

`main` 向けのPRは、差分に応じて選ばれた検査に合格することが完了条件です。各テストのリンクから、条件と期待結果を実装で確認できます。

## 全体の行カバレッジ

単体・結合テストとブラウザーE2Eの計測を合算します。分野別の数値は内訳です。合否には対象ブランチの有効なGitHubルールを使います。

| 判定項目 | 基準・対象 |
| --- | --- |
| 単体テストのパッケージ別下限 | C0 90%、C1 85% |
| 全体の最低行カバレッジ | 84%以上 |
| 比較元からの低下幅 | 1ポイント以内 |
| 計測対象 | `packages/backend/src/app`、`packages/database`、`packages/frontend/src/web_app`、`packages/infra`、`packages/sample_api/src/sample_api`、`packages/agent/src/agent`、`packages/tools` |
| 計測から除くパターン | `*/tests/*`、`*/cdk.out/*`、`*/__pycache__/*` |

## 分野別の変更と必要な検査

実在するファイルを1つ変更した場合の例です。複数のファイルを変更すると対象が広がります。過去の計測で変更行を通ったスイートも再実行の対象になります。

| 分野 | 変更ファイルの例 | 合格が必要なテスト | 追加の検査・生成 |
| --- | --- | --- | --- |
| サンプルAPI | `packages/sample_api/src/sample_api/database.py` | サンプルAPI、アーキテクチャ、バックエンド、インフラ、ブラウザーE2E、開発ツール | Ruff（書式・静的解析）、API設計書・契約の生成、依存関係・CDK監査、CDK合成・インフラ文書生成、AWSエミュレーターE2E |
| エージェント・推論モデル | `packages/agent/src/agent/jobs.py` | エージェント・推論モデル、アーキテクチャ、バックエンド、インフラ、ブラウザーE2E | Ruff（書式・静的解析）、型検査、依存関係・CDK監査、CDK合成・インフラ文書生成、AWSエミュレーターE2E |
| バックエンド | `packages/backend/src/app/apis/catalog/apply.py` | エージェント・推論モデル、アーキテクチャ、バックエンド、ブラウザーE2E、開発ツール | Ruff（書式・静的解析）、型検査、API設計書・契約の生成、CDK合成・インフラ文書生成、AWSエミュレーターE2E |
| フロントエンド | `packages/frontend/src/web_app/actions/activity.py` | アーキテクチャ、フロントエンド、ブラウザーE2E | Ruff（書式・静的解析）、型検査、CDK合成・インフラ文書生成、AWSエミュレーターE2E |
| インフラ | `packages/infra/app.py` | アーキテクチャ、インフラ | Ruff（書式・静的解析）、依存関係・CDK監査、CDK合成・インフラ文書生成、AWSエミュレーターE2E |
| データベース | `packages/database/migrations/env.py` | エージェント・推論モデル、アーキテクチャ、バックエンド、データベース、ブラウザーE2E、開発ツール | Ruff（書式・静的解析）、型検査、API設計書・契約の生成、CDK合成・インフラ文書生成、AWSエミュレーターE2E |
| 開発ツール | `packages/tools/ci/audit_infra.py` | アーキテクチャ | Ruff（書式・静的解析）、依存関係・CDK監査、CDK合成・インフラ文書生成 |

## CIの検査項目と実行条件

条件欄の `steps.scope.outputs` は、PRの差分からCIが決めた実行計画です。各行のリンクは判定を実行するステップを指します。

| 検査 | 確認内容 | 実行条件 |
| --- | --- | --- |
| [完了の定義を生成](../../../.github/workflows/check.yml#L26) | 分野別のテスト定義と有効なカバレッジ基準から完了の定義を生成できる。 | すべてのPR |
| [要件別の受入テスト定義を検査](../../../.github/workflows/check.yml#L38) | 各要件に実在する受入テストと証跡の取得方法が定義されている。 | すべてのPR |
| [要件一覧と用語一覧を生成し、feat ブランチの新規要件を検査](../../../.github/workflows/check.yml#L41) | 要件文・必須の節・共通語彙を検査する。feat ブランチには新しい要件が1件以上ある。 | すべてのPR |
| [Markdown文書の表題を検証](../../../.github/workflows/check.yml#L77) | 文書の最初のレベル1見出しに日本語がある。 | `steps.scope.outputs.documents == 'true'` |
| [変更ファイルの文字コードと改行を検査](../../../.github/workflows/check.yml#L81) | 変更したテキストはUTF-8（BOMなし）・LFで、末尾の改行が1つある。 | `steps.scope.outputs.full != 'true'` |
| [task lint](../../../.github/workflows/check.yml#L97) | 全体のRuff書式検査・静的解析と、Git管理対象のテキスト検査が通る。 | `steps.scope.outputs.full == 'true'` |
| [変更したPythonファイルの書式と静的検査](../../../.github/workflows/check.yml#L100) | 追加・変更したPythonファイルにRuffの書式違反やルール違反がない。 | `steps.scope.outputs.lint == 'true' && steps.scope.outputs.full != 'true'` |
| [task types](../../../.github/workflows/check.yml#L109) | 設定対象のPyrightとmypyの型検査がともに通る。 | `steps.scope.outputs.types == 'true'` |
| [task test:hooks](../../../.github/workflows/check.yml#L112) | Gitフックが機密情報を含むコミットや保護対象ブランチへの不正なプッシュを拒否する。 | `steps.scope.outputs.hooks == 'true'` |
| [task synth](../../../.github/workflows/check.yml#L121) | 配布物をビルドし、CDKからCloudFormationテンプレートを合成できる。 | `steps.scope.outputs.synth == 'true'` |
| [同じロックから再ビルドしたLambda LayerのSHA-256を照合](../../../.github/workflows/check.yml#L124) | 依存ロックまたはビルダーの変更時は、再生成したLambda依存パッケージのSHA-256が一致する。 | `steps.scope.outputs.synth == 'true'` |
| [uv run --locked --all-packages python packages/tools/packaging/build_frontend.py](../../../.github/workflows/check.yml#L135) | フロントエンドの配布物を生成できる。 | `steps.scope.outputs.frontend_build == 'true'` |
| [task docs:infra:render](../../../.github/workflows/check.yml#L138) | 合成済みテンプレートからリソース一覧とパラメーターシートを生成できる。 | `steps.scope.outputs.synth == 'true'` |
| [task contracts docs:api](../../../.github/workflows/check.yml#L141) | OpenAPI・テーブル定義・API設計書を生成できる。 | `steps.scope.outputs.design == 'true'` |
| [商品別OpenAPIの生成と差分検査](../../../.github/workflows/check.yml#L144) | 商品別のOpenAPI YAMLをFastAPIから再生成し、コミット済みの仕様と一致する。 | `steps.scope.outputs.design == 'true'` |
| [task audit](../../../.github/workflows/check.yml#L150) | CDKの監査結果を出力し、Lambda実行時依存に対するpip-auditが通る。 | `steps.scope.outputs.audit == 'true'` |
| [対象テストを実行し、全体カバレッジを集計](../../../.github/workflows/check.yml#L153) | 差分に応じて選ばれたテストが成功し、比較元の計測結果と合わせて全体を集計できる。 | `steps.scope.outputs.suites != '[]'` |
| [パッケージごとの単体テストカバレッジを検査](../../../.github/workflows/check.yml#L158) | パッケージ別に単体テストのみで行・分岐の両方が設定した下限を満たす。 | `steps.scope.outputs.suites != '[]'` |
| [task test:aws](../../../.github/workflows/check.yml#L162) | AWSエミュレーターで対象のE2Eが成功する。 | `${{ !cancelled() && (success() \|\| steps.suites.outcome == 'failure') && steps.scope.outputs.aws == 'true' && steps.scope.outputs.aws_portal_only != 'true' }}` |
| [task test:aws -- -k test_cognito_browser](../../../.github/workflows/check.yml#L165) | ポータルに限定した検証ではCognitoを使うブラウザーテストが成功する。 | `${{ !cancelled() && (success() \|\| steps.suites.outcome == 'failure') && steps.scope.outputs.aws_portal_only == 'true' }}` |
| [行カバレッジをブランチルールと照合](../../../.github/workflows/check.yml#L168) | 全体の行カバレッジが、対象ブランチの下限と許容低下幅を満たす。 | `steps.scope.outputs.coverage == 'true'` |
| [カバレッジと成果物へのリンクをCIの概要に表示](../../../.github/workflows/check.yml#L186) | 行カバレッジとXML成果物へのリンクをCIの概要で確認できる。 | `steps.coverage_artifact.outcome == 'success'` |
| [今回のJUnit・画面証跡から要件別の合否を判定](../../../.github/workflows/check.yml#L195) | 今回の実行対象となった要件について、JUnit結果と指定された証跡から合否を判定できる。 | `${{ !cancelled() }}` |
| [Build screenshot report](../../../.github/workflows/check.yml#L211) | JUnit結果とスクリーンショットからレポートを生成できる。 | `${{ !cancelled() && steps.scope.outputs.report == 'true' && hashFiles('artifacts/junit.xml') != '' }}` |

### 静的解析の設定

| ツール | ルール・対象 |
| --- | --- |
| Ruff | `E4`、`E7`、`E9`、`F`、`I`、`F631`、`PT011`、`PT012` |
| Pyright | `packages/agent`、`packages/backend/src/app`、`packages/database/src/tsugite_db` |
| Pyright（strict） | `packages/database/src/tsugite_db/models`、`packages/backend/src/app/schemas/catalog.py`、`packages/backend/src/app/schemas/base.py` |
| mypy（strict=True） | `packages/database/src/tsugite_db/models`、`packages/backend/src/app/schemas/catalog.py`、`packages/backend/src/app/schemas/base.py` |
| フロントエンドのmypy（strict=True） | `packages/frontend/src/web_app`、`packages/frontend/tests` |

## テストが確認する条件と期待結果

分野ごとにテスト関数を1行ずつ掲載します。条件別の確認内容はテストに付けた日本語の説明から取得します。

### サンプルAPI（3項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| 全商品の出品仕様がFastAPIと一致し、再生成した各YAMLを同じ内容で公開できる。 | — | [test_generated_product_contracts](../../../packages/sample_api/tests/test_products.py#L12) |
| 12商品で5つの業務操作とヘルスチェックを実行し、商品境界とLambda応答を照合する。 | — | [test_each_product_operation_through_lambda](../../../packages/sample_api/tests/test_products.py#L29) |
| 在庫サンプルが操作に応じたステータスとJSON応答を返す。 | 登録されている商品の在庫一覧を返す<br>指定した商品の在庫を返す<br>未登録の商品は該当なしと返す | [test_stock_response](../../../packages/sample_api/tests/test_stock_lambda.py#L34) |

### エージェント・推論モデル（19項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| 同じ受付番号の再送はワーカーを増やさず、本人が有効期間内に結果を取得できる。 | — | [test_worker_dispatch_and_result_lifecycle](../../../packages/agent/tests/test_agent_jobs.py#L10) |
| モデルの辞書応答を返し、設定漏れ・関数エラー・壊れた応答では空の候補で処理を続ける。 | — | [test_worker_model_result_and_unavailable_model](../../../packages/agent/tests/test_agent_jobs.py#L50) |
| 期限ちょうどのジョブは失敗として返し、遅れて届いたワーカーが上書きしない。 | — | [test_expired_job_returns_error_without_invoking_models](../../../packages/agent/tests/test_agent_jobs.py#L71) |
| 重複した受付を抑止し、結果保存が競合した場合だけ先に書き込まれた結果を維持する。 | — | [test_concurrent_submission_and_result_updates](../../../packages/agent/tests/test_agent_jobs.py#L82) |
| ワーカーの起動に失敗したときは失敗結果を保存し、受付側へ起動例外を返す。 | — | [test_worker_dispatch_failure_persists_retry_result](../../../packages/agent/tests/test_agent_jobs.py#L106) |
| 消えたジョブは処理せず、保存先の障害は要求識別子を記録して再送可能にする。 | — | [test_unknown_job_and_worker_storage_failure](../../../packages/agent/tests/test_agent_jobs.py#L124) |
| 語句が一致しない質問も日本語埋め込みで公開商品に結び付ける。 | — | [test_model_resolves_paraphrase_with_hybrid_retrieval](../../../packages/agent/tests/test_agent_retrieval.py#L10) |
| 生成モデルに架空の案内文や無効な出典を渡されても、実在するガイドに戻す。 | — | [test_manual_answer_rejects_generated_text_outside_evidence](../../../packages/agent/tests/test_agent_retrieval.py#L39) |
| 対象外と判定した質問はおすすめという語を含んでも検索・生成を呼ばない。 | — | [test_strong_outside_decision_prevents_tools_and_generation](../../../packages/agent/tests/test_agent_retrieval.py#L54) |
| 指示の上書きを拒否し、質問の語が含まれない生成クエリは元の質問に戻す。 | — | [test_agent_blocks_prompt_instructions_and_keeps_query_grounded](../../../packages/agent/tests/test_agent_retrieval.py#L70) |
| 生成クエリだけに一致する商品は意味検索の候補から外す。 | — | [test_rewritten_similarity_needs_support_from_original_question](../../../packages/agent/tests/test_agent_retrieval.py#L81) |
| 重複する入力の埋め込みを再利用し、空のバッチは推論前に拒否する。 | — | [test_embedding_reuses_vectors_and_validates_batch](../../../packages/agent/tests/test_model_workers.py#L30) |
| 検索モデルへの選択肢を許可された操作に限定し、候補が空ならモデルを呼び出さない。 | — | [test_completion_limits_tool_choices](../../../packages/agent/tests/test_model_workers.py#L51) |
| モデルのハッシュが異なる場合は一時ファイルを破棄し、正しいモデルを取得した後は再利用する。 | — | [test_model_download_verifies_digest_before_reuse](../../../packages/agent/tests/test_model_workers.py#L64) |
| 起動済みの生成モデルを再利用し、提示した資料の範囲と決定的な生成条件を渡す。 | — | [test_generation_returns_grounded_result_from_warm_process](../../../packages/agent/tests/test_model_workers.py#L83) |
| 応答しない生成プロセスを停止し、同じモデルをCPUで再起動して準備完了を待つ。 | — | [test_model_process_recovers_from_failed_health_check](../../../packages/agent/tests/test_model_workers.py#L106) |
| 埋め込みモデルと長さ制限付きトークナイザーを初回だけ読み込む。 | — | [test_embedding_load_reuses_cpu_model_and_tokenizer](../../../packages/agent/tests/test_model_workers.py#L126) |
| 成功時は戻り値を保ち、重みの検証エラーは診断ログを出して呼び出し元へ伝える。 | — | [test_model_runtime_logs_failures_and_preserves_exceptions](../../../packages/agent/tests/test_model_workers.py#L145) |
| 起動中に終了したプロセスと応答期限を超えたプロセスを区別して後片付けする。 | — | [test_completion_startup_handles_crash_and_timeout](../../../packages/agent/tests/test_model_workers.py#L164) |

### アーキテクチャ（48項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| エージェントが使う推論モデルの役割、取得元、ハッシュを検査する。 | — | [test_agent_distributes_pinned_models](../../../tests/architecture/agent/test_distribution.py#L6) |
| 公開操作のOpenAPI IDと実装が対応する | — | [test_published_operations_have_stable_ids](../../../tests/architecture/backend/test_routes.py#L5) |
| FastAPIに登録した業務ルートはapis配下で定義し、下位層からルーターを参照しない。 | — | [test_route_handlers_belong_to_api_layer](../../../tests/architecture/backend/test_routes.py#L17) |
| 全層の単体テスト・アーキテクチャテスト・E2Eに簡潔な日本語の説明がある。 | — | [test_test_cases_have_japanese_descriptions](../../../tests/architecture/core/test_case_descriptions.py#L19) |
| 各パッケージの依存宣言から逆依存をたどり、変更元と利用側の単体テストを選ぶ。 | — | [test_workspace_dependency_changes_verify_consumers](../../../tests/architecture/core/test_ci_scope.py#L16) |
| 実装が他の配布単位から読み込むモジュールを解析し、変更時に利用側のテストが選ばれる。 | — | [test_imported_modules_verify_their_actual_consumers](../../../tests/architecture/core/test_ci_scope.py#L44) |
| PR説明・CSS・各層のテスト変更で、キャッシュがなくても無関係な層やCDKを起動しない。 | — | [test_verify_skips_unrelated_packages_even_without_coverage](../../../tests/architecture/core/test_ci_scope.py#L67) |
| AWSエミュレーターは合成済みテンプレートを使い、モデル定義の変更はCDKの単体テストでも検証する。 | — | [test_emulator_and_model_manifest_verify_deployment_inputs](../../../tests/architecture/core/test_ci_scope.py#L83) |
| Verifyが差分判定の出力を使い、対象外のCDK合成・AWS・ブラウザー・単体テストを起動しない。 | — | [test_workflow_runs_expensive_steps_only_for_selected_outputs](../../../tests/architecture/core/test_ci_scope.py#L96) |
| CIは単体テストの計測後にパッケージ別の行・分岐カバレッジを必須判定する。 | — | [test_verify_enforces_package_unit_coverage](../../../tests/architecture/core/test_ci_scope.py#L112) |
| 全実装のインポートを調べ、配布単位を越える未許可の依存を検出する。 | — | [test_runtime_dependencies_respect_layer_boundaries](../../../tests/architecture/core/test_dependencies.py#L6) |
| 要件・設計書・生成文書・各層の説明書は、日本語を含む表題で目的を示す。 | — | [test_markdown_documents_have_japanese_titles](../../../tests/architecture/core/test_documents.py#L26) |
| 全要件のファイル名・要件文・四つの節・共通語彙を索引生成と同じ規則で検査する。 | — | [test_requirements_follow_the_project_vocabulary](../../../tests/architecture/core/test_documents.py#L39) |
| 全パッケージがuvワークスペースに属し、単体テストと固有のアーキテクチャテストを持つ。 | — | [test_packages_have_collected_tests_and_metadata](../../../tests/architecture/core/test_packages.py#L10) |
| 全パッケージに適用する行と分岐の下限、およびuvの既定のPyPI取得先を確認する。 | — | [test_workspace_coverage_and_index](../../../tests/architecture/core/test_packages.py#L38) |
| すべてのPythonファイルの先頭に、そのファイルの役割を説明する日本語コメントがある。 | — | [test_python_files_start_with_japanese_purpose](../../../tests/architecture/core/test_packages.py#L50) |
| どの単体テストでも定数だけのassertや同一式同士の等価比較を検出する。 | — | [test_unit_assertions_check_observations](../../../tests/architecture/core/test_packages.py#L63) |
| 各層の違反をインポートの別名・相対参照・完全修飾名でも行番号付きで報告する。 | — | [test_boundary_checker_rejects_cross_layer_imports](../../../tests/architecture/core/test_rule_checks.py#L15) |
| APIのジョブ受付、エージェントのガイド共有、モデル内の参照を許可する。 | — | [test_boundary_checker_accepts_supported_collaboration](../../../tests/architecture/core/test_rule_checks.py#L48) |
| 所属する層を定義していない新規パッケージを検査対象から漏らさない。 | — | [test_new_package_requires_layer_rules](../../../tests/architecture/core/test_rule_checks.py#L61) |
| コード例の日本語を表題に数えず、例の後に続く日本語の表題を採用する。 | — | [test_document_checker_uses_title_outside_code_examples](../../../tests/architecture/core/test_rule_checks.py#L67) |
| 新しい配下の文書と生成設計書を自動で検査し、ビルドの一時コピーを除外する。 | — | [test_project_discovery_includes_new_components](../../../tests/architecture/core/test_rule_checks.py#L74) |
| 取得元が可変または重みのハッシュが不正なモデルについて両方の原因を報告する。 | — | [test_model_checker_rejects_unpinned_weight](../../../tests/architecture/core/test_rule_checks.py#L88) |
| クラス内の非同期テストも説明の検査対象に含め、補助関数を除く。 | — | [test_case_discovery_includes_async_class_methods](../../../tests/architecture/core/test_rule_checks.py#L96) |
| 正常な説明を受け付け、英語だけの説明・複数行・短すぎる説明を検出する。 | — | [test_case_explanation_requires_one_japanese_sentence](../../../tests/architecture/core/test_rule_checks.py#L105) |
| 三つの役割がそろった配布物は通過し、一つでも定義が欠けると失敗する。 | — | [test_model_distribution_requires_all_three_roles](../../../tests/architecture/core/test_rule_checks.py#L112) |
| DB層はHTTPのルーターに依存しない | — | [test_persistence_has_no_http_dependencies](../../../tests/architecture/database/test_persistence.py#L5) |
| 各テーブルと同名のファイルにモデルを1件置き、全モデルを共通のメタデータに登録する。 | — | [test_model_files_match_registered_tables](../../../tests/architecture/database/test_persistence.py#L15) |
| 全画面で機能ごとの定義を検査し、共通コードへの画面登録と個別画面間の直接依存を検出する。 | — | [test_portal_screens_keep_their_feature_boundaries](../../../tests/architecture/frontend/test_frontend_screens.py#L10) |
| 画面が同じディレクトリの補助処理と共通の表示部品を組み合わせられる。 | — | [test_feature_can_compose_components_and_its_own_helpers](../../../tests/architecture/frontend/test_frontend_screens.py#L23) |
| 画面定義の欠落、空の宣言、別モジュールからの丸ごと転送を検出する。 | — | [test_feature_requires_local_screen_declaration](../../../tests/architecture/frontend/test_frontend_screens.py#L36) |
| 共通コードに移した画面一覧と、別名で取り込んだ個別画面の両方を検出する。 | — | [test_shared_code_cannot_own_or_import_an_individual_screen](../../../tests/architecture/frontend/test_frontend_screens.py#L48) |
| 画面間の相対インポートと共通レイアウトへの逆向き依存を行番号付きで検出する。 | — | [test_feature_cannot_depend_on_another_screen_or_the_shell](../../../tests/architecture/frontend/test_frontend_screens.py#L57) |
| 共通レイアウトへのURL別の条件分岐を検出し、通知やガイドへのリンクを許可する。 | — | [test_shared_layout_delegates_route_dispatch](../../../tests/architecture/frontend/test_frontend_screens.py#L67) |
| 遷移時の状態破棄を許可し、共通ナビゲーションに戻した画面別API取得を検出する。 | — | [test_page_loading_stays_in_the_feature](../../../tests/architecture/frontend/test_frontend_screens.py#L82) |
| 部品からの画面参照とページ内の独自描画を別名・相対インポートでも検出する。 | — | [test_components_cannot_import_pages_and_pages_cannot_define_widgets](../../../tests/architecture/frontend/test_frontend_screens.py#L92) |
| フロントのソース先頭行と公開関数の説明が日本語で記述されていることを確認する。 | — | [test_frontend_source_describes_files_and_public_functions](../../../tests/architecture/frontend/test_frontend_screens.py#L103) |
| 空行・英語だけのコメント・日本語の文字列をファイル先頭の説明として受理しない。 | — | [test_first_line_requires_a_japanese_comment](../../../tests/architecture/frontend/test_frontend_screens.py#L114) |
| CDKスタックが各コンポーネントを組み立て、コンポーネントからスタックを参照しない。 | — | [test_components_do_not_import_the_stack](../../../tests/architecture/infra/test_stack.py#L8) |
| 商品ごとに実装モジュールと公開用のOpenAPIファイルが一対一で対応する。 | — | [test_each_product_has_a_published_contract](../../../tests/architecture/sample_api/test_products.py#L5) |
| 設計解析とその補助モジュールで外部辞書の読み込みと正規表現を検出する。 | — | [test_design_analysis_uses_only_python_sources_and_syntax_trees](../../../tests/architecture/tools/test_design_sources.py#L98) |
| コードやスタイルシートを読む開発ツールで正規表現による解析を検出する。 | — | [test_project_tools_do_not_parse_source_files_with_regex](../../../tests/architecture/tools/test_design_sources.py#L103) |
| 廃止した用語集の復活と設計書生成パッケージへの外部辞書の追加を検出する。 | — | [test_design_source_directories_contain_no_sidecar_data](../../../tests/architecture/tools/test_design_sources.py#L122) |
| 別名や相対インポートを経由した正規表現と外部辞書も呼び出し元から検出する。 | — | [test_analysis_policy_follows_renamed_helpers_and_relative_imports](../../../tests/architecture/tools/test_design_sources.py#L134) |
| 同名項目の和名を各モデルから取得し、文字列中の偽コメントや通常の注釈を無視する。 | — | [test_schema_field_uses_only_the_comment_on_its_declaration](../../../tests/architecture/tools/test_design_sources.py#L149) |
| 拡張子を変更した外部辞書をコメントの入力として読み込めない。 | — | [test_non_python_source_cannot_supply_business_names](../../../tests/architecture/tools/test_design_sources.py#L161) |
| 全API項目とDBカラムに業務用の和名がある | — | [test_business_names_cover_every_operation_field_and_database_column](../../../tests/architecture/tools/test_design_sources.py#L172) |
| 定義元のコメントだけを変更するとOpenAPI、API詳細、DB定義書、AWS操作表に反映される。 | — | [test_editing_declaration_comments_changes_openapi_and_design_pages](../../../tests/architecture/tools/test_design_sources.py#L209) |

### バックエンド（162項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| 条件を満たさないアクセストークンを401で拒否する | 発行元が設定値と異なる<br>IDトークンを送った場合<br>未登録クライアントから送信<br>有効期限を過ぎている<br>システム用トークンに呼び出しスコープがない | [test_invalid_token](../../../packages/backend/tests/test_auth.py#L71) |
| 人とシステムを識別し、システムのポータル利用を拒否する | — | [test_people_and_machines](../../../packages/backend/tests/test_auth.py#L78) |
| API識別名が必須かつ一意で、登録後に変更や再利用ができない。 | — | [test_api_slug_is_unique_and_fixed](../../../packages/backend/tests/test_catalog.py#L10) |
| 既存商品に識別名を加えても利用権が残り、識別名と従来のUUIDで同じAPIを呼べる。 | — | [test_existing_api_keeps_grants_when_named](../../../packages/backend/tests/test_catalog.py#L36) |
| 承認した環境だけで呼び出せ、取消後の拒否を監査できる | — | [test_lifecycle](../../../packages/backend/tests/test_catalog.py#L73) |
| 却下後に再申請でき、古い判断の再適用を拒否する | — | [test_reapply](../../../packages/backend/tests/test_catalog.py#L153) |
| 外部参照、環境違いの接続先、不正な仕様の登録を拒否する | — | [test_registration_validation](../../../packages/backend/tests/test_catalog.py#L188) |
| OpenAPIの固定パスを優先し、許可された操作だけを通す | — | [test_route_contract](../../../packages/backend/tests/test_catalog.py#L205) |
| Lambdaではデモ用ログインを無効にする | — | [test_demo_disabled_on_lambda](../../../packages/backend/tests/test_catalog.py#L214) |
| 未申請・取下げ後の権限を拒否し、他プロジェクトに監査記録を開示しない | — | [test_withdrawal_and_audit_visibility](../../../packages/backend/tests/test_catalog.py#L227) |
| チャットが公開中の商品だけを勧め、別の利用者や取り下げ後の閲覧を拒む。 | — | [test_chat_only_returns_currently_visible_products](../../../packages/backend/tests/test_chat_api.py#L16) |
| 操作の質問に実際の手順を返し、使い方ガイドを参照できる。 | — | [test_chat_cites_authored_guide_steps](../../../packages/backend/tests/test_chat_api.py#L34) |
| ワーカーの手順番号が文字列でも、閲覧できるガイドの最初の手順を案内する。 | — | [test_invalid_worker_step_returns_first_visible_guide_step](../../../packages/backend/tests/test_chat_api.py#L43) |
| 問い合わせの案内だけでは未送信で、送信後の回答は本人と管理者にだけ表示する。 | — | [test_inquiry_requires_explicit_submission_and_private_reply](../../../packages/backend/tests/test_chat_api.py#L58) |
| APIが受け付けた質問をワーカーがDBで検索し、本人の受付番号で公開商品を取得できる。 | — | [test_async_chat_resolves_public_product_through_worker](../../../packages/backend/tests/test_chat_api.py#L81) |
| 提供者・部署・プロジェクトの上限、更新と失効の秒境界、発行後の上限短縮を確認する | — | [test_nested_token_lifetime](../../../packages/backend/tests/test_credential_lifecycle.py#L13) |
| 60日後もシステム資格で再発行でき、古いアクセストークン・従来キーは失効する | — | [test_persistent_system_and_legacy_expiry](../../../packages/backend/tests/test_credential_lifecycle.py#L85) |
| 本人の認証情報との交換だけを許可し、失効・他人の認証情報・ログイン単独の実行を拒否する。 | — | [test_interactive_exchange_requires_registered_credential](../../../packages/backend/tests/test_credential_lifecycle.py#L122) |
| 権限を毎回照合し、取消後は同じトークンでも拒否する | — | [test_gateway_authorizer_rechecks_each_invocation](../../../packages/backend/tests/test_gateway_event.py#L7) |
| スタック削除イベントでDBを削除しない | — | [test_stack_deletion_preserves_database](../../../packages/backend/tests/test_gateway_event.py#L63) |
| API Gateway用の認可関数で、本人キー・別ユーザー・失効の判定を確認する | — | [test_gateway_scoped_key_authorizer](../../../packages/backend/tests/test_gateway_event.py#L70) |
| 管理者が追加・削除し、同一メールで再登録しても旧利用権を復活させない | — | [test_member_lifecycle](../../../packages/backend/tests/test_governance.py#L11) |
| 掲載内容の修正と仕様の変更を区別し、競合を検知し、削除後も監査を保持する | — | [test_listing_revisions](../../../packages/backend/tests/test_governance.py#L35) |
| 管理者・提供者の通知先を制御し、同じプロジェクトでも既読状態を利用者ごとに保持する | — | [test_notification_scope](../../../packages/backend/tests/test_governance.py#L77) |
| 同時実行の上限、通知のみ・停止・解除、次期間の回復、メトリクス集計とログの閲覧範囲を確認する | — | [test_alert_window_and_access_logs](../../../packages/backend/tests/test_governance.py#L117) |
| 同じ時刻の251件を複数ページに分けて全件取得し、重複・欠落と時差を確認する | — | [test_log_download_pages](../../../packages/backend/tests/test_governance.py#L189) |
| 管理者が同時刻の501件をカーソル非対応のDBで集計しても、失敗や二重計上が起きない。 | — | [test_admin_metrics_across_pages](../../../packages/backend/tests/test_governance.py#L238) |
| 接続確認の後、呼び出し情報をLambdaへ渡して応答を返す | — | [test_lambda_adapter](../../../packages/backend/tests/test_integrations.py#L12) |
| クエリと認証情報を保持してHTTPSの接続先に転送する | — | [test_https_adapter](../../../packages/backend/tests/test_integrations.py#L39) |
| 接続確認に失敗したAPIは下書きのまま残る | — | [test_failed_probe_keeps_draft](../../../packages/backend/tests/test_integrations.py#L72) |
| 本人と全体管理者の変更を兼務先に反映し、IDと監査の閲覧範囲を保持する。 | — | [test_profile_edits_filter_directory_and_audit](../../../packages/backend/tests/test_member_profiles.py#L12) |
| 既存のメール招待・アカウント行のない利用者は、任意の氏名を初回保存できる。 | — | [test_legacy_profile_first_edit](../../../packages/backend/tests/test_member_profiles.py#L129) |
| Cognitoだけにある利用者は確認時のsubが一致し、かつ有効なときだけ管理者が編集できる。 | — | [test_managed_cognito_only_account_requires_matching_subject](../../../packages/backend/tests/test_member_profiles.py#L163) |
| 移行時は public のスキーマ権限を変更せず、実行ロールに対象テーブルの権限を付与する | 既存の実行ロールだけを設定する<br>チャット用の読取ロールも設定する | [test_grants_public_tables_without_altering_the_schema](../../../packages/backend/tests/test_migrate.py#L17) |
| 内部参照の連鎖とJSON Pointerのエスケープを解決し、パス順を保つ。 | — | [test_resolves_path_item_references_in_order](../../../packages/backend/tests/test_openapi.py#L6) |
| 解決できないパスと拡張項目を飛ばし、有効なパスを返す。 | 自分自身を参照している<br>参照先が存在しない<br>外部ドキュメントを参照している<br>パス項目が配列になっている | [test_skips_invalid_path_item_without_losing_valid_paths](../../../packages/backend/tests/test_openapi.py#L34) |
| 公開スキーマの操作、入力項目、成功応答を日本語で取得し、再取得しても内容が変わらない。 | — | [test_published_schema_uses_business_names](../../../packages/backend/tests/test_openapi.py#L40) |
| 提供者は購読者に仕様内の操作を設定でき、解除すると個別設定が一覧から消える。 | — | [test_subscriber_operation_policy_is_scoped_and_resettable](../../../packages/backend/tests/test_operation_policy.py#L5) |
| 公開範囲、委任判断、個人・プロジェクト別申請、部署・役職の自動承認を確認する | — | [test_delegation_search_and_personal_isolation](../../../packages/backend/tests/test_org_access.py#L40) |
| Cognitoグループの除外が有効で、ポータルで新設したプロジェクトへの招待も反映される | — | [test_invitation_respects_identity_source](../../../packages/backend/tests/test_org_access.py#L156) |
| 利用者には有効な所属先だけを返し、兼務の追加と所属解除を同じセッションに反映する | — | [test_workspace_project_visibility](../../../packages/backend/tests/test_org_access.py#L184) |
| 招待時の所属が名簿に残っても、現在のグループから外れたプロジェクトは返さない | — | [test_workspace_honors_current_groups](../../../packages/backend/tests/test_org_access.py#L212) |
| 部署に所属する利用者のうち、担当リーダーだけが管理対象のプロジェクトも参照できる | — | [test_workspace_department_lead_projects](../../../packages/backend/tests/test_org_access.py#L229) |
| 同じ所属でも本人の履歴を分離し、配下の監査・絞り込み・出力と権限解除を検証する。 | — | [test_access_log_scopes](../../../packages/backend/tests/test_org_access.py#L241) |
| 環境別の承認条件を守り、複数の承認を指定の順序で行う | — | [test_three_environments_and_ordered_reviews](../../../packages/backend/tests/test_product_offers.py#L8) |
| 公開仕様の履歴を保持し、保管に失敗した公開を確定しない | — | [test_publication_history_and_archive_failures](../../../packages/backend/tests/test_product_offers.py#L85) |
| 同じ内部参照を使う複数のOpenAPIパスで操作を解決できる | — | [test_internal_path_item_reference_is_invokable](../../../packages/backend/tests/test_product_offers.py#L141) |
| HTTPの結果と原因から重要度を決め、対象APIと画面を安全に記録する。 | 正常に応答した呼び出しを記録する<br>権限不足の呼び出しを利用者起因に分類する<br>未処理例外をサーバー障害に分類する<br>保存仕様が壊れたときにデータ修正の手順を残す<br>入力値の型が違うときに利用者起因に分類する | [test_http_log](../../../packages/backend/tests/test_request_logs.py#L70) |
| 入口で拒否しても追跡IDを返し、未検証の利用者や画面を記録しない。 | — | [test_origin_denial](../../../packages/backend/tests/test_request_logs.py#L97) |
| 履歴の出力時にも記録時点の復旧手順を保ち、旧形式の行も読み出せる。 | — | [test_export_preserves_repair](../../../packages/backend/tests/test_request_logs.py#L110) |
| ポータル停止後のCognito障害では、操作した管理者と対象利用者を分けて復旧方法を記録する。 | — | [test_member_partial_deletion](../../../packages/backend/tests/test_request_logs.py#L128) |
| モデル呼び出しの失敗を元のAPI・画面・利用者に結び付け、質問本文を記録しない。 | — | [test_model_worker_error_has_request_context](../../../packages/backend/tests/test_request_logs.py#L183) |
| モデルにも同じJSON形式を同梱し、重み不一致時は復元作業を記録する。 | — | [test_packaged_model_reports_weight_repair](../../../packages/backend/tests/test_request_logs.py#L209) |
| 管轄部署の変更前後に呼び出すと、各部署のリーダーは実行時点で配下にあった記録を取得できる。 | — | [test_department_audit_uses_hierarchy_at_call_time](../../../packages/backend/tests/test_required_audit_scope.py#L7) |
| 認証方式に応じた手順で期限付きトークンを発行し、利用後は対象の認証情報だけを失効させる。 | 本人の短期Bearerで承認済みAPI全体を呼べる<br>共有の短期Bearerを指定のAPIで利用できる<br>アプリと本人の資格で指定のAPIを利用できる<br>共有アプリで指定したメンバーが承認済み操作を利用できる<br>プロジェクトのリーダーがシステム認証を発行し、利用者のログインなしで交換できる | [test_issue_use_and_retire_credentials](../../../packages/backend/tests/test_required_credentials.py#L49) |
| 提供APIと利用プロジェクトの両方で有効期間を制限したとき、短い方の上限が発行条件に反映される。 | — | [test_choose_shortest_scope_limit](../../../packages/backend/tests/test_required_credentials.py#L110) |
| 発行条件に一致しない設定で認証情報を発行できず、既存の認証情報一覧を維持する。 | 有効期間後の時刻を更新開始に選べない<br>既に提供終了したAPIを対象として発行しない<br>APIに存在しない操作は選んで発行できない<br>プロジェクトに所属しない利用者を対象にしたアプリ設定を保存しない | [test_invalid_issuance_keeps_project_credentials](../../../packages/backend/tests/test_required_credentials.py#L164) |
| 短期Bearerをポータルで更新しても認証情報は増えず、指定のAPIと有効期間を維持する。 | — | [test_portal_bearer_refresh_and_scope_after_renewal](../../../packages/backend/tests/test_required_credentials.py#L197) |
| 新設プロジェクトのメンバーには本人が選べる認証情報と、承認待ちで空の対象API一覧を示す。 | — | [test_project_with_no_approvals_can_see_empty_options](../../../packages/backend/tests/test_required_credentials.py#L225) |
| 従来キーを複数発行し、一つを失効させても同じプロジェクトの別のキーで利用を続けられる。 | 共有キーでプロジェクトの承認済みAPI全体を選べる<br>本人限定キーで指定したAPIを選べる | [test_legacy_credential_inventory_and_independent_revocation](../../../packages/backend/tests/test_required_credentials.py#L267) |
| 提供者が対象APIの有効期間を縮めると、長すぎる発行条件を拒み、新しい上限以内の発行を許可する。 | — | [test_shortened_api_limit_requires_shorter_credential](../../../packages/backend/tests/test_required_credentials.py#L292) |
| 承認されたAPIを呼び出せた本人も、権利の取消後はトークンを更新してもそのAPIを実行できない。 | — | [test_revoked_grant_applies_to_refreshed_bearer](../../../packages/backend/tests/test_required_credentials.py#L316) |
| API Docsで本人のログインを短期Bearerに交換し、元の期限までは直前のトークンでも呼び出せる。 | 希望するトークン種別を省略して短期Bearerを取得する<br>アクセストークンを指定してOAuth交換したあとも直前のトークンを利用できる | [test_oauth_exchange_keeps_original_token_valid](../../../packages/backend/tests/test_required_credentials.py#L367) |
| 個人と共有の両方で認証情報を発行すると、共有のメンバーと本人がそれぞれの範囲を確認できる。 | — | [test_whole_project_and_individual_inventories](../../../packages/backend/tests/test_required_credentials.py#L402) |
| 組織で定めた上限を守って発行し、更新開始時刻は指定した有効期間の中に限定する。 | — | [test_shorter_project_cap_rejects_invalid_refresh](../../../packages/backend/tests/test_required_credentials.py#L432) |
| 後任のプロジェクトリーダーは共有システム認証のシークレットを更新し、同じ資格名で継続運用できる。 | — | [test_project_leader_takes_over_shared_system_credential](../../../packages/backend/tests/test_required_credentials.py#L459) |
| 削除済みまたは存在しない認証情報の操作を再試行しても、同じプロジェクトの有効なキーを維持する。 | — | [test_retired_key_and_missing_key_do_not_change_other_issuances](../../../packages/backend/tests/test_required_credentials.py#L514) |
| API Docsの交換フォームで未対応の方式や種別を指定したとき、短期トークンを発行しない。 | トークン交換以外の方式は入力エラーとして返す<br>交換元の種類にIDトークンを選んだフォームを拒否する<br>アクセストークン以外の応答種別を指定したフォームを拒否する | [test_oauth_exchange_form_accepts_only_documented_token_types](../../../packages/backend/tests/test_required_credentials.py#L556) |
| 短期Bearer方式には更新するクライアントシークレットがなく、本人はポータルからトークンを更新できる。 | — | [test_personal_bearer_has_no_client_secret_to_rotate](../../../packages/backend/tests/test_required_credentials.py#L582) |
| リーダーがシステム認証を失効させた後はシークレットを再発行できず、一覧でも失効状態を保つ。 | — | [test_project_system_credential_cannot_be_rotated_after_retirement](../../../packages/backend/tests/test_required_credentials.py#L599) |
| 同名のパス引数を操作ごとに和名化し、依存から受ける検索件数の範囲と既定値を保持する。 | — | [test_portal_schema_localizes_operation_and_parameter_by_context](../../../packages/backend/tests/test_required_design_contract.py#L41) |
| 和名を適用しても配列と辞書の返却型・共通モデル参照・必須フィールドは元の仕様と一致する。 | — | [test_localized_schema_preserves_arrays_maps_responses_and_required_fields](../../../packages/backend/tests/test_required_design_contract.py#L62) |
| 厳格な設計チェックは和名を取得できない定義の位置を開発者に報告する。 | 和名を取得できない操作にはHTTPメソッドとパスを示す<br>和名のない新規モデルにはモデル名を示す<br>新しい項目だけの和名が不足した場合はモデル名と項目名を示す | [test_strict_design_check_identifies_the_missing_name](../../../packages/backend/tests/test_required_design_contract.py#L113) |
| 操作に和名があっても、引数の和名がなければその引数を含めて生成エラーを報告する。 | — | [test_missing_query_label_identifies_the_route_and_parameter](../../../packages/backend/tests/test_required_design_contract.py#L120) |
| 通常のOpenAPI生成は和名のない外部スキーマや追加メタデータを保持し、既知の操作を利用できる。 | — | [test_normal_openapi_keeps_unlabelled_extensions_and_non_operation_metadata](../../../packages/backend/tests/test_required_design_contract.py#L134) |
| 同じルーターを異なる接頭辞で公開しても各経路の和名、クエリの制約と明示した説明を保持する。 | — | [test_routing_prefixes_preserve_parameter_context_and_explicit_descriptions](../../../packages/backend/tests/test_required_design_contract.py#L160) |
| ソースを参照できない外部ハンドラーでは手動の操作説明と経路共通パラメータを保持する。 | — | [test_external_callable_keeps_published_schema_and_common_path_parameters](../../../packages/backend/tests/test_required_design_contract.py#L185) |
| 公開対象外の補助ルートは設計に出さず、複数の公開先で同じ応答モデルの参照を維持する。 | — | [test_openapi_ignores_hidden_routes_and_preserves_model_refs_for_each_mount](../../../packages/backend/tests/test_required_design_contract.py#L214) |
| 部署と管轄プロジェクトの利用状況に外部名簿の全ページを反映し、退会者と所属解除者を除く。 | — | [test_usage_combines_cognito_pages_without_reviving_removed_members](../../../packages/backend/tests/test_required_directory_usage.py#L14) |
| 部署の実績では直接付与した役職を保持し、他部署の利用者や存在しないグループを含めない。 | — | [test_department_usage_preserves_assigned_roles_and_excludes_other_projects](../../../packages/backend/tests/test_required_directory_usage.py#L78) |
| プロジェクトを移管すると移管先の実績に所属と役職を引き継ぎ、廃止した元の実績は開けない。 | — | [test_transferred_project_reports_only_its_current_membership](../../../packages/backend/tests/test_required_directory_usage.py#L134) |
| 従来のプロジェクト所属を実績画面に表示し、退会済みデモ利用者を標準の所属から復活させない。 | — | [test_local_directory_keeps_legacy_members_but_excludes_deleted_demo_accounts](../../../packages/backend/tests/test_required_directory_usage.py#L176) |
| 既定プロジェクトの移管後も旧グループや旧形式の所属から廃止したプロジェクトを再表示しない。 | — | [test_retired_configured_project_stays_hidden_with_stale_local_memberships](../../../packages/backend/tests/test_required_directory_usage.py#L195) |
| 外部名簿の続きがあるとき、公開カーソルで次ページに進み、各人のメールと識別子を保持する。 | — | [test_external_directory_pagination](../../../packages/backend/tests/test_required_member_directory.py#L42) |
| Cognitoで招待を受け付けた対象者のプロフィールを保存し、退会時も同じアカウントを操作する。 | 招待した利用者の氏名とメールアドレスを取得できる<br>提供者として招待した人も同じ名簿で退会できる | [test_external_invitation_and_retirement](../../../packages/backend/tests/test_required_member_directory.py#L91) |
| Cognitoで既存のメールアドレスを再招待すると競合を通知し、既存アカウントを削除しない。 | — | [test_duplicate_external_invitation_preserves_original_member](../../../packages/backend/tests/test_required_member_directory.py#L128) |
| 外部名簿が一時的に利用できなければ一覧APIはサービス障害を返し、復旧後に同じページを読める。 | — | [test_directory_temporarily_unavailable](../../../packages/backend/tests/test_required_member_directory.py#L143) |
| 招待先の役割を付与できなければ作成途中のアカウントを取り消し、同じ人を改めて招待できる。 | — | [test_failed_group_assignment_cleans_up_new_invitation](../../../packages/backend/tests/test_required_member_directory.py#L159) |
| Cognitoで登録した人を部署に所属させると、その識別子・ログイン名・役職で名簿を更新できる。 | — | [test_external_directory_source_for_membership](../../../packages/backend/tests/test_required_member_directory.py#L182) |
| 名簿に該当する利用者がいない場合は、組織への所属を作成しない。 | — | [test_unknown_cognito_member_cannot_be_assigned](../../../packages/backend/tests/test_required_member_directory.py#L224) |
| 外部名簿から退会済みの利用者を再編集したとき、対象者が見つからないことを管理者へ返す。 | — | [test_external_member_disappears_before_profile_edit](../../../packages/backend/tests/test_required_member_directory.py#L243) |
| 招待先のアカウントをまだ作成できなかった場合、復旧後に同じ内容で招待を完了できる。 | — | [test_account_creation_outage_can_be_retried](../../../packages/backend/tests/test_required_member_directory.py#L264) |
| 退会した人と同じメールで別の利用者が登録されても、以前の氏名や表示名を引き継がない。 | — | [test_external_and_locally_retired_members_listed_by_subject](../../../packages/backend/tests/test_required_member_directory.py#L285) |
| 外部名簿の退会処理後は、その利用者を組織の有効な所属として表示しない。 | — | [test_removed_cognito_group_member_stays_retired](../../../packages/backend/tests/test_required_member_directory.py#L317) |
| 外部名簿との通信・流量制限で一覧が取れない場合は、一時障害を示し、復旧後に再取得できる。 | 外部名簿の一時的な流量制限を503で返す<br>名簿サービスへの接続が途切れても同じページを再取得できる | [test_external_list_recovers_from_transient_errors](../../../packages/backend/tests/test_required_member_directory.py#L357) |
| 外部名簿で無効になった利用者を所属に追加しようとしても、有効な所属を作成しない。 | — | [test_disabled_external_user_is_not_assignable](../../../packages/backend/tests/test_required_member_directory.py#L381) |
| 再利用されたログイン名の現在の識別子が異なる場合、以前の会員としてプロフィールを変更しない。 | — | [test_external_username_lookup_keeps_distinct_subjects](../../../packages/backend/tests/test_required_member_directory.py#L404) |
| ポータルで新設したプロジェクトへ招待すると、外部グループの設定がなくても所属が作られる。 | — | [test_invitation_to_portal_project_without_external_group](../../../packages/backend/tests/test_required_member_directory.py#L430) |
| 外部のアカウントが消えた後に退会操作を繰り返しても、ポータルの会員資格は復活しない。 | — | [test_retirement_retry_after_remote_account_has_gone](../../../packages/backend/tests/test_required_member_directory.py#L451) |
| 以前の人と同じログイン名に別の識別子が割り当てられた場合、退会操作で後任を削除しない。 | — | [test_retirement_does_not_delete_replacement_username](../../../packages/backend/tests/test_required_member_directory.py#L489) |
| Cognito名簿から選んだ外部登録の利用者も、管理者が識別子とログイン名を照合して退会させられる。 | — | [test_external_only_member_can_retire](../../../packages/backend/tests/test_required_member_directory.py#L515) |
| 招待画面を開いてから対象プロジェクトが廃止されたとき、外部名簿に宛先だけの人を残さない。 | — | [test_invitation_with_unavailable_project_does_not_create_external_account](../../../packages/backend/tests/test_required_member_directory.py#L535) |
| 招待のロール付与と後片付けがともに失敗したら、復旧対象を運用担当者がログから確認できる。 | — | [test_incomplete_external_invitation_reports_required_recovery](../../../packages/backend/tests/test_required_member_directory.py#L556) |
| 同じ所属先の二人が通知を受け、一人が複数回開いても既読件数は本人の一件分だけ変わる。 | — | [test_independent_notification_counts](../../../packages/backend/tests/test_required_messages.py#L9) |
| 問い合わせを同じ受付番号で再送すると一件だけ残り、運営の回答は本人の履歴に反映される。 | 本文と回答が最短の二文字でも同じ受付に記録される<br>本文と回答が各二千文字でも全文を保持する | [test_retry_and_reply_in_inquiry_history](../../../packages/backend/tests/test_required_messages.py#L66) |
| 短すぎる問い合わせを訂正すると、元の受付番号で送信し直せる。 | — | [test_invalid_inquiry_does_not_consume_receipt](../../../packages/backend/tests/test_required_messages.py#L93) |
| 異なる質問を同じ受付番号に送っても元の質問を保持し、運営はその受付に回答できる。 | — | [test_receipt_reuse_and_answer_retry](../../../packages/backend/tests/test_required_messages.py#L107) |
| 二人が別々に相談すると各自の履歴には本人の受付だけが載り、管理者は双方を確認できる。 | — | [test_inquiry_history_separates_requesters](../../../packages/backend/tests/test_required_messages.py#L132) |
| 受付の確認が回答後になった場合も、同じ本文の再送は既存の回答を保持する。 | — | [test_response_retry_after_an_inquiry_has_been_answered](../../../packages/backend/tests/test_required_messages.py#L154) |
| 空白だけの問い合わせ・回答は本文として受理せず、利用者が本文を書き直すまでは履歴を変えない。 | — | [test_blank_question_and_reply_leave_history_unchanged](../../../packages/backend/tests/test_required_messages.py#L176) |
| 兼務する任意属性の値を追加・訂正・解除しても既存のプロジェクトと部署の権限を保つ。 | — | [test_metadata_assignments_can_be_corrected_without_adding_projects](../../../packages/backend/tests/test_required_metadata.py#L29) |
| 任意属性の名称を公開しても所属名簿を開示せず、値のリーダーは配下の名簿のみを確認できる。 | — | [test_public_value_names_do_not_expose_rosters_and_leader_scope_stays_in_tree](../../../packages/backend/tests/test_required_metadata.py#L75) |
| 分類値の名称が公開されていても一般利用者は定義・値・所属権限を変更できない。 | 非管理者による項目の公開設定と表示名変更を拒否する<br>非管理者による新しい分類値の作成を拒否する<br>非管理者による自身への分類値のリーダー付与を拒否する | [test_non_admin_cannot_change_metadata_definition_or_grant_roles](../../../packages/backend/tests/test_required_metadata.py#L136) |
| 公開名を持つ値を商品の対象にすると、下位の値だけを持つ人には見えず直接の所属変更が反映される。 | — | [test_public_metadata_restricts_catalog_to_direct_value_members](../../../packages/backend/tests/test_required_metadata.py#L150) |
| 別項目の値への移管を拒否し、元項目の所属・役割とプロジェクト権限を維持する。 | — | [test_metadata_hierarchy_cannot_move_members_into_a_different_attribute](../../../packages/backend/tests/test_required_metadata.py#L201) |
| 未定義の項目、他項目の親、循環する親を拒否し、既存の分類値と所属を維持する。 | — | [test_invalid_attribute_hierarchy_leaves_existing_values_and_roles_intact](../../../packages/backend/tests/test_required_metadata.py#L224) |
| 利用者が所属する分類値の削除を拒否し、所属を解除した後はその値だけを削除できる。 | — | [test_value_in_use_must_be_released_before_removal](../../../packages/backend/tests/test_required_metadata.py#L245) |
| 属性のキーや表示名が公開された制約の範囲外なら入力エラーとなり項目一覧に追加しない。 | 公開契約の形式に合わない項目キーを拒否する<br>63文字を超えるキーを拒否する<br>空の表示名で属性を作成しない<br>120文字を超える表示名を拒否する | [test_invalid_metadata_keys_and_labels_are_not_registered](../../../packages/backend/tests/test_required_metadata.py#L281) |
| 利用中の値の名称を訂正しても識別子と所属を維持し、別項目への付け替えを拒否する。 | — | [test_attribute_value_identity_survives_rename_and_cannot_be_retyped](../../../packages/backend/tests/test_required_metadata.py#L291) |
| デモのOpenAPIは利用者招待の操作と入力項目を公開設計書と同じ和名で説明する。 | — | [test_demo_openapi_has_japanese_operation_and_input_labels](../../../packages/backend/tests/test_required_openapi_labels.py#L2) |
| 招待時の氏名・表示名は所属一覧に載り、管理者による変更と退会は対象者に反映される。 | 利用者として招待して会員一覧に反映する<br>提供者として招待して会員一覧に反映する | [test_invitation_profile_and_retirement](../../../packages/backend/tests/test_required_people.py#L22) |
| 本人のプロフィール変更が古い編集画面から失われず、氏名を消しても本人の識別子は変わらない。 | — | [test_self_edit_conflict_and_clear](../../../packages/backend/tests/test_required_people.py#L82) |
| 自動承認の環境でも規約と必須の回答を確認し、受理した同意と回答を申請に保存する。 | — | [test_automatic_offer_requires_terms_and_registered_answer](../../../packages/backend/tests/test_required_products.py#L33) |
| 却下または取り下げの理由を本人が確認でき、同じ商品と環境に再申請できる。 | 提供者がプロジェクトの申請を却下すると理由が残り再申請できる<br>申請者が本人の申請を取り下げると理由が残り再申請できる | [test_request_decision_and_reapplication](../../../packages/backend/tests/test_required_products.py#L94) |
| 操作の追加・変更・削除を含む仕様を再公開すると、利用者は版ごとの説明と差分を読める。 | — | [test_spec_revision_and_release_history](../../../packages/backend/tests/test_required_products.py#L128) |
| 利用中のプロジェクトを移管すると、利用者の所属、商品の公開範囲、利用権と監視設定を引き継ぐ。 | — | [test_project_transfer_with_established_usage](../../../packages/backend/tests/test_required_products.py#L155) |
| 部署リーダーの判断だけでは承認は終わらず、提供者の最終承認で両者の理由を確認できる。 | 所属部署の上位リーダーから提供者へ回す<br>指定部署のリーダーから提供者へ回す | [test_two_stage_review](../../../packages/backend/tests/test_required_products.py#L247) |
| 限定商品のカタログは子部署の所属を反映し、所属変更後も現在の公開範囲で検索結果を返す。 | — | [test_visible_catalog_moves_with_department_membership](../../../packages/backend/tests/test_required_products.py#L308) |
| 提供者が新規受付を停止しても利用権を維持し、再掲載後は別のプロジェクトから新しく申請できる。 | — | [test_provider_stops_and_reopens_new_applications](../../../packages/backend/tests/test_required_products.py#L349) |
| 提供者が商品名を変更した後、古い版番号で削除しても新しい商品と利用者向けの掲載を保持する。 | — | [test_revision_conflict_does_not_remove_published_product](../../../packages/backend/tests/test_required_products.py#L397) |
| 限定公開と自動承認に使う部署を移管しても、移管した配下の人は商品を見つけて申請できる。 | — | [test_department_transfer_preserves_visibility_and_auto_approval](../../../packages/backend/tests/test_required_products.py#L421) |
| 同じ商品の利用申請が両方のプロジェクトにある場合、移管競合は承認結果や理由を上書きしない。 | — | [test_overlapping_project_grants_do_not_overwrite_decisions](../../../packages/backend/tests/test_required_products.py#L468) |
| 提供プロジェクトの組織を移管しても既存商品の公開名と提供の責任を後継組織から確認できる。 | — | [test_existing_api_settings_survive_project_transfer](../../../packages/backend/tests/test_required_products.py#L526) |
| 対応対象外のOpenAPI形式を登録しようとしても、公開カタログに不完全な商品は追加されない。 | — | [test_product_with_unsupported_contract_stays_out_of_catalog](../../../packages/backend/tests/test_required_products.py#L552) |
| 利用条件の表示後に規約を更新した場合、古い版への同意では申請を受け付けず、新版への同意を保存する。 | — | [test_updated_terms_require_fresh_consent](../../../packages/backend/tests/test_required_products.py#L566) |
| チームに所属していない利用者も個人ワークスペースで申請し、本人用の認証情報で承認された商品を呼べる。 | — | [test_personal_workspace_solicits_and_uses_a_single_api](../../../packages/backend/tests/test_required_products.py#L600) |
| 提供者が役職を自動承認条件にすると、申請者の実際の所属上の役職に応じて審査結果が変わる。 | 役職が指定条件に一致しなければ提供者の判断を待つ<br>所属の役職が指定条件に一致すれば自動承認する | [test_title_based_auto_approval](../../../packages/backend/tests/test_required_products.py#L663) |
| プロジェクト内で本人限定の承認を得た人は、チームの承認がなくても本人限定キーで利用できる。 | — | [test_personal_approval_as_shared_project_member](../../../packages/backend/tests/test_required_products.py#L702) |
| 部署の有効期間上限をプロジェクトが継承し、個別上限を消すと上位の値に戻る。 | — | [test_lifetime_inheritance_and_reset](../../../packages/backend/tests/test_required_usage_settings.py#L7) |
| 提供者が一部の操作、全解除、継承を順に設定すると、商品詳細で本人に示す操作も切り替わる。 | — | [test_provider_changes_and_clears_individual_operations](../../../packages/backend/tests/test_required_usage_settings.py#L44) |
| 到達時に一回だけ通知し、上限を変更すると次の呼び出しを新しい件数として集計する。 | 通知のみなら上限到達後も呼び出せて、通知は一回に限られる<br>停止ありなら上限到達の次の呼び出しを止め、設定の更新で再開する | [test_alert_threshold_and_counter_reset](../../../packages/backend/tests/test_required_usage_settings.py#L86) |
| プロジェクトの管轄が変わると、後継部署の短い上限が発行候補に反映される。 | — | [test_inherited_limit_after_department_reorganization](../../../packages/backend/tests/test_required_usage_settings.py#L132) |
| 担当リーダーが部署を停止すると配下の呼び出しも止まり、再開後は同じ認証情報で利用を続けられる。 | — | [test_project_pause_and_resume_preserves_active_key](../../../packages/backend/tests/test_required_usage_settings.py#L164) |
| 上位部署とプロジェクトを兼務してから片方を外しても、残る所属の役職と管理権限を保持する。 | — | [test_direct_and_concurrent_memberships](../../../packages/backend/tests/test_required_workspace.py#L31) |
| 新しい組織を改名し、リーダーが停止・再開すると、一覧から各時点の状態を確認できる。 | プロジェクトの停止と再開を一覧に反映する<br>部署の停止と再開を一覧に反映する | [test_unit_lifecycle](../../../packages/backend/tests/test_required_workspace.py#L79) |
| 所属のある組織は同種の移管先に統合でき、旧組織は一覧から消える。 | プロジェクトの所属を移管先に引き継ぐ<br>部署の所属と配下の組織を移管先に引き継ぐ | [test_transfer_of_affiliated_unit](../../../packages/backend/tests/test_required_workspace.py#L112) |
| 利用を開始する前に空の組織を廃止すると、組織一覧に表示されなくなる。 | — | [test_empty_unit_can_be_removed](../../../packages/backend/tests/test_required_workspace.py#L138) |
| 子部署とプロジェクトが残る部署は削除できず、移管後は両方の親が移管先に変わる。 | — | [test_in_use_department_requires_transfer](../../../packages/backend/tests/test_required_workspace.py#L149) |
| 移管先が使えない場合は変更を拒み、元の組織、親子関係、所属をすべて保持する。 | 移管元自身を指定しても組織を消さない<br>子孫の部署を移管先にして階層を循環させない<br>部署の後継にプロジェクトを指定した場合に部署の所属を維持する<br>未登録の移管先へ組織や所属を移さない | [test_invalid_transfer_preserves_directory](../../../packages/backend/tests/test_required_workspace.py#L195) |
| 重複した所属で移管が競合した場合は、両プロジェクトの既存の所属を保持する。 | — | [test_conflicting_transfer_keeps_both_projects](../../../packages/backend/tests/test_required_workspace.py#L212) |
| 親を変更できないとき、既存の部署名と親子関係は維持される。 | 部署自身を親にする編集を拒否する<br>子部署を親にする編集を拒否する<br>プロジェクトを部署の親にする編集を拒否する<br>存在しない部署への付け替えを拒否する | [test_invalid_parent_keeps_hierarchy](../../../packages/backend/tests/test_required_workspace.py#L268) |
| 所属先が既に廃止された場合は新しい所属を作らず、既存の所属を維持する。 | — | [test_missing_membership_target](../../../packages/backend/tests/test_required_workspace.py#L288) |
| 移管元で既に解除した所属があっても、後継部署で現在有効な役職とリーダー設定は保持される。 | — | [test_department_transfer_preserves_successor_leadership](../../../packages/backend/tests/test_required_workspace.py#L305) |
| 移管済みの旧組織を再度指定しても、後継組織に引き継いだ所属を二重に移管しない。 | — | [test_repeated_transfer_keeps_successor_membership](../../../packages/backend/tests/test_required_workspace.py#L332) |
| 二つのプロジェクトに別々の有効期間上限があるとき、移管競合によってどちらの設定も失われない。 | — | [test_transfer_conflicting_token_lifetime_settings](../../../packages/backend/tests/test_required_workspace.py#L357) |
| 旧版の出品を同じIDで更新し、再実行後も承認済みの商品がSQLiteの配送状況を返す。 | — | [test_seed_replaces_old_contract_and_calls_product](../../../packages/backend/tests/test_sample_catalog.py#L6) |
| 語句・意味の両方で業務APIを検索し、同義語を含めて順位付けする | — | [test_hybrid_retrieval](../../../packages/backend/tests/test_search_rank.py#L18) |
| 閲覧可能なOpenAPIタグの説明だけを意味検索に使う | — | [test_visible_openapi_tags_supply_custom_meaning](../../../packages/backend/tests/test_search_rank.py#L33) |
| 管理者だけが空の部署を子から削除でき、廃止した識別子は再作成できない。 | — | [test_unit_retirement](../../../packages/backend/tests/test_unit_lifecycle.py#L5) |
| 提供・利用を既存プロジェクトへ移管し、公開状態・旧URLと新URLでの認証済み呼び出しを確認する。 | — | [test_project_transfer](../../../packages/backend/tests/test_unit_lifecycle.py#L25) |
| 任意属性は所属単位で閲覧でき、グループのリーダーや役職を業務権限に引き継がない。 | — | [test_metadata_groups_and_visibility](../../../packages/backend/tests/test_user_metadata.py#L5) |
| 限定公開の任意属性条件を移管時に引き継ぎ、所属を解除すると閲覧できなくなる。 | — | [test_metadata_audience_and_transfer](../../../packages/backend/tests/test_user_metadata.py#L64) |

### フロントエンド（231項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| 過去分の推定時刻と実測時刻を区別し、質問には選んだ記録の結果と識別子で答える。 | — | [test_detail_timestamps_and_answers](../../../packages/frontend/tests/test_access_log_detail.py#L32) |
| 共有用URLから記号を含む元のIDと閲覧範囲を復元し、1件だけを読み込む。 | — | [test_detail_link_preserves_scope_and_id](../../../packages/frontend/tests/test_access_log_detail.py#L48) |
| 次ページ確認用の21件目を表に出さず、最終ページで次への案内を消す。 | — | [test_log_page_shows_only_requested_rows](../../../packages/frontend/tests/test_access_log_detail.py#L62) |
| 前のページに戻る間に新しい呼び出しがあっても、検索期間を固定して同じ行を表示する。 | — | [test_paging_back_keeps_the_time_window](../../../packages/frontend/tests/test_access_log_detail.py#L94) |
| ログ取得に失敗したときも認証ヘッダーを送り、ダウンロードを中止して理由を表示する。 | — | [test_failed_log_download_reports_error](../../../packages/frontend/tests/test_access_log_download.py#L12) |
| 承認済みの申請だけを候補にし、失効した商品の直接指定では仕様を取得しない。 | — | [test_console_reads_only_approved_spec](../../../packages/frontend/tests/test_api_client.py#L14) |
| 本人に許可された操作と承認環境を選べ、操作制限のある委任認証は候補から外れる。 | — | [test_only_allowed_operations_and_environments](../../../packages/frontend/tests/test_api_client.py#L35) |
| ログインだけの実行を拒否し、選択した委任認証でOAuth交換した短期トークンを送る。 | — | [test_identity_and_delegated_token](../../../packages/frontend/tests/test_api_client.py#L66) |
| 承認済み環境だけを表示し、同時実行でも同じ商品の個人認証情報を再利用する。 | — | [test_trial_uses_approved_environments_and_reuses_personal_credential](../../../packages/frontend/tests/test_api_client.py#L96) |
| URL直接指定では入力したヘッダーと本文だけを使い、Cookieとリダイレクトを無効にする。 | — | [test_manual_request_uses_only_entered_headers](../../../packages/frontend/tests/test_api_client.py#L144) |
| 送信先やヘッダーの形式が不正な場合やGETに本文がある場合は送信前にエラーになる。 | — | [test_invalid_manual_requests_are_rejected](../../../packages/frontend/tests/test_api_client.py#L175) |
| 呼び出し先にAPI識別名を使い、既存商品で識別名が未設定ならUUIDを使う。 | — | [test_invocation_path_uses_product_slug](../../../packages/frontend/tests/test_components.py#L32) |
| チャットの候補と操作手順に、対応する商品・ガイドのリンクが付く。 | — | [test_chat_product_and_guide_are_linked](../../../packages/frontend/tests/test_components.py#L46) |
| 提供者の検索結果で一致したガイドを先頭に表示し、件数を読み上げる。 | — | [test_guide_results_render_matching_cards_only](../../../packages/frontend/tests/test_components.py#L73) |
| ガイドの条件をクリアすると全件に戻り、検索欄にフォーカスする。 | — | [test_guide_reset_restores_role_and_keyboard_focus](../../../packages/frontend/tests/test_components.py#L87) |
| ユーザー管理の手順は閲覧でき、管理画面へのボタンは管理者にだけ表示する。 | — | [test_guide_article_shows_admin_navigation_only_to_admins](../../../packages/frontend/tests/test_components.py#L123) |
| 全手順でサンプルデータから実画面の操作部品を描画し、画面例の内側だけを操作不能にする。 | — | [test_each_guide_renders_inert_example](../../../packages/frontend/tests/test_components.py#L156) |
| OpenAPIの型定義を参照し、クエリ入力欄に既定値の例を表示する。 | — | [test_operation_parameter_renders_openapi_default](../../../packages/frontend/tests/test_components.py#L184) |
| パスの予約文字をエンコードし、配列とオブジェクトを指定形式で送る。 | — | [test_operation_location_encodes_path_and_query_values](../../../packages/frontend/tests/test_components.py#L194) |
| 必須のクエリ入力が空なら、入力項目名を示して送信を止める。 | — | [test_operation_location_requires_mandatory_query](../../../packages/frontend/tests/test_components.py#L216) |
| 公開履歴の表に版番号・公開日・変更された操作を表示し、空の差分は省く。 | — | [test_publication_history_shows_release_changes](../../../packages/frontend/tests/test_components.py#L223) |
| ログインフォームに入力ラベルと自動入力の用途を示し、Enterで送信できる。 | — | [test_login_form_uses_native_labels_and_keyboard_submit](../../../packages/frontend/tests/test_components.py#L259) |
| 送信したURL・形式・本文をシェルで再現し、短期トークンは変数で参照する。 | — | [test_curl_reuses_request_without_exposing_token](../../../packages/frontend/tests/test_components.py#L283) |
| 条件を適用しても入力欄は折りたたみ、閉じた見出しには期間と絞り込み状態を表示する。 | — | [test_log_search_starts_collapsed_and_shows_active_conditions](../../../packages/frontend/tests/test_components.py#L313) |
| メトリクス取得が失敗しても件数とログを表示し、再読み込みで業務メニューのない利用状況が表示される。 | — | [test_dashboard_recovers_from_metrics_failure](../../../packages/frontend/tests/test_dashboard.py#L19) |
| 応答を受け取れずに再送しても受付番号を再利用し、次の新規送信には別の番号を使う。 | — | [test_retry_reuses_pending_inquiry_id](../../../packages/frontend/tests/test_inquiry_form.py#L12) |
| 短すぎる本文と文字数の上限を超えた本文は運営へ送信しない。 | — | [test_invalid_question_is_not_submitted](../../../packages/frontend/tests/test_inquiry_form.py#L35) |
| 自分の履歴の2ページ目から送信すると、受付番号と先頭ページの新しい問い合わせが表示される。 | — | [test_inquiries_page_shows_receipt_and_latest_tickets](../../../packages/frontend/tests/test_inquiry_form.py#L48) |
| 管理者と提供者の通知先には登録された名称を表示し、送信には識別子を使う。 | — | [test_notification_recipient_dropdown_uses_display_names](../../../packages/frontend/tests/test_notification_recipients.py#L10) |
| JSON Pointerを解決し、同名のパス共通パラメーターを操作側で上書きする | — | [test_operation_overrides_path_parameter_and_resolves_pointer](../../../packages/frontend/tests/test_openapi_fields.py#L8) |
| 初回パスワードの変更から認証アプリ登録まで、各応答のセッションを次の処理に渡す。 | — | [test_invitation_and_totp_setup](../../../packages/frontend/tests/test_portal_login.py#L18) |
| 登録済みの利用者は確認コードを間違えても同じ画面で再入力できる。 | — | [test_returning_user_retries_mfa](../../../packages/frontend/tests/test_portal_login.py#L66) |
| 再設定コードを受け取った利用者は新しいパスワードを設定してログイン画面に戻れる。 | — | [test_reset_returns_to_signin](../../../packages/frontend/tests/test_portal_login.py#L88) |
| パスワードは認証サービスへのPOST本文だけで送信し、エラーは日本語で表示する。 | — | [test_credentials_sent_to_identity_service](../../../packages/frontend/tests/test_portal_login.py#L109) |
| 利用者には本人の編集欄を表示し、他者のプロフィールの読み込みと編集を制限する。 | — | [test_profile_reads_only_the_allowed_member](../../../packages/frontend/tests/test_profile_screen.py#L12) |
| プロフィール更新で読み込み時の版を送り、空に戻した表示名を解除する。 | — | [test_profile_save_preserves_revision_and_clears_blank_names](../../../packages/frontend/tests/test_profile_screen.py#L53) |
| 役割と業務を入力すると目的の画面に進む手順が候補に含まれる。 | 読み取り権限についての言い換えから提供APIの手順を探せる。<br>認証方式を指定すると利用者向けの発行手順を探せる。<br>ユーザー追加の操作から管理者向けの招待手順を探せる。 | [test_search_by_work_and_role](../../../packages/frontend/tests/test_required_guide.py#L60) |
| 該当する手順がないときは件数をゼロと示して再検索を案内する。 | — | [test_guide_search_no_match](../../../packages/frontend/tests/test_required_guide.py#L68) |
| ガイド一覧の各手順は操作後の確認方法と入力できない画面例を持ち、対象画面を案内する。 | — | [test_every_guide_has_an_inert_example_and_ordered_steps](../../../packages/frontend/tests/test_required_guide.py#L82) |
| 存在しない手順のリンクを開くと一覧へ戻る案内が表示される。 | — | [test_missing_article_leads_back_to_the_index](../../../packages/frontend/tests/test_required_guide.py#L120) |
| 役割に合わせて日常操作と監査・管理の入口を表示する。 | 利用者には検索・申請とガイドの入口を示す。<br>提供者には出品と届いた利用申請の入口を示す。<br>管理者には利用者・組織管理と利用状況の入口を示す。<br>監査担当には監査履歴と利用状況の入口を示す。 | [test_role_navigation](../../../packages/frontend/tests/test_required_guide.py#L161) |
| 提供者のガイドでは誰でも見本を読め、担当者にだけ操作画面への入口を表示する。 | 提供者が出品ガイドを開けば、その場から提供APIの管理画面へ進める。<br>利用者も出品の見本を読めるが、担当外の管理操作には進めない。 | [test_provider_guide_keeps_its_sample_separate_from_the_real_management_screen](../../../packages/frontend/tests/test_required_guide.py#L195) |
| 起動時に配備されたAPIの入口と設定を読み込み、保存済みのログインがある場合に本人を取得する。 | 未ログインなら本人の情報を要求せずログイン設定を取得する。<br>既存のログインがあれば本人の情報を更新する。 | [test_start_loads_portal_configuration_and_restores_a_session](../../../packages/frontend/tests/test_required_guide_boot.py#L52) |
| 未読件数の更新でログイン中の利用者のベルに最新の件数を反映する。 | — | [test_notification_poll_updates_signed_in_readers_badge](../../../packages/frontend/tests/test_required_guide_boot.py#L74) |
| 未ログインまたはページが非表示のとき、ベルの個人別件数の更新を待機する。 | 未ログインなら利用者個人の未読件数を取りに行かない。<br>バックグラウンドの画面では未読表示の取得を待つ。 | [test_only_a_visible_authenticated_screen_polls_personal_notices](../../../packages/frontend/tests/test_required_guide_boot.py#L110) |
| リクエストIDを得られないAPIエラーは画面に理由を返し、対象と分類をブラウザーに記録する。 | 入力不備は内容を伝え、WARNの画面ログを記録する。<br>期限切れのログインは通知し、使えない資格情報を破棄する。<br>一時障害は対象APIとHTTP状態をERRORの画面ログに記録する。 | [test_service_error_with_no_trace_id_is_visible_to_the_operator](../../../packages/frontend/tests/test_required_guide_client.py#L37) |
| 画面で起きた処理エラーは、対象API・画面の処理・指定したリクエストIDで照合できる。 | — | [test_ui_report_can_be_correlated_to_an_api_response](../../../packages/frontend/tests/test_required_guide_client.py#L69) |
| 接続先の失敗応答がJSONでなくても、HTTP状態を含む案内を返す。 | — | [test_non_json_failure_retains_http_status](../../../packages/frontend/tests/test_required_guide_client.py#L92) |
| 認証コードはユーザープールに直接POSTし、失敗時には次の操作を日本語で案内する。 | 確認コードを認証APIへ直接送り成功を受け取る。<br>確認コードが違うときは新しいコードの入力を日本語で促す。<br>認証サービスの一時障害は日本語で再ログインを案内する。 | [test_user_pool_directly_receives_the_authenticator_code](../../../packages/frontend/tests/test_required_guide_client.py#L135) |
| 検索した商品とガイドに元情報へのリンクを付け、質問への回答と操作手順を表示する。 | — | [test_chat_cites_each_product_and_guide](../../../packages/frontend/tests/test_required_guide_home.py#L12) |
| 候補を返せない回答では、その理由を伝えて商品や手順のリンクを表示しない。 | 候補がない場合は検索結果の説明だけを表示する。<br>扱えない質問には対応する範囲の案内を表示する。<br>処理の失敗時に商品や手順を表示せず案内を伝える。 | [test_chat_explains_a_reply_without_sources](../../../packages/frontend/tests/test_required_guide_home.py#L76) |
| 作成中のチャットは同じ受付番号で再確認し、確定した回答を返す。 | — | [test_polling_keeps_the_receipt_until_ready](../../../packages/frontend/tests/test_required_guide_home.py#L85) |
| 問い合わせを開くと入力欄と送信操作が現れ、送信前には受付を表示しない。 | — | [test_chat_home_opens_an_unsent_inquiry](../../../packages/frontend/tests/test_required_guide_home.py#L99) |
| ログインの各段階で必要な入力を日本語ラベルと自動入力の用途で示す。 | ログインには利用者名と現在のパスワードを入力する。<br>招待直後は新しいパスワードを確認用にも入力する。<br>再設定の開始画面では利用者名を入力して確認コードを送る。<br>再設定には届いたコードと新しいパスワードを指定する。<br>認証アプリの登録は確認コードを入力して確定する。<br>二要素認証ではアプリのコードを入力してログインする。 | [test_login_forms_explain_the_current_step](../../../packages/frontend/tests/test_required_guide_home.py#L160) |
| 質問を送ったら受付番号で回答を一度取得し、会話に元の質問と回答を残す。 | — | [test_chat_submit_keeps_the_question_and_renders_the_received_answer](../../../packages/frontend/tests/test_required_guide_home.py#L218) |
| 問い合わせを開いただけでは送信せず、入力した利用者が送信して初めて受付となる。 | — | [test_only_explicit_inquiry_submission_contacts_the_operator](../../../packages/frontend/tests/test_required_guide_home.py#L260) |
| 空の質問や受付の一時障害では、会話を再開でき問い合わせを自動送信しない。 | 空の入力はチャット受付に送らない。<br>チャットの受付障害を伝え、次の質問を入力できる状態に戻す。 | [test_chat_handles_empty_input_and_service_failure](../../../packages/frontend/tests/test_required_guide_home.py#L316) |
| 詳細から処理時間を質問し、問い合わせを送ると同じリクエストIDを本文に含める。 | — | [test_log_question_and_inquiry_refer_to_the_same_request](../../../packages/frontend/tests/test_required_guide_home.py#L355) |
| 回答の作成中は送信を無効にし、同じ質問を二重受付せずに結果を表示する。 | — | [test_waiting_for_a_chat_answer_prevents_a_second_submission](../../../packages/frontend/tests/test_required_guide_home.py#L414) |
| 問い合わせ送信が一時的に失敗したら、内容とエラーを残し利用者による再送を受け付ける。 | — | [test_failed_inquiry_can_be_reviewed_before_the_user_retries](../../../packages/frontend/tests/test_required_guide_home.py#L460) |
| 回答が長時間作成中のままなら待機を終え、あとで再試行できるよう案内する。 | — | [test_chat_pending_too_long_returns_a_retry_message](../../../packages/frontend/tests/test_required_guide_home.py#L500) |
| チャットの回答を待つ間に別画面に移った場合、遅れて届く回答で現在の画面を描画し直さない。 | — | [test_late_reply_preserves_the_readers_new_page](../../../packages/frontend/tests/test_required_guide_home.py#L513) |
| 受付を待つ間に同じ問い合わせの送信操作が重なっても、受付は一件にとどまる。 | — | [test_an_inquiry_being_submitted_cannot_be_sent_twice](../../../packages/frontend/tests/test_required_guide_home.py#L532) |
| 利用状況の表と棒は、指定した表示指標とUTCの時間帯を示す。 | 件数の表と棒に呼び出し総数を示す。<br>エラーを選ぶと失敗した件数を示す。<br>拒否を選ぶと拒否された件数を示す。<br>平均応答時間をミリ秒で示す。 | [test_metrics_show_the_selected_measure_for_each_utc_bucket](../../../packages/frontend/tests/test_required_guide_metrics.py#L48) |
| 利用実績がない期間はUTCの範囲と空の結果を表示する。 | — | [test_empty_period_identifies_the_absence_of_calls](../../../packages/frontend/tests/test_required_guide_metrics.py#L73) |
| 日付をまたぐ棒を選ぶと、APIとプロジェクトの条件を保ってその区間のログへ移る。 | — | [test_drilldown_carries_only_the_selected_utc_interval](../../../packages/frontend/tests/test_required_guide_metrics.py#L87) |
| API・環境・プロジェクトと応答コードを選ぶと、指定の条件・期間・間隔で集計を取得する。 | 開始・終了を指定したらその区間を集計する。<br>相対期間を選んだら指定時間数のUTC区間を集計する。 | [test_selected_metric_filters_reach_the_api](../../../packages/frontend/tests/test_required_guide_metrics.py#L124) |
| ログインした利用者に所属名・ガイドの現在地とログアウトを表示する。 | — | [test_header_and_current_page_for_an_authenticated_reader](../../../packages/frontend/tests/test_required_guide_navigation.py#L20) |
| 未ログインでガイドを開くと、製品名が分かるログインフォームで案内する。 | — | [test_header_offers_signin_for_anonymous_reader](../../../packages/frontend/tests/test_required_guide_navigation.py#L43) |
| モバイルメニューの開閉は利用者と支援技術の両方に同じ状態を伝える。 | — | [test_small_screen_menu_exposes_expanded_and_collapsed_states](../../../packages/frontend/tests/test_required_guide_navigation.py#L62) |
| ライト・ダークを選ぶと選択した表示モードを文書に反映しブラウザーに記憶する。 | — | [test_theme_is_applied_and_remembered](../../../packages/frontend/tests/test_required_guide_navigation.py#L79) |
| 初回パスワードの確認結果に応じて、ログインを確定するか入力をやり直す。 | 初回のパスワードが一致するとログインを完了できる。<br>確認入力が一致しなければ認証を送信せず再入力を案内する。 | [test_initial_password_requires_confirmation_before_login](../../../packages/frontend/tests/test_required_guide_navigation.py#L110) |
| モバイルの検索でカタログへ進むと、検索語を引き継ぎメニューを閉じる。 | — | [test_search_from_mobile_navigation_opens_catalog_with_query](../../../packages/frontend/tests/test_required_guide_navigation.py#L154) |
| デモの利用者として入ると本人の所属を読み込み、ログアウトでホームの匿名状態に戻る。 | — | [test_demo_login_and_logout_restore_anonymous_home](../../../packages/frontend/tests/test_required_guide_navigation.py#L172) |
| 追加確認の回答は最初のログインと同じユーザープールと継続セッションに送り、成功後にログインする。 | 認証アプリの確認コードを招待先利用者の継続セッションで送る。<br>初回パスワードを同じ利用者の継続セッションで設定する。 | [test_login_challenge_continues_the_same_user_pool_session](../../../packages/frontend/tests/test_required_guide_navigation.py#L223) |
| 認証サービスから資格情報も次の操作も返らないときは、再ログインを日本語で案内する。 | — | [test_incomplete_authentication_asks_for_a_new_login](../../../packages/frontend/tests/test_required_guide_navigation.py#L256) |
| ガイド記事のブックマークは対象の内容を表示し、元の一覧に戻れる。 | 共有されたガイドURLから認証情報の手順を直接開ける。<br>見つからないガイドでは一覧へ戻る案内を表示する。 | [test_guide_article_can_be_opened_from_a_bookmark](../../../packages/frontend/tests/test_required_guide_navigation.py#L285) |
| 現在の利用者区分を日本語で識別できる。 | 一般利用者に利用者の役割名を表示する。<br>提供プロジェクトを担当する人には提供者の役割名を表示する。<br>全体監査権限を持つ人には監査担当の役割名を表示する。<br>全体管理権限を持つ人には管理者の役割名を表示する。 | [test_header_identifies_the_current_role](../../../packages/frontend/tests/test_required_guide_navigation.py#L333) |
| 画面を狭めるとメニューを折り畳み、十分に広くしたときはメニューを表示する。 | — | [test_mobile_breakpoint_closes_navigation_and_desktop_reveals_it](../../../packages/frontend/tests/test_required_guide_navigation.py#L342) |
| ローカルのデモでは業務の役割を選ぶか追加済み利用者のメールアドレスでログインできる。 | — | [test_demo_login_lets_the_reader_choose_a_role_or_invited_user](../../../packages/frontend/tests/test_required_guide_navigation.py#L355) |
| 画面操作の失敗を利用者と運用担当に伝え、再操作できる状態に戻す。 | 入力内容を見直すケースはWARNとし、操作をやり直せる状態に戻る。<br>予想しない画面エラーをERRORとし、利用者に結果を表示する。 | [test_failed_ui_action_releases_the_page_and_reports_its_severity](../../../packages/frontend/tests/test_required_guide_navigation.py#L393) |
| ログイン後に別の画面に進むと、最新の所属と本人の未読件数を読み込む。 | — | [test_navigation_refreshes_personal_profile_and_unread_count_after_login](../../../packages/frontend/tests/test_required_guide_navigation.py#L425) |
| 認証アプリの初回登録でコードを間違えても、同じ登録画面で新しいコードを確認してログインできる。 | — | [test_totp_enrollment_can_retry_a_mistyped_code](../../../packages/frontend/tests/test_required_guide_navigation.py#L451) |
| 処理結果や存在しないページを表示しても共通メニューから次の仕事へ移れる。 | 操作完了のメッセージを現在の画面で確認できる。<br>操作に失敗しても画面に日本語で理由を示す。<br>ブックマークの画面が存在しない場合はガイドとメニューに戻れる。 | [test_portal_feedback_and_missing_pages_preserve_navigation](../../../packages/frontend/tests/test_required_guide_navigation.py#L508) |
| パスワードを忘れた利用者は再設定フォームへ進み、コードを送る前にログインへ戻れる。 | — | [test_forgot_password_link_can_return_to_the_original_login_form](../../../packages/frontend/tests/test_required_guide_navigation.py#L545) |
| ヘッダーから用途を検索すると、その語句を指定したカタログへ移る。 | — | [test_header_search_opens_a_catalog_for_the_entered_words](../../../packages/frontend/tests/test_required_guide_navigation.py#L577) |
| 指定したUTC期間・API・環境・プロジェクト・応答コードを適用し、該当データを再読込する。 | メトリクスでは集計条件と表示指標を適用する<br>アクセスログでは条件とリクエストIDを適用し先頭ページに戻る | [test_apply_monitoring_filters](../../../packages/frontend/tests/test_required_monitoring.py#L29) |
| 開始と終了を直接選ばない場合、選択した時間数を直近のUTC期間に変換する。 | — | [test_relative_period_uses_utc](../../../packages/frontend/tests/test_required_monitoring.py#L68) |
| 集計画面の読込は組織の選択肢を取得し、期間とプロジェクトを保持してAPIの実績を表示用に渡す。 | — | [test_metrics_page_loads_organization_filter_and_period](../../../packages/frontend/tests/test_required_monitoring.py#L79) |
| URLの構成で日本語と予約文字を失わず、業務画面が指定した絞り込みを渡す。 | プロジェクト名と区間をメトリクスAPIに渡す<br>特殊文字を含む識別子を監査範囲のログAPIに渡す<br>ログ詳細に対象組織と監査範囲を渡す<br>監査の操作名とリクエストIDを保持する | [test_monitoring_api_preserves_encoded_filter_values](../../../packages/frontend/tests/test_required_monitoring.py#L136) |
| 監査ファイルの保存を開始すると指定名のリンクを開き、一時URLを解放する。 | — | [test_saved_file_uses_requested_filename_and_releases_url](../../../packages/frontend/tests/test_required_monitoring.py#L156) |
| 選択中の組織と閲覧範囲に合わせたAPIから絞り込み候補を取得する。 | 利用実績では集計の選択候補を取得する<br>本人用のアクセスログ候補を取得する<br>監査可能なアクセスログの候補を取得する | [test_available_monitoring_dimensions_follow_scope](../../../packages/frontend/tests/test_required_monitoring.py#L199) |
| ダッシュボードに役割別の件数、直近の個人履歴、UTC時間帯の実績を表示する。 | 一般利用者に利用履歴と契約数を表示する<br>提供者には管理対象のAPI件数も表示する<br>管理者のダッシュボードに管理対象件数を含める | [test_dashboard_renders_personal_history_and_role_counts](../../../packages/frontend/tests/test_required_monitoring.py#L251) |
| 業務監査の一覧に検索条件・照合用の情報と、そのページで利用可能な移動を表示する。 | 未絞り込みで記録がないときは空の結果を説明する<br>絞り込んだ1件を時刻・実行者・リクエストIDで照合できる<br>記録が続く途中のページには新旧両方向の操作を表示する | [test_audit_result_table_shows_context_and_pagination](../../../packages/frontend/tests/test_required_monitoring.py#L312) |
| 集計が未取得で本人の履歴が空の場合、件数の取得失敗と呼び出しがないことを別々に示す。 | — | [test_dashboard_retry_distinguishes_unavailable_summary_from_empty_personal_logs](../../../packages/frontend/tests/test_required_monitoring.py#L357) |
| アクセスログを表示中の期間・識別子で最後のページまで取得し、一つのJSON Linesに保存する。 | 次の開始位置がなければ一度の取得で保存する<br>各応答の開始位置で取得を継続し全ページを順番どおり保存する | [test_access_export_uses_cursor_and_preserves_current_filter](../../../packages/frontend/tests/test_required_monitoring.py#L382) |
| 個人・監査の一覧を切り替えたら以前の検索条件を解除し、閲覧可能な範囲だけを読み直す。 | 利用者の一覧は本人範囲で取得する<br>管理者の監査一覧は監査範囲で取得する<br>監査権限のない利用者には監査一覧の照会を発行しない | [test_log_navigation_requests_only_current_scope](../../../packages/frontend/tests/test_required_monitoring.py#L453) |
| 監視画面が読み込み中の再操作を重複実行せず、完了後は次の要求を受け付ける。 | — | [test_block_repeated_monitoring_action_until_first_completes](../../../packages/frontend/tests/test_required_monitoring_runtime.py#L9) |
| 集計操作が失敗すると対象操作を運用ログに渡し、画面に理由を示して入力を再開できる。 | — | [test_failed_monitoring_query_records_action_and_releases_screen](../../../packages/frontend/tests/test_required_monitoring_runtime.py#L44) |
| 対象プロジェクトの権限と有効期間上限に合った方式と発行条件を選べる。 | リーダーはシステム認証を選べ、標準値で60分・45分を表示する<br>メンバーは本人用の方式を選び、部署の20分上限が適用される | [test_credential_modes_and_validity](../../../packages/frontend/tests/test_required_people_credentials.py#L60) |
| 従来キーの発行では対象プロジェクト、共有・本人限定と承認済みのAPIを選べる。 | — | [test_legacy_key_scope_and_project](../../../packages/frontend/tests/test_required_people_credentials.py#L90) |
| アプリ認証を発行すると指定した利用者・API操作・更新時刻を発行サービスに渡す。 | — | [test_issue_app_with_selected_operation](../../../packages/frontend/tests/test_required_people_credentials.py#L102) |
| 発行済みの方式に応じて利用範囲・有効期限・呼び出し方と失効状態を確認できる。 | — | [test_key_directory_explains_each_method](../../../packages/frontend/tests/test_required_people_credentials.py#L176) |
| 対象行の更新操作は選択した認証情報を更新し、新しく発行された資格を画面に表示する。 | アプリのシークレットを更新して発行結果を確認する<br>短期Bearerを更新し新しいアクセストークンを確認する | [test_manage_issued_credential](../../../packages/frontend/tests/test_required_people_credentials.py#L227) |
| 発行先を選んで条件を取得すると、選択したプロジェクトのAPIと操作が発行画面に現れる。 | — | [test_refresh_project_conditions](../../../packages/frontend/tests/test_required_people_credentials.py#L274) |
| 個別の操作を絞らない場合でも方式・プロジェクト・指定APIとトークンの期限を保存する。 | 短期Bearerは承認済みの全APIを利用範囲にできる<br>無人実行用には特定APIの全操作を選択できる | [test_issue_whole_api_access](../../../packages/frontend/tests/test_required_people_credentials.py#L320) |
| 従来キーの発行フォームが選択した範囲で発行し、受け取ったキーを利用者に提示する。 | 共有キーは承認済みのAPI全体に発行できる<br>本人限定キーは指定したAPIだけに発行できる | [test_issue_legacy_key](../../../packages/frontend/tests/test_required_people_credentials.py#L400) |
| 認証方式と対象範囲を変更すると、その方式で指定できる利用者・API操作の欄を表示する。 | プロジェクトのアプリは対象API・操作・利用者を指定できる<br>本人用Bearerで対象を全APIとすると個別の操作選択を閉じる<br>無人実行は対象API・操作を選べるが利用者指定を表示しない | [test_change_credential_scope](../../../packages/frontend/tests/test_required_people_credentials.py#L481) |
| 認証情報の失効操作を確定した場合だけ、対象行の資格を失効させる。 | 従来APIキーを選んで失効を確定できる<br>従来キーの失効を取りやめるとキーは更新されない<br>アプリの認証情報を識別子で失効できる<br>アプリの失効を取りやめると資格は更新されない | [test_revoke_selected_key](../../../packages/frontend/tests/test_required_people_credentials.py#L564) |
| 発行条件が未選択・範囲外のときは訂正対象を表示し、発行要求を送らない。 | 有効期間がプロジェクト上限を超えたら発行を止める<br>有効期間より後の更新開始を選ぶと訂正を求める<br>個別APIを選ぶ設定で対象が空なら発行しない<br>操作指定で一つも選ばない場合は対象操作の選択を求める<br>利用者を指定するアプリに対象者がいなければ発行を止める | [test_correct_incomplete_credential_form](../../../packages/frontend/tests/test_required_people_credentials.py#L637) |
| 有効期間を短くすると更新開始を指定できる上限も同じ期間までに短くなる。 | — | [test_change_expiry_updates_refresh_bounds](../../../packages/frontend/tests/test_required_people_credentials.py#L680) |
| 共有キーの一覧で利用状態と対象APIを確認し、有効な間は呼び出し方を参照できる。 | 有効な共有キーにプロジェクト全体の呼び出し方を表示する<br>失効済みの共有キーを一覧で識別できる | [test_shared_legacy_key_status_and_usage](../../../packages/frontend/tests/test_required_people_credentials.py#L740) |
| 個別APIを選ぶ本人限定キーでAPIを指定し忘れた場合、選択を求めて発行を止める。 | — | [test_missing_target_on_specific_legacy_key](../../../packages/frontend/tests/test_required_people_credentials.py#L760) |
| シークレット更新を取りやめた場合は既存のクライアント資格の更新を要求しない。 | — | [test_cancel_application_secret_rotation](../../../packages/frontend/tests/test_required_people_credentials.py#L794) |
| 受信者は通知の件名と本文を確認し、未読の通知だけを既読にできる。 | — | [test_recipient_reads_notice](../../../packages/frontend/tests/test_required_people_governance.py#L21) |
| 通知送信フォームは送信者の役割に合う宛先と件名・本文の入力欄を表示する。 | 管理者は全体または指定した所属先を選べる<br>提供者は申請元を宛先に選べる | [test_sender_audiences](../../../packages/frontend/tests/test_required_people_governance.py#L66) |
| 利用上限の表には対象API・環境・プロジェクトと通知のみか停止つきかを表示する。 | — | [test_alert_rule_table](../../../packages/frontend/tests/test_required_people_governance.py#L77) |
| 利用上限を保存すると選択したAPI・環境・プロジェクトの件数、期間と動作を送る。 | 通知のみのルールを保存する<br>到達後は利用を止めるルールを保存する<br>指定したルールを無効にする | [test_save_alert](../../../packages/frontend/tests/test_required_people_governance.py#L120) |
| 監査担当は業務操作の対象と判断理由、記録日時、リクエストIDを同じ行で照合できる。 | — | [test_audit_row_contains_correlation](../../../packages/frontend/tests/test_required_people_governance.py#L152) |
| 管理者は登録済み利用者の名前・役割を確認し、氏名と表示名を添えて招待できる。 | — | [test_member_directory_and_invitation](../../../packages/frontend/tests/test_required_people_governance.py#L182) |
| 通知送信時に件名・本文と選んだ配信対象をその役割で指定できる形にして送信する。 | 管理者が選択した所属先に件名と本文を配信する<br>提供者は選んだAPIの申請元に案内を配信する | [test_send_notice_to_selected_audience](../../../packages/frontend/tests/test_required_people_governance.py#L224) |
| 未読の通知を既読にすると通知一覧を再取得し、次ページの取得位置を更新できる。 | — | [test_read_and_change_notice_page](../../../packages/frontend/tests/test_required_people_governance.py#L254) |
| 管理者が招待を確定すると、指定した氏名・表示名・役割で登録し名簿を再取得する。 | — | [test_invite_and_show_members](../../../packages/frontend/tests/test_required_people_governance.py#L273) |
| 管理者が確認した場合だけ、選択した対象者の在籍終了を反映する。 | 在籍終了を確定すると選択した利用者を削除する<br>削除を取りやめると利用者を残す | [test_confirm_member_removal](../../../packages/frontend/tests/test_required_people_governance.py#L327) |
| 氏名のない利用者もログイン名とメールで識別でき、利用者・提供者の役割を確認できる。 | — | [test_identify_members_without_optional_names](../../../packages/frontend/tests/test_required_people_governance.py#L344) |
| 既読通知の後続ページには前の通知に戻る操作と各通知の状態が表示される。 | — | [test_later_notification_page_offers_previous_page](../../../packages/frontend/tests/test_required_people_governance.py#L369) |
| 業務監査の次ページではリクエストIDと操作の条件を保ち、対象の記録を表示する。 | — | [test_audit_history_paginates_filtered_records](../../../packages/frontend/tests/test_required_people_governance.py#L391) |
| ログの詳細は共通のリクエストIDと主体・対象、時刻、処理時間、結果を確認できる。 | 正常な記録に開始・応答時刻とHTTP 200を示す<br>接続先が利用できなかった記録にHTTP 503と理由を示す | [test_access_log_detail](../../../packages/frontend/tests/test_required_people_logs.py#L50) |
| 詳細画面で選択中の実行について質問すると、その記録に基づく答えを読める。 | 処理時間を聞くと選んだ呼び出しのミリ秒数がわかる<br>実行者を聞くと選んだ呼び出しの主体がわかる | [test_question_about_selected_log](../../../packages/frontend/tests/test_required_people_logs.py#L89) |
| 一覧から詳細への経路はリクエストIDと個人・監査の範囲を保つ。 | 本人のアクセスログから対象リクエストの詳細へ進める<br>部署リーダーの監査範囲を保って対象リクエストの詳細へ進める | [test_detail_links_preserve_audit_scope](../../../packages/frontend/tests/test_required_people_logs.py#L113) |
| アクセスログ一覧の検索条件は閉じた状態で、結果表には記録と詳細へのリンクを表示する。 | — | [test_access_log_table_initial_disclosure](../../../packages/frontend/tests/test_required_people_logs.py#L126) |
| 詳細で応答と実行者を確認し、選んだリクエストIDを付けて問い合わせを始められる。 | — | [test_open_log_detail_and_support](../../../packages/frontend/tests/test_required_people_logs.py#L149) |
| 本人と監査担当のログは20件ずつ表示し、次ページにも同じ閲覧範囲を適用する。 | 本人の一覧を20件で区切り次ページに進める<br>監査範囲を保ったまま20件目から先の記録を取得する | [test_log_pagination_scope](../../../packages/frontend/tests/test_required_people_logs.py#L184) |
| 業務監査で指定したリクエストIDと操作を一覧取得とJSON Lines保存の両方に使用する。 | — | [test_audit_filter_and_download](../../../packages/frontend/tests/test_required_people_logs.py#L215) |
| 部署リーダーが監査履歴の行を開くと、部署と監査範囲を付けて照会し、詳細に対象リクエストを表示する。 | — | [test_department_audit_detail_scope](../../../packages/frontend/tests/test_required_people_logs.py#L259) |
| 部署とプロジェクトは使用中のデータパーツ、任意項目は公開設定付きで一覧できる。 | 管理者には属性の追加と任意項目の編集操作が表示される<br>利用者には閲覧できる項目と値の公開範囲が表示される | [test_metadata_field_directory](../../../packages/frontend/tests/test_required_people_metadata.py#L84) |
| 雇用区分から同じ項目の値だけを一覧し、対象グループの詳細を開ける。 | — | [test_attribute_navigation_and_values](../../../packages/frontend/tests/test_required_people_metadata.py#L101) |
| 属性項目の保存はキーと表示名、値名の公開範囲を組織APIに渡して一覧に戻れる。 | 新しい分類キーと名称を登録して値の名称を全員に公開する<br>既存の分類キーを保ち表示名と値名の公開範囲を変更する | [test_save_attribute_definition](../../../packages/frontend/tests/test_required_people_metadata.py#L142) |
| 本人のプロフィールは割り当てられた値・役割を表示し、別の利用者だけの値は含めない。 | — | [test_profile_lists_assigned_values_and_roles](../../../packages/frontend/tests/test_required_people_metadata.py#L170) |
| 属性値の追加では同一項目の上位値を選び、任意属性として新しいグループを登録する。 | — | [test_create_attribute_value_with_parent](../../../packages/frontend/tests/test_required_people_metadata.py#L187) |
| 任意属性の値に利用者を割り当てると、その値を対象に役割名とリーダー権限を保存する。 | — | [test_assign_role_in_attribute_group](../../../packages/frontend/tests/test_required_people_metadata.py#L213) |
| 公開された値名は一覧で読めるが、名簿が提供されていない値の利用者や役割は表示されない。 | — | [test_public_group_value_without_roster](../../../packages/frontend/tests/test_required_people_metadata.py#L235) |
| プロフィールに本人の割当てがなければ他人の属性値や役割を表示しない。 | — | [test_profile_with_no_values](../../../packages/frontend/tests/test_required_people_metadata.py#L249) |
| 対象者を選んで許可操作の保存または継承を選ぶと、該当する利用者とAPIに変更を適用する。 | 個別制限を設け、参照操作だけを保存する<br>選択をすべて外して保存すると個別許可は0件になる<br>個別設定を解除して利用申請の許可範囲を継承する | [test_person_operation_policy](../../../packages/frontend/tests/test_required_people_permissions.py#L40) |
| プロジェクトのトークン上限を開き、上位上限を確認して個別上限の設定・解除ができる。 | 上位から継承していた有効期間に19分の上限を設定する<br>個別上限を空欄に戻し上位組織の上限を継承する | [test_project_token_limit](../../../packages/frontend/tests/test_required_people_permissions.py#L99) |
| 部署の一覧を開くと部署だけを10件ずつ表示し、名称から詳細へ進める。 | 最初の10件を部署の表に表示する<br>次ページには残り2件だけ表示する | [test_department_directory_pages](../../../packages/frontend/tests/test_required_people_workspace.py#L34) |
| プロジェクトの表で所属先の名称と状態を確認し、詳細画面を選べる。 | — | [test_project_directory_has_link_and_state](../../../packages/frontend/tests/test_required_people_workspace.py#L59) |
| 直接所属する利用者についてメール、氏名、表示名と役職を同じ一覧で読める。 | — | [test_directory_member_details](../../../packages/frontend/tests/test_required_people_workspace.py#L80) |
| モニタリングで呼び出し数・エラー数とAPI別、プロジェクト別の内訳を照合できる。 | — | [test_monitor_totals_and_breakdowns](../../../packages/frontend/tests/test_required_people_workspace.py#L92) |
| 所属を編集すると選んだ利用者の役職とリーダー設定が入力済みになる。 | — | [test_membership_editor_shows_current_role](../../../packages/frontend/tests/test_required_people_workspace.py#L121) |
| 新規プロジェクトには管轄部署を設定でき、部署を未指定にもできる。 | — | [test_unit_editor_offers_parent_departments](../../../packages/frontend/tests/test_required_people_workspace.py#L136) |
| 一覧の名称リンクを開くと対象組織の所属と状態をその場で確認できる。 | 管理者が部署名を選ぶと物流本部の詳細が開く<br>所属プロジェクト名を選ぶと在庫移行の詳細が開く | [test_detail_from_directory](../../../packages/frontend/tests/test_required_people_workspace.py#L178) |
| 所属編集画面で保存すると対象者、組織、役職とリーダー権限を指定して所属を更新する。 | 新規の所属にリーダー権限と役職を付ける<br>既存メンバーの役職を変え、リーダー指定を外す | [test_save_membership_for_selected_unit](../../../packages/frontend/tests/test_required_people_workspace.py#L226) |
| プロジェクトの基本設定を保存すると表示名と管轄部署を同じプロジェクトに反映する。 | — | [test_edit_project_label_and_parent](../../../packages/frontend/tests/test_required_people_workspace.py#L259) |
| リーダーが部署の利用を停止・再開すると、その部署に新しい利用状態を適用する。 | 対象組織の利用を一時停止する<br>停止している対象組織の利用を再開する | [test_workspace_use_state](../../../packages/frontend/tests/test_required_people_workspace.py#L298) |
| 部署の移管・削除では対象を確認し、確定された操作だけを組織APIに送る。 | 対象部署と引継ぎ先を確認して移管する<br>移管の確認で取りやめれば所属を移さない<br>空の部署を選んで削除を確定できる<br>部署の削除確認で取りやめれば削除しない | [test_confirm_organization_retirement](../../../packages/frontend/tests/test_required_people_workspace.py#L344) |
| 所属詳細に表示された解除操作を確定した場合だけ、選んだ組織と利用者の関連を解除する。 | 選択した組織でだけメンバーの所属を解除する<br>所属解除を取りやめるとメンバーは組織に残る | [test_remove_membership_from_detail](../../../packages/frontend/tests/test_required_people_workspace.py#L389) |
| 管理者が所属候補を読み込むと、追加の登録ユーザーを対象組織の所属先に選べる。 | — | [test_load_more_candidates_for_membership](../../../packages/frontend/tests/test_required_people_workspace.py#L419) |
| 最後の所属を外れた利用者のプロジェクト一覧は0件となり、他組織の名前を表示しない。 | — | [test_empty_project_directory](../../../packages/frontend/tests/test_required_people_workspace.py#L449) |
| 管理画面のリンク先が対象組織の情報を読み込み、選んだ仕事に対応する画面を表示する。 | 作成画面で新しいプロジェクトの名称を入力する<br>対象プロジェクトの現在の基本設定から編集を始める<br>所属追加の画面から既存利用者を選べる<br>所属編集の画面から対象者の役職を確認する<br>モニタリング画面で選択したプロジェクトのAPI利用実績を取得する | [test_workspace_screens_load_selected_project](../../../packages/frontend/tests/test_required_people_workspace.py#L505) |
| 新規作成では利用者が指定した識別子・名称と親部署を選んだ組織種別で保存する。 | 上位部署を持つ新しい部署を作成する<br>管轄部署を持つ新しいプロジェクトを作成する | [test_create_named_organization](../../../packages/frontend/tests/test_required_people_workspace.py#L559) |
| 検索し直すと先頭ページから選択した環境と入力した語句で問い合わせ、返った商品を表示対象にする。 | — | [test_search_resets_page_and_submits_filters](../../../packages/frontend/tests/test_required_product_actions.py#L55) |
| 申請すると、選択した対象・環境・目的に加えて、同意した条件の版と回答を送信する。 | 本人を対象に利用目的と利用規約への同意を送る<br>プロジェクト全員を対象に環境別の利用条件を送る | [test_application_submits_terms_and_answers](../../../packages/frontend/tests/test_required_product_actions.py#L105) |
| 掲載を開始または停止したときは掲載状態だけを更新し、最新の商品画面を読み直す。 | 下書きを公開してカタログ掲載を受け付ける<br>掲載停止は新規受付だけを止める | [test_publication_updates_listing_acceptance](../../../packages/frontend/tests/test_required_product_actions.py#L157) |
| 商品単位で一時停止・再開を確認すると、全環境に適用する指定を送る。 | 全環境の呼び出しを一時停止する<br>一時停止中の商品の呼び出しを再開する | [test_suspension_controls_all_environments](../../../packages/frontend/tests/test_required_product_actions.py#L184) |
| 商品の削除は表示した版を指定し、終了後に提供一覧へ戻る。 | — | [test_delete_listing_sends_seen_revision](../../../packages/frontend/tests/test_required_product_actions.py#L200) |
| 提供者の審査は、対象の申請・環境・プロジェクトに理由と判断時点の版を送る。 | — | [test_review_preserves_reason_and_revision](../../../packages/frontend/tests/test_required_product_actions.py#L213) |
| 新規商品を保存すると選択環境の接続先・仕様・利用条件を登録し、指定時にその商品を公開する。 | 下書きの商品を作成し直ちには公開しない<br>保存した新規商品の識別子を指定して公開する | [test_register_with_openapi_and_environment](../../../packages/frontend/tests/test_required_product_actions.py#L242) |
| 提供者が設定した承認担当の順序、回答候補、必須か任意かを本番の利用条件として保持する。 | — | [test_provider_custom_approval_order_and_questions](../../../packages/frontend/tests/test_required_product_actions.py#L294) |
| 提供者の必須条件が満たされないときは利用申請を送信せず、修正すべき項目を案内する。 | 必須の申請項目が空なら項目名を示す<br>規約への同意がなければ同意を求める | [test_application_requires_answers_and_terms](../../../packages/frontend/tests/test_required_product_actions.py#L355) |
| 限定公開の部署・プロジェクト、委任先と自動承認条件を表示時の版とともに保存する。 | — | [test_provider_policy_targets_units_and_titles](../../../packages/frontend/tests/test_required_product_actions.py#L385) |
| URLを直接指定して送ると、接続先専用のヘッダーと本文が使われ、応答状態と本文を画面で読める。 | — | [test_manual_browser_send_displays_response](../../../packages/frontend/tests/test_required_product_actions.py#L416) |
| API Docsの初回発行は選択プロジェクトと商品のみに使う短期の個人認証情報を作る。 | — | [test_trial_issues_personal_product_key](../../../packages/frontend/tests/test_required_product_actions.py#L451) |
| 商品を開くと商品別の申請と仕様を読み、提供者にはその商品用の管理設定を読み込む。 | 利用者は商品仕様、認証情報と利用申請を取得する<br>提供者は加えて公開範囲、操作の設定と部署の選択肢を取得する | [test_listing_loads_appropriate_details](../../../packages/frontend/tests/test_required_product_actions.py#L487) |
| 既存商品の仕様をJSONファイルで変更すると、名称と説明を取り込み、識別名と表示中の版を保って更新する。 | — | [test_upload_updates_existing_listing_with_openapi_metadata](../../../packages/frontend/tests/test_required_product_actions.py#L516) |
| 新規商品にAPI識別名を入力しないと必要な項目を知らせ、商品を作成しない。 | — | [test_create_requires_product_identifier](../../../packages/frontend/tests/test_required_product_actions.py#L564) |
| 停止・削除の確認を取り消したときは状態変更を送らず、商品と利用権を維持する。 | — | [test_cancel_confirmation_leaves_publication_and_grants](../../../packages/frontend/tests/test_required_product_actions.py#L577) |
| OpenAPI原本をダウンロードすると商品名の付いたJSONファイルに登録済みの仕様全体を保存する。 | — | [test_download_preserves_original_openapi_json](../../../packages/frontend/tests/test_required_product_actions.py#L593) |
| URL直接指定の送信ボタンを連続して押しても通信は一度だけで、完了後は再び操作できる。 | — | [test_manual_click_prevents_duplicate_during_send](../../../packages/frontend/tests/test_required_product_actions.py#L617) |
| 部署・プロジェクトの公開先を指定しない商品で、選択した任意属性の値と限定公開の指定を一緒に保存する。 | 公開先がなくても限定公開の商品を全体公開に変更しない<br>社員という任意属性だけを公開先に指定できる | [test_metadata_only_audience_is_saved_as_restricted](../../../packages/frontend/tests/test_required_product_actions.py#L672) |
| ゲートウェイの呼び出し先は商品の識別名、承認環境、利用プロジェクトで決まる。 | 識別名を指定した商品は識別名で呼び出す<br>識別名のない既存商品は従来の識別子で呼び出す | [test_gateway_url_uses_product_identity](../../../packages/frontend/tests/test_required_product_client.py#L30) |
| OpenAPIのパス・クエリを別々にエンコードし、任意の未入力値を送信対象から外す。 | — | [test_openapi_location_uses_path_and_query](../../../packages/frontend/tests/test_required_product_client.py#L38) |
| OpenAPI内部参照の型、パス共通の入力、個別操作で上書きした入力を正しく解決する。 | — | [test_openapi_schema_names_and_request_parameters](../../../packages/frontend/tests/test_required_product_client.py#L52) |
| コピー用curlは入力したURL・JSON本文・ヘッダーを保持し、アクセストークンをシェル変数で参照する。 | — | [test_curl_copy_preserves_request_and_uses_shell_token](../../../packages/frontend/tests/test_required_product_client.py#L75) |
| URLの直接指定では入力したヘッダーと本文だけを使い、ポータルの資格情報を付けずに送る。 | GETで入力したヘッダーとURLを利用する<br>PATCHでは本文と接続先専用のヘッダーを送る | [test_manual_request_uses_only_destination_credentials](../../../packages/frontend/tests/test_required_product_client.py#L108) |
| 指定したメソッドやヘッダーに合わない入力では、送信前に誤りのある項目を示す。 | GETに本文を指定したら本文のエラーを示す<br>ヘッダーの値を区切れない入力では形式を案内する | [test_client_explains_invalid_input](../../../packages/frontend/tests/test_required_product_client.py#L143) |
| 配列・オブジェクトの入力をOpenAPIに指定したシリアライズ形式と展開規則でURLに組み込む。 | 展開する配列は同名のクエリ項目を繰り返す<br>縦棒区切りの配列は一つの項目にまとめる<br>空白区切りの配列は一つの項目にまとめる<br>展開しないオブジェクトはキーと値を順番に並べる<br>展開するオブジェクトはキー別のクエリにする<br>入れ子のオブジェクトは項目名とキーを角括弧で結ぶ | [test_openapi_query_serialization](../../../packages/frontend/tests/test_required_product_client.py#L211) |
| 構造を持つ必須パスパラメータをOpenAPIのsimple形式で組み込む。 | パスの配列は要素をコンマで区切る<br>展開したパスのオブジェクトはキーと値を等号で結ぶ | [test_openapi_path_structured_parameters](../../../packages/frontend/tests/test_required_product_client.py#L250) |
| 配列を受け取る操作に無効な入力があれば、送信前に項目名と必要な形式を示す。 | 配列入力にオブジェクトを指定したときは必要な型を案内する<br>配列の記述が不完全なときはJSON形式を案内する | [test_openapi_reports_invalid_structured_input](../../../packages/frontend/tests/test_required_product_client.py#L283) |
| 操作を押すと選択した環境とプロジェクトへ認証付きで送り、応答・照合ID・コピー用curlを表示する。 | 既存の認証情報を使って短期トークンで実行する<br>初回の実行で商品専用の認証情報を発行する | [test_api_docs_runs_and_copies_curl](../../../packages/frontend/tests/test_required_product_trial.py#L113) |
| 必須入力の不足や本文の形式不正は送信前に知らせ、修正して再実行できる。 | 必須のパスパラメータを空にした場合は項目名を案内する<br>必須のJSON本文が空なら送信せずに本文の入力を求める<br>JSONとして成立しない本文では送信前に形式を案内する | [test_trial_explains_unusable_input](../../../packages/frontend/tests/test_required_product_trial.py#L185) |
| 任意本文を空で送った呼び出しでもエラー本文と応答コードを示し、照合IDがなければ監査への入口を隠す。 | — | [test_trial_shows_error_response_without_request_id](../../../packages/frontend/tests/test_required_product_trial.py#L204) |
| 実行中に同じボタンをもう一度押しても、同じ在庫の更新を重複して送信しない。 | — | [test_busy_execute_button_prevents_duplicate_request](../../../packages/frontend/tests/test_required_product_trial.py#L236) |
| カタログの商品行に名称・用途・提供元・環境を示し、検索条件を初期状態で閉じる。 | — | [test_catalog_displays_matching_product](../../../packages/frontend/tests/test_required_product_views.py#L168) |
| カタログ末尾のページでは総件数と今回の表示範囲を確認できる。 | — | [test_catalog_last_page_shows_count](../../../packages/frontend/tests/test_required_product_views.py#L178) |
| 公開履歴は各版の公開日・バージョン・仕様差分・提供者の説明を同じ行にまとめる。 | — | [test_release_table_separates_versions](../../../packages/frontend/tests/test_required_product_views.py#L188) |
| 利用申請にはプロジェクト・対象・環境の選択肢、規約、環境別の必須項目と利用目的を表示する。 | — | [test_application_displays_environment_terms](../../../packages/frontend/tests/test_required_product_views.py#L213) |
| 既存商品を開くと識別名を固定し、環境ごとの接続先と承認条件を編集できる。 | — | [test_listing_form_preserves_provider_settings](../../../packages/frontend/tests/test_required_product_views.py#L230) |
| 商品登録では識別名・環境別接続先と仕様ファイルを入力し、下書きまたは公開を選べる。 | — | [test_listing_registration_accepts_slug_and_openapi](../../../packages/frontend/tests/test_required_product_views.py#L244) |
| 公開商品には名称、説明、利用申請への入口、API操作と公開履歴を表示する。 | — | [test_product_detail_links_to_application](../../../packages/frontend/tests/test_required_product_views.py#L255) |
| 承認済みの申請は商品・プロジェクト・理由と実行画面への入口を示す。 | — | [test_approved_request_links_to_client](../../../packages/frontend/tests/test_required_product_views.py#L271) |
| 承認待ちの申請では取り下げが可能で、実行画面への入口を表示しない。 | — | [test_pending_request_can_be_withdrawn](../../../packages/frontend/tests/test_required_product_views.py#L283) |
| API Docsは各操作の入力・成功応答・エラーとモデルを仕様どおり表示し、承認先で試行できる。 | — | [test_docs_match_openapi_operations](../../../packages/frontend/tests/test_required_product_views.py#L293) |
| クライアントには承認商品と操作の選択肢があり、手動URL送信用の独立した入力欄もある。 | — | [test_console_shows_approved_operations_and_manual_url](../../../packages/frontend/tests/test_required_product_views.py#L325) |
| 商品・環境・本人に対応する承認だけを抽出し、同じ申請先を重複して表示しない。 | — | [test_docs_offers_only_current_approved_environment](../../../packages/frontend/tests/test_required_product_views.py#L342) |
| 本人用の承認は同じ商品とプロジェクトで本人に使える個人認証情報だけを選択肢にする。 | — | [test_docs_credential_choices_respect_grant](../../../packages/frontend/tests/test_required_product_views.py#L364) |
| 一時停止している商品では実行ボタンを表示せず、直接URLを指定する別の操作は利用できる。 | — | [test_suspended_console_omits_execution](../../../packages/frontend/tests/test_required_product_views.py#L395) |
| 提供者に届いた承認待ち申請に、申請時の規約、回答、段階ごとの判断と承認・却下を表示する。 | — | [test_incoming_pending_request_shows_review_evidence](../../../packages/frontend/tests/test_required_product_views.py#L404) |
| 掲載停止の商品を申請画面で開くと利用申請を送信できない。 | — | [test_application_page_for_unlisted_product](../../../packages/frontend/tests/test_required_product_views.py#L440) |
| プロジェクトに所属していない利用者は、個人ワークスペースで利用申請を始められる。 | — | [test_application_personal_workspace](../../../packages/frontend/tests/test_required_product_views.py#L448) |
| 提供者が指定した環境で申請項目と承認段階を追加・削除すると、対応する一覧だけが更新される。 | 申請項目の追加と削除で回答欄の行数が変化する<br>承認段階の追加と削除で担当順の行数が変化する | [test_offer_editor_adds_and_removes_rows](../../../packages/frontend/tests/test_required_product_views.py#L496) |
| 環境を切り替えると、その環境の利用条件を表示し、前の環境に固有の条件を隠す。 | — | [test_application_environment_switches_terms](../../../packages/frontend/tests/test_required_product_views.py#L528) |
| 操作ごとの仕様は複数の本文形式、応答コード、説明と任意入力の例を表示する。 | — | [test_openapi_documents_response_media_and_input_examples](../../../packages/frontend/tests/test_required_product_views.py#L548) |
| 仕様に複数の型を許した場合、配列内の型の選択肢を入力欄の案内で確認できる。 | — | [test_openapi_displays_union_array_types](../../../packages/frontend/tests/test_required_product_views.py#L585) |
| APIクライアントでは、認証情報で許可した操作を選んだときだけ対応する実行欄を表示する。 | — | [test_console_changes_execution_by_selected_operation](../../../packages/frontend/tests/test_required_product_views.py#L598) |
| カタログに一致する商品がないときは0件と明示して次の検索を案内する。 | — | [test_empty_catalog_offers_new_search](../../../packages/frontend/tests/test_required_product_views.py#L628) |
| 提供一覧では公開済み商品と未掲載商品の状態を行ごとに区別できる。 | — | [test_provider_inventory_distinguishes_listing_status](../../../packages/frontend/tests/test_required_product_views.py#L637) |
| 提供者の詳細画面に現在の掲載状態に合った公開操作と、既存の利用権を別々に示す。 | — | [test_provider_publication_buttons_follow_status](../../../packages/frontend/tests/test_required_product_views.py#L658) |
| 許可された操作が限定された商品では、対象操作の入力と応答だけを実行できる。 | — | [test_operation_list_honors_user_scope](../../../packages/frontend/tests/test_required_product_views.py#L672) |
| 未承認でも商品仕様の操作・本文形式・応答を閲覧でき、その操作の実行には承認を求める。 | — | [test_docs_show_multi_media_and_approval_requirement](../../../packages/frontend/tests/test_required_product_views.py#L692) |
| 提供者の公開条件フォームは公開先なしと任意属性の値による限定公開を区別して表示する。 | 限定公開で公開先がない商品には属性値のチェックが付かない<br>社員に限定した商品では社員だけが登録済みの公開条件として選択される | [test_restricted_visibility_displays_selected_metadata_values](../../../packages/frontend/tests/test_required_product_views.py#L754) |
| 画面内の入力不備と不具合を区別し、商品と本人の識別子だけを残す。 | — | [test_screen_error_context](../../../packages/frontend/tests/test_screen_logs.py#L13) |
| API呼び出しには登録済み画面の識別子だけを付加する。 | — | [test_request_carries_screen](../../../packages/frontend/tests/test_screen_logs.py#L33) |
| 独立した画面ファイルを追加すると配布物に入り、URLからデータ取得と描画までできる。 | — | [test_new_screen_is_packaged_loaded_and_rendered](../../../packages/frontend/tests/test_screen_registry.py#L17) |
| 既存の固定・詳細URLを解決し、役割に応じたメニューを従来の順序で表示する。 | — | [test_existing_routes_and_role_menus](../../../packages/frontend/tests/test_screen_registry.py#L71) |
| 別の画面が登録済みのURLを使うと重複したパスを示して失敗する。 | — | [test_duplicate_screen_path_is_rejected](../../../packages/frontend/tests/test_screen_registry.py#L104) |
| 部署を10件ずつ表示し、次ページとプロジェクト一覧では該当する対象だけを開ける。 | — | [test_directory_pages_filter_before_paginating](../../../packages/frontend/tests/test_workspace_screens.py#L48) |
| 直接所属の利用者をメールアドレス・名前・担当ロールに分け、管理者にだけ操作列を表示する。 | — | [test_direct_members_have_aligned_table_columns](../../../packages/frontend/tests/test_workspace_screens.py#L66) |
| 権限と種類が一致する対象だけの利用統計を取得し、管理者専用の編集フォームを分離する。 | — | [test_scoped_monitor_and_edit_routes](../../../packages/frontend/tests/test_workspace_screens.py#L120) |
| 管理者にだけ移管・削除を表示し、移管先には同種の別組織だけを提示する。 | — | [test_unit_retirement_actions_are_admin_only](../../../packages/frontend/tests/test_workspace_screens.py#L155) |
| プロジェクト単位の集計であることを案内し、所属メンバーを4列の表で表示する。 | — | [test_project_monitor_shows_members_as_a_table](../../../packages/frontend/tests/test_workspace_screens.py#L171) |

### インフラ（11項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| 標準構成のリソース型と論理ID、スタック出力をスナップショットと照合する。 | — | [test_cloudformation_structure_matches_snapshot](../../../packages/infra/tests/test_cdk_regression.py#L28) |
| AWS Solutionsの全ルールを実行し、記録済み以外の指摘がないことを確認する。 | — | [test_cdk_nag_detects_no_new_findings](../../../packages/infra/tests/test_cdk_regression.py#L50) |
| ロジック変更で関数だけが更新され、依存変更で共有Layerだけが更新される。 | — | [test_backend_layer_changes_only_with_dependencies](../../../packages/infra/tests/test_cdk_regression.py#L66) |
| モデルコードの変更ではLayerが変わらず、判定依存の変更は生成モデルに波及しない。 | — | [test_model_layer_changes_are_isolated](../../../packages/infra/tests/test_cdk_regression.py#L105) |
| 判定・ツール選択・生成の各関数の配備が完了してからDB移行を開始する。 | — | [test_schema_waits_for_chat_models](../../../packages/infra/tests/test_cdk_regression.py#L143) |
| 常時稼働の構成を置かず、Lambdaのメモリ・タイムアウトとログ保存期間を制限する。 | — | [test_cost_drivers_are_bounded](../../../packages/infra/tests/test_cost.py#L10) |
| チャット処理と3モデルを分離し、予約枠を要求せず所定のメモリと作業領域で実行する。 | — | [test_chat_uses_separate_on_demand_python_functions](../../../packages/infra/tests/test_cost.py#L34) |
| 非公開S3、呼び出しの認可、キャッシュと配信の設定が設計どおりである | — | [test_access_boundaries](../../../packages/infra/tests/test_stack.py#L12) |
| すべてのリソースに管理情報を付け、タグ対応リソースには同じ値を付ける | サンプル付きの標準構成を検証<br>独自プロジェクト構成を検証 | [test_every_resource_has_ownership](../../../packages/infra/tests/test_stack.py#L116) |
| 既存リソースの論理IDと分割後の所属が対応する | — | [test_existing_resources_keep_their_logical_ids](../../../packages/infra/tests/test_stack.py#L151) |
| 提供先の所有者・環境・種類とARNを検査し、不正な接続設定で配備を進めない。 | — | [test_upstream_bindings_validate_target_and_secret](../../../packages/infra/tests/test_stack.py#L161) |

### データベース（6項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| 実際のテーブルと列に業務名が対応し、Alembicの内部テーブルにも説明がある。 | — | [test_every_column_is_documented_including_schema_version](../../../packages/database/tests/test_design_metadata.py#L7) |
| コメントの次の行にある最初の文字列だけを業務名に対応付ける。 | — | [test_labels_follow_the_first_literal_on_each_annotated_line](../../../packages/database/tests/test_design_metadata.py#L18) |
| Aurora DSQL では公開スキーマの現行カラム名をシステムカタログから取得する | — | [test_dsql_column_names_use_the_system_catalog](../../../packages/database/tests/test_migration_columns.py#L7) |
| DB定義がモデルと一致し、旧版のデータを移行できる | — | [test_schema_matches_models_and_replays](../../../packages/database/tests/test_migrations.py#L11) |
| DDLが完了して版番号の記録だけが失われた場合も、データを保持して再適用できる。 | — | [test_schema_upgrade_can_resume_after_all_ddl](../../../packages/database/tests/test_migrations.py#L66) |
| Aurora DSQL 接続では Amazon ルート CA を含むバンドルで証明書とホスト名を検証する。 | — | [test_dsql_uses_a_bundled_ca_for_full_tls_verification](../../../packages/database/tests/test_session.py#L9) |

### ブラウザーE2E（28項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| OpenAPIの型からパス・クエリ・JSONを入力し、選択したキーでHTTPSの送料計算を実行する | — | [test_openapi_key_console](../../../tests/e2e/browser/test_api_docs.py#L136) |
| ブラウザーで3方式を発行し、実時計で1分後に更新、シークレット変更・失効まで確認する | — | [test_credentials_console](../../../tests/e2e/browser/test_credentials_console.py#L18) |
| 提供者が公開・自動承認・委任の条件を保存し、部署リーダーが個人申請を画面から却下する | — | [test_provider_policy_console](../../../tests/e2e/browser/test_delegation_console.py#L14) |
| 6種類の権限で全メニューを開き、狭幅と広幅で余白・操作領域・横あふれを検査する。 | — | [test_role_screen_layout](../../../tests/e2e/browser/test_layout.py#L95) |
| 管理者が招待時に氏名を入力し、本人の表示名とともに兼務先に表示して監査を確認する。 | — | [test_member_profile_management](../../../tests/e2e/browser/test_member_profile_console.py#L17) |
| 雇用区分を登録して利用者に割り当てると本人のプロフィールに値が表示される。 | — | [test_metadata_assignment_console](../../../tests/e2e/browser/test_metadata_console.py#L12) |
| 提供者が利用者の操作を選び、送料1,400円のHTTPS応答と権限変更直後の転送停止を照合する | — | [test_person_operation_console](../../../tests/e2e/browser/test_operation_console.py#L16) |
| デモの提供者と利用者が公開・申請・承認・実行・権限取消を画面で完了できる | — | [test_user_flow](../../../tests/e2e/browser/test_portal.py#L27) |
| ホームで商品と手順を調べ、運営への問い合わせを明示的に送信できる。 | — | [test_home_chat_and_inquiry](../../../tests/e2e/browser/test_portal.py#L32) |
| 利用者が問い合わせ画面から送信すると受付番号が表示され、再訪しても回答待ちの履歴を確認できる。 | — | [test_submit_from_inquiries](../../../tests/e2e/browser/test_portal.py#L65) |
| 12業務・20拠点の公開240件を全件照合し、PC・スマートフォンの検索とページ送りを確認する | — | [test_large_catalog](../../../tests/e2e/browser/test_portal.py#L98) |
| 11月の外観変更を反映した明暗テーマの文字コントラストとキーボード操作を確認する | — | [test_console_visual_modes](../../../tests/e2e/browser/test_portal.py#L173) |
| 3役で利用状況、ユーザー管理、名称で選んだ宛先への通知、ログ保存、掲載終了を確認する。 | — | [test_governance_console](../../../tests/e2e/browser/test_portal.py#L278) |
| スマートフォンでログインし、確認コードを入力して元のカタログへ戻れる。 | — | [test_portal_login_on_mobile](../../../tests/e2e/browser/test_portal.py#L415) |
| 商品を公開し、利用者が商品詳細から利用申請できる | — | [test_publish_and_apply_from_product_page](../../../tests/e2e/browser/test_product_publication.py#L16) |
| 実行レポートの画像をオフラインで拡大し、キーボード・タッチ・印刷でも確認できる | — | [test_report_image_viewer](../../../tests/e2e/browser/test_report_images.py#L13) |
| 利用者が承認待ちの申請を取り下げると画面に反映され、同じ環境に再申請できる。 | — | [test_withdraw_pending](../../../tests/e2e/browser/test_requirement_flows.py#L51) |
| 利用者が商品画面で旧版と新版の版番号、追加された操作と提供者の説明を確認できる。 | — | [test_release_history](../../../tests/e2e/browser/test_requirement_flows.py#L73) |
| 部署リーダーの判断が済むまで提供者は承認できず、最終承認後に呼び出しが成功する。 | — | [test_ordered_review](../../../tests/e2e/browser/test_requirement_flows.py#L107) |
| 拒否を記録した対象APIを管理者が一時停止し、許可済みの呼び出しだけを対象別に止められる。 | — | [test_admin_stops_target_after_denial](../../../tests/e2e/browser/test_requirement_flows.py#L168) |
| 利用者が2ページ目の1件を開き、同じリクエストIDで質問と問い合わせを送れる。 | — | [test_access_log_detail_and_support](../../../tests/e2e/browser/test_requirement_flows.py#L211) |
| 部署リーダーが配下の別人の呼び出しを監査し、リーダー解除後は詳細を再表示できない。 | — | [test_lead_access_audit](../../../tests/e2e/browser/test_requirement_flows.py#L256) |
| 監査担当が他の利用者のアクセスと業務監査を同じIDで照合し、両方の記録を保存できる。 | — | [test_auditor_cross_checks_exports](../../../tests/e2e/browser/test_requirement_flows.py#L296) |
| 提供者が商品ごとのトークンの上限を短縮すると、利用者による上限超過の発行を拒否する。 | — | [test_provider_shortens_token_lifetime](../../../tests/e2e/browser/test_requirement_flows.py#L332) |
| 役割と検索語で使い方を絞り込み、手順から対象画面を開ける | — | [test_usage_guide](../../../tests/e2e/browser/test_usage_guide.py#L14) |
| 管理者が組織階層と兼務を設定し、リーダーがキー・利用状況・停止と再開を操作する | — | [test_workspace_key_console](../../../tests/e2e/browser/test_workspace_console.py#L30) |
| finance の利用者には所属先が1件だけ表示され、未所属の詳細URLを開いても情報は表示されない | — | [test_consumer_project_directory](../../../tests/e2e/browser/test_workspace_console.py#L213) |
| 管理画面で部署を移管して子部署を引き継ぎ、未使用の子部署を削除できる。 | — | [test_retire_workspace_units](../../../tests/e2e/browser/test_workspace_console.py#L238) |

### 開発ツール（102項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| 管理者がいないときだけメールで招待し、作成したユーザーの識別子を次のジョブに渡す。 | — | [test_invite_delivers_password_by_email](../../../packages/tools/tests/test_bootstrap_admin.py#L28) |
| 管理者が既にいるときは招待と権限付与の両方を省く。 | — | [test_existing_admin_skips_writes_in_both_jobs](../../../packages/tools/tests/test_bootstrap_admin.py#L54) |
| 同名ユーザーが存在して作成に失敗したときは権限付与用の出力を残さない。 | — | [test_collision_never_adopts_an_existing_account](../../../packages/tools/tests/test_bootstrap_admin.py#L63) |
| 招待と同じプールとユーザーなら初回ログイン用の管理権限を付与する。 | — | [test_grant_only_invited_user](../../../packages/tools/tests/test_bootstrap_admin.py#L74) |
| 招待後に同名の別ユーザーに置き換わったときは権限を付与しない。 | — | [test_replaced_user_cannot_be_promoted](../../../packages/tools/tests/test_bootstrap_admin.py#L96) |
| 招待後にスタックのプールが置き換わったときはユーザーを操作しない。 | — | [test_pool_replacement_stops_grant](../../../packages/tools/tests/test_bootstrap_admin.py#L107) |
| 招待先を設定していないときはアカウントを作成しない。 | — | [test_missing_recipient_stops_before_creation](../../../packages/tools/tests/test_bootstrap_admin.py#L116) |
| AWS CLI の照会結果を読み取り、グループ追加で応答が空でも成功する。 | — | [test_cli_returns_json_and_handles_empty_responses](../../../packages/tools/tests/test_bootstrap_admin.py#L125) |
| AWS CLI が失敗したときは操作名を示し、引数の招待先を例外に含めない。 | — | [test_cli_error_hides_invitation_address](../../../packages/tools/tests/test_bootstrap_admin.py#L138) |
| 説明文のみの変更は既存の全体カバレッジを引き継ぎ、実行環境の準備を省ける。 | — | [test_docs_reuse_complete_report](../../../packages/tools/tests/test_ci_scope.py#L18) |
| 単体テストの変更は該当層に絞り、複数層の変更は両方を選ぶ。 | — | [test_component_tests_and_mixed_changes](../../../packages/tools/tests/test_ci_scope.py#L26) |
| CSSは画面の検証を行い、認証クライアントの変更ではCognitoの画面操作も確認する。 | — | [test_css_and_authentication_have_different_consumers](../../../packages/tools/tests/test_ci_scope.py#L39) |
| 画面のビルド処理を変えるとCSS解析とコード解析の規則も検査する。 | — | [test_frontend_builder_runs_stylesheet_and_design_policy_tests](../../../packages/tools/tests/test_ci_scope.py#L49) |
| インフラの実装変更ではCDK・監査・AWSの画面連携に必要な環境を用意する。 | — | [test_infra_and_aws_require_browser_and_assets](../../../packages/tools/tests/test_ci_scope.py#L58) |
| 計測対象コードの変更時は以前に実行行を記録した層も再計測する。 | — | [test_measured_source_invalidates_suites_that_executed_it](../../../packages/tools/tests/test_ci_scope.py#L67) |
| 保存結果がない層は比較元での補完対象にし、PRの実行対象とは区別する。 | — | [test_missing_coverage_never_becomes_a_partial_baseline](../../../packages/tools/tests/test_ci_scope.py#L76) |
| 未知の領域・依存ロック・CI定義を変更した場合は全検証を選ぶ。 | — | [test_unknown_or_shared_input_runs_all_checks](../../../packages/tools/tests/test_ci_scope.py#L88) |
| 日本語と空白を含むパスの移動と削除を移動元も含めて判定する。 | — | [test_git_diff_includes_deleted_and_both_renamed_paths](../../../packages/tools/tests/test_ci_scope.py#L102) |
| 全領域の実行行と未実行行を区別し、未読込のモデルとインフラの入口も分母に含める。 | — | [test_coverage_includes_all_runtime_layers_and_unexecuted_files](../../../packages/tools/tests/test_ci_scope.py#L124) |
| 画面変更時はその画面を実行した別の層を再計測し、無関係な層の結果を再利用する。 | — | [test_changed_screen_invalidates_only_suites_that_executed_it](../../../packages/tools/tests/test_ci_scope.py#L165) |
| 旧形式または異なる計測条件の結果は再利用せず、同じ条件の結果だけを使う。 | — | [test_cache_requires_same_coverage_policy](../../../packages/tools/tests/test_ci_scope.py#L179) |
| 比較元でブラウザーのタイムアウトだけが起きた場合に限り再計測する。 | — | [test_baseline_retry_requires_only_browser_timeouts](../../../packages/tools/tests/test_ci_scope.py#L190) |
| エージェントとモデルの変更で単体・API結合・構造・型・配布物の検査を選ぶ。 | — | [test_agent_sources_select_agent_consumers_and_deployment_checks](../../../packages/tools/tests/test_ci_scope.py#L205) |
| 移動前と同じ範囲の総カバレッジを比較に使い、古いパスのスイート別結果は再利用しない。 | — | [test_moved_agent_reuses_only_aggregate_baseline](../../../packages/tools/tests/test_ci_scope.py#L217) |
| 間接依存の更新は利用パッケージに絞り、移動した依存は変更前と変更後の両方を検証する。 | — | [test_lock_changes_follow_transitive_old_and_new_consumers](../../../packages/tools/tests/test_ci_scope.py#L234) |
| PRテンプレートだけの差分はキャッシュがなくても準備やテストを起動せず、空の計測を公開しない。 | — | [test_template_plan_never_bootstraps_coverage](../../../packages/tools/tests/test_ci_scope.py#L263) |
| 検査の直前の説明と実行条件を対応付け、シェル文字列内の偽コメントを無視する。 | — | [test_workflow_comments_follow_steps](../../../packages/tools/tests/test_completion.py#L9) |
| ブランチの下限・低下幅を合成し、非同期テストとクラスの説明を定義行から取得する。 | — | [test_rule_changes_and_test_edits_reach_document](../../../packages/tools/tests/test_completion.py#L29) |
| 旧方式で測った成果物は比較元に階層付き画面がなく計測器の他の部分が一致するときだけ使う。 | — | [test_flat_baseline_requires_equivalent_file_selection](../../../packages/tools/tests/test_coverage_baseline.py#L7) |
| 開発ツール移動前の2種類の配置と移動後の配置で、比較元のビルダーを選ぶ。 | — | [test_baseline_resolves_its_own_frontend_builder](../../../packages/tools/tests/test_coverage_baseline.py#L62) |
| コミットフックが規約に沿った件名を許可し、規約外の件名を理由付きで拒否する。 | — | [test_commit_message_hook](../../../packages/tools/tests/test_delivery_contracts.py#L13) |
| mainへのマージを検証した後だけOIDCで配備し、PRでは検証を実行する。 | — | [test_merge_deploy_workflow](../../../packages/tools/tests/test_delivery_contracts.py#L31) |
| 変異後のアサーション失敗を検出に数え、収集エラーやスキップを検出件数から除く。 | — | [test_mutation_verdict](../../../packages/tools/tests/test_delivery_contracts.py#L60) |
| 全APIの入出力を出力し、再生成時に不要な文書を取り除く | — | [test_all_routes_inputs_outputs_and_cleanup](../../../packages/tools/tests/test_design.py#L9) |
| CRUD表の全APIを個別設計書の根拠と照合できる | — | [test_crud_matrices_cover_all_routes_and_match_per_api_evidence](../../../packages/tools/tests/test_design.py#L56) |
| ORMの操作と条件付きAWS書き込みを設計解析で追跡できる | — | [test_sqlalchemy_and_conditional_aws_writes](../../../packages/tools/tests/test_design.py#L93) |
| 相対インポートと再帰をたどり、動的SQLを識別できる | — | [test_sql_sources_relative_import_recursion_and_dynamic_sql](../../../packages/tools/tests/test_design.py#L112) |
| UTF-8の正常な文書を許可し、異常な符号化や改行を検出する | — | [test_text_policy](../../../packages/tools/tests/test_design.py#L132) |
| OpenAPIの通信上の項目名を保ち、用途に応じた和名を表示する | — | [test_openapi_preserves_wire_names_and_labels_them_in_context](../../../packages/tools/tests/test_design.py#L139) |
| 過去に保存した独自項目を返しつつ、公開する入れ子の型をフィールド宣言から取得する。 | — | [test_nested_contracts_preserve_legacy_records_and_follow_field_annotations](../../../packages/tools/tests/test_design.py#L165) |
| 結果ファイルや画面が欠けたら不合格とし、そろった場合は画像・実行日時・リソースを表示する。 | — | [test_html_report_tracks_missing_results_and_renders_artifacts](../../../packages/tools/tests/test_html_report.py#L8) |
| 各リソースを所属別に掲載し、配列・参照・埋め込みJSONを項目ごとの行に展開する。 | — | [test_component_parameter_sheet](../../../packages/tools/tests/test_infrastructure_docs.py#L9) |
| 所属が欠けたリソースは論理IDを示して生成を止める。 | — | [test_missing_component_identifies_resource](../../../packages/tools/tests/test_infrastructure_docs.py#L56) |
| 同じ依存を別の場所で同期してもLayerが一致し、依存を更新したときだけ内容が変わる。 | — | [test_layer_rebuild_is_reproducible](../../../packages/tools/tests/test_lambda_layer.py#L29) |
| 各Layerが対応する依存群をロックから取り出し、正しいPythonの版で同期する。 | — | [test_each_lambda_layer_exports_its_locked_dependencies](../../../packages/tools/tests/test_lambda_layer.py#L54) |
| PRの行カバレッジを対象ブランチの最低値と許容低下幅の両方で判定する。 | 下限と低下幅がともに境界なら合格する<br>低下がなくても最低行カバレッジ未満なら失敗する<br>下限を満たしていても低下幅を超えたら失敗する<br>低下幅の判定を無効にしたルールでは下限だけを使う<br>改善した計測は低下幅の判定に合格する | [test_branch_gate](../../../packages/tools/tests/test_required_ci_coverage.py#L76) |
| 複数のルールから厳しい下限と有効な低下幅を選び、行数から正確な割合を得る。 | — | [test_combined_branch_rules_and_exact_measurement](../../../packages/tools/tests/test_required_ci_coverage.py#L93) |
| 保存済みの合算結果を再利用し、取得できない場合だけ比較元コミットを計測する。 | — | [test_baseline_prefers_saved_aggregate_and_measures_missing](../../../packages/tools/tests/test_required_ci_coverage.py#L101) |
| GitHubのブランチルールをJSONで読み、取得したルールから下限を取り出す。 | — | [test_github_rules_are_requested_as_json](../../../packages/tools/tests/test_required_ci_coverage.py#L115) |
| マージ済みPRの計測はツリーの一致と有効な成果物を確認できた場合だけ使用する。 | 同一ツリーの検証済みPRの計測を取得する<br>マージ時に内容が変わったPRの計測を再利用しない<br>有効期限切れの計測を再利用しない | [test_baseline_download_verifies_source_and_artifact](../../../packages/tools/tests/test_required_ci_coverage.py#L151) |
| 要件コマンドが日本語の要件、定義元、共通用語を二つの索引に反映する。 | — | [test_documents_command_generates_linked_indexes](../../../packages/tools/tests/test_required_ci_documents.py#L54) |
| 共通語彙の定義が欠けている要件を索引作成時に不合格とする。 | — | [test_documents_command_rejects_malformed_requirements](../../../packages/tools/tests/test_required_ci_documents.py#L65) |
| 差分の実行予定とJUnit結果を照合し、要件ページと機械判定用XMLの両方を生成する。 | 成功した対象ケースを合格にする<br>失敗を要件ページとJUnitに記録する<br>テストエラーを不合格として記録する<br>対象テストのスキップで未完了とする<br>実行計画にない層は対象外とする | [test_requirement_evidence_command](../../../packages/tools/tests/test_required_ci_documents.py#L125) |
| 同じ単体テストが元の実装で成功し変異で失敗した場合だけ検出に数える。 | 値の変化で対象のテストが失敗すれば検出する<br>変更後も成功するテストを検出に含めない<br>元の実装で失敗するテストを検出に含めない<br>スキップを変異の検出に含めない | [test_local_mutation_compares_target_before_and_after](../../../packages/tools/tests/test_required_ci_mutation.py#L38) |
| PR用の実行計画と比較元で補完する計測を分けてGitHubの出力に記録する。 | PRテンプレートのみでは単体テストを起動しない<br>画面の単体テストの追加ではフロントのスイートだけを選択する | [test_plan_records_changed_suites_and_baseline_gaps](../../../packages/tools/tests/test_required_ci_plan.py#L83) |
| 選択した二つのスイートのJUnitと計測を残し、合算したXMLに両方の実行行を反映する。 | — | [test_selected_suites_retain_separate_measurements_and_combined_result](../../../packages/tools/tests/test_required_ci_plan.py#L102) |
| テストが失敗したスイート名を示して不合格にし、そのJUnitを保存する。 | — | [test_suite_failure_reports_which_run_failed](../../../packages/tools/tests/test_required_ci_plan.py#L118) |
| 比較元の計測は分岐点のクリーンな作業ツリーで行い、PR側の編集を保持する。 | 全体の比較元には分岐点のテストの行数を使う<br>欠けたスイートだけを比較元で補完する | [test_baseline_measurement_uses_clean_checkout](../../../packages/tools/tests/test_required_ci_plan.py#L143) |
| 変更した分野が必要とするテストと検査を差分計画に含める。 | 共有するガイド検索の変更は推論、画面、APIの検証に波及する<br>共通のガイド本文を変えたら画面と推論の両方を検証する<br>ブラウザー型スタブの変更は型検査とフロント単体を選ぶ<br>スタック全体の変更はインフラ単体と合成・監査を選ぶ<br>共通のログ形式を変えたらAPIと推論・開発ツールの利用箇所も検証する<br>フックの変更はフック検証を起動する<br>要件定義の追加は全層の受入テストを選ぶ<br>生成設計書の変更では設計生成とツール検証を選ぶ<br>サンプルAPIの変更は専用テストと配備・契約の検証を選ぶ<br>実行Layerの変更時は合成と依存監査を実行する<br>推論用配布物の変更時はエージェント単体とリソースを検査する<br>AWSの画面操作テストにはエミュレーターとブラウザーを用意する<br>画面操作テストの変更時は画面とブラウザーを用意する<br>API設計の生成変更は生成とツール単体を検証する<br>デモ商品の変更は実際の画面とAWSで確認する<br>構造規則のテストを変更するとそのスイートを起動する | [test_changed_consumer_plan_keeps_each_required_check](../../../packages/tools/tests/test_required_ci_plan.py#L306) |
| 文書だけを変更した場合、検証済みの全体計測を保存し、追加のテストを要求しない。 | — | [test_document_only_plan_copies_verified_aggregate](../../../packages/tools/tests/test_required_ci_plan.py#L316) |
| 完了条件のCI成果物は適用ルールの値を示し、検証したコミットのソースにリンクする。 | — | [test_quality_document_links_selected_commit_and_live_policy](../../../packages/tools/tests/test_required_ci_plan.py#L335) |
| 各パッケージ自身のpytest計測ファイルを読み、実測した行と分岐の達成度で判定する。 | 両方向を通る単体テストの計測で行と分岐の基準を満たす<br>一方向しか通らない単体テストの計測を不合格にする | [test_package_gate_reads_own_suite_measurement](../../../packages/tools/tests/test_required_ci_plan.py#L366) |
| 単体テストを片方だけ変更したとき、比較元の他方の計測を再利用し合算結果に含める。 | — | [test_plan_preserves_untouched_suite_cache](../../../packages/tools/tests/test_required_ci_plan.py#L389) |
| 変更したテキストの符号化と改行が規約に一致するときだけ受け付ける。 | 日本語のUTF-8とLFを許可する<br>UTF-8のBOMを拒否する<br>UTF-8として読めないバイトを拒否する<br>途中のCRLFを拒否する<br>末尾の改行がない文書を拒否する<br>末尾に改行が二つある文書を拒否する | [test_text_encoding_and_terminator](../../../packages/tools/tests/test_required_ci_text.py#L64) |
| ステージ済みの不正な日本語名の文書を特定し、修正をステージしたら画像とともに許可する。 | — | [test_staged_text_uses_index_and_ignores_binary](../../../packages/tools/tests/test_required_ci_text.py#L69) |
| PR差分は未変更の既存違反を除外し、全体検査は既存違反も検出する。 | — | [test_pull_request_range_and_full_checkout](../../../packages/tools/tests/test_required_ci_text.py#L85) |
| 配備対象ブランチでは規約どおりの文書だけをステージしていても直接コミットを拒否する。 | mainでの直接コミットを拒否する<br>masterでの直接コミットを拒否する | [test_staged_protects_release_branches](../../../packages/tools/tests/test_required_ci_text.py#L114) |
| 独自の接続先を指定すると配布物を作り、その接続設定で合成または配備する。 | 合成ではモデルを配信しない<br>配備では指定した承認条件とモデルを使用する | [test_cdk_receives_packaged_app_and_bindings](../../../packages/tools/tests/test_required_delivery_operations.py#L52) |
| ビルドだけを選ぶとSPAとAPIとモデルの配布物を準備して終了する。 | — | [test_build_prepares_all_delivery_artifacts](../../../packages/tools/tests/test_required_delivery_operations.py#L68) |
| デモではDBを最新まで移行してから指定したループバックのポートでAPIを起動する。 | — | [test_demo_uses_local_port_after_migration](../../../packages/tools/tests/test_required_delivery_operations.py#L75) |
| 二拠点に十二商品ずつ公開し、再投入時は未公開に戻った一商品だけを再公開する。 | — | [test_seed_publishes_each_edition_and_reuses_existing_inventory](../../../packages/tools/tests/test_required_delivery_operations.py#L88) |
| 監査を実行すると合成で得たCSVの各指摘を成果物から読める。 | — | [test_audit_retains_the_generated_report](../../../packages/tools/tests/test_required_delivery_operations.py#L139) |
| 専用のエミュレーターが起動中に終了したらテストを開始せずプロセスを回収する。 | — | [test_emulator_startup_failure_stops_before_pytest](../../../packages/tools/tests/test_required_delivery_operations.py#L149) |
| 同期は件数だけを確認でき、反映時は同一メールの別人を区別し照合の失敗した属性を保存しない。 | — | [test_directory_sync_previews_then_confirms_each_subject](../../../packages/tools/tests/test_required_delivery_operations.py#L165) |
| 同期CLIは指定した環境と保存モードで照合し、運用者に処理の件数を表示する。 | 省略時は反映候補の件数を表示する<br>反映の指定時は保存件数を表示する | [test_directory_command_reports_preview_or_apply](../../../packages/tools/tests/test_required_delivery_operations.py#L219) |
| ヘルスチェックに成功すると隔離環境でpytestを起動し、失敗コードを返して専用資格情報を破棄する。 | — | [test_emulator_runs_selected_tests_then_removes_credentials](../../../packages/tools/tests/test_required_delivery_operations.py#L236) |
| 見本商品の仕様を更新すると各商品に日本語の操作とスキーマが揃い、廃止した仕様は消える。 | — | [test_sample_api_documents_follow_catalog_and_remove_retired_files](../../../packages/tools/tests/test_required_delivery_operations.py#L280) |
| 契約の生成を選ぶとAPIの操作とテーブルの日本語カラム定義をJSONで取得できる。 | — | [test_contracts_command_exports_openapi_and_column_names](../../../packages/tools/tests/test_required_delivery_operations.py#L302) |
| エミュレーターが認証情報を準備しない場合は待機を打ち切り、pytestを起動せず終了する。 | — | [test_emulator_timeout_cleans_up_without_running_pytest](../../../packages/tools/tests/test_required_delivery_operations.py#L316) |
| 初回登録の各ジョブを再実行しても、既存の管理者がいればCognitoの更新を行わない。 | 既存の管理者がいると招待メールを送信しない<br>既存の管理者がいるとグループを変更しない | [test_bootstrap_workflow_can_be_retried_without_changing_admins](../../../packages/tools/tests/test_required_delivery_operations.py#L344) |
| API配布物は移行とガイドを含み、固定依存から作る四つのLayerは再ビルドしても一致する。 | — | [test_backend_build_includes_migrations_and_reproducible_layers](../../../packages/tools/tests/test_required_delivery_packaging.py#L50) |
| 生成モデルの配布物には固定版から作った実行ファイルと再配布ライセンスを同梱する。 | — | [test_model_package_pins_native_server_and_carries_its_license](../../../packages/tools/tests/test_required_delivery_packaging.py#L99) |
| 取得したコミットが固定版と異なる場合は生成サーバーを配布物に含めない。 | — | [test_model_package_rejects_unexpected_source_revision](../../../packages/tools/tests/test_required_delivery_packaging.py#L129) |
| 初回は検証した重みを配信し、同じ版が配信済みなら取得と送信を省略する。 | — | [test_model_publisher_reuses_identical_uploaded_version](../../../packages/tools/tests/test_required_delivery_packaging.py#L174) |
| ダウンロードした重みが公表済みチェックサムに一致しなければアップロードしない。 | — | [test_model_publisher_rejects_damaged_weights](../../../packages/tools/tests/test_required_delivery_packaging.py#L197) |
| 階層化された画面と補助モジュールを同じパスで配信し、画面CSSを共通CSSの後に置く。 | — | [test_screen_assets_preserve_nested_imports_and_style_order](../../../packages/tools/tests/test_required_delivery_packaging.py#L210) |
| SPAの設定・画面・ブラウザー実行環境を同じ配信元に配置し、再ビルドでは検証済み資材を使う。 | — | [test_frontend_build_serves_runtime_locally_and_reuses_verified_assets](../../../packages/tools/tests/test_required_delivery_packaging.py#L227) |
| 実行予定の単体テストにJUnit結果がなければ、要件を未実行として不合格にする。 | — | [test_unexecuted_requirement_fails](../../../packages/tools/tests/test_requirement_evidence.py#L19) |
| 同じ要件の一部の条件だけをスキップしても要件を合格にしない。 | — | [test_skipped_requirement_fails](../../../packages/tools/tests/test_requirement_evidence.py#L28) |
| ブラウザーの成功結果には対応する実画像を必要とし、画像を相対リンクから参照できる。 | — | [test_required_browser_capture](../../../packages/tools/tests/test_requirement_evidence.py#L45) |
| 差分対象外を成功から区別し、テスト未登録の要件と消えた関数を検知する。 | — | [test_scope_and_missing_definition](../../../packages/tools/tests/test_requirement_evidence.py#L76) |
| 収集エラーや破損したJUnitがあれば、取得済みの結果を残してCIを失敗させる。 | — | [test_junit_errors_survive_reporting](../../../packages/tools/tests/test_requirement_evidence.py#L95) |
| 収集した条件の一部だけが成功したJUnitでは、実行予定の要件を合格にしない。 | — | [test_missing_parameter_result_fails](../../../packages/tools/tests/test_requirement_evidence.py#L109) |
| 本文の定義を一度だけ掲載し、両方の一覧から日本語名の要件を開ける。 | — | [test_indexes_follow_sources](../../../packages/tools/tests/test_requirements.py#L24) |
| 条件または操作で未定義の用語を使うと、その用語を示して失敗する。 | — | [test_undefined_term_in_condition_or_result_fails](../../../packages/tools/tests/test_requirements.py#L46) |
| 別々の要件で同じ用語を再定義すると失敗する。 | — | [test_duplicate_definition_fails](../../../packages/tools/tests/test_requirements.py#L54) |
| 見出しと異なるファイル名と、理由が空欄の要件をそれぞれ拒否する。 | — | [test_wrong_filename_and_empty_section_fail](../../../packages/tools/tests/test_requirements.py#L62) |
| 実際のPR相当の差分で編集・改名・テンプレートを除外し、新規要件だけを受け付ける。 | — | [test_feature_requires_added_requirement](../../../packages/tools/tests/test_requirements.py#L74) |
| テーマ生成はCSSの文字列とコメントを除外し、入れ子の変数と代替値を取得する。 | — | [test_stylesheet_uses_only_variable_references](../../../packages/tools/tests/test_stylesheet.py#L5) |
| メール補完はドライランで保存せず、確認したsubだけのメールを更新し氏名を保持する。 | — | [test_sync_uses_verified_subject_and_preserves_names](../../../packages/tools/tests/test_sync_member_emails.py#L18) |
| 境界値を許容し、片方だけが基準未満なら表示上の丸めで合格にしない。 | — | [test_coverage_compares_exact_line_and_branch_counts](../../../packages/tools/tests/test_unit_coverage.py#L5) |
| 他スイートの結果で単体の未計測を補わず、未実行・分岐なし計測・下限未達を区別する。 | — | [test_gate_uses_only_the_packages_own_unit_run](../../../packages/tools/tests/test_unit_coverage.py#L16) |

### AWSエミュレーターE2E（15項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| AWS EmulatorのCognito利用者とシステムのトークンを発行し、HTTPS到達・拒否・秘密更新を確認する | — | [test_client_tokens_reach_https](../../../tests/e2e/aws/test_credential_tokens.py#L40) |
| 合成したテンプレートから移行 Lambda を構築し、関数 ZIP と依存 Layer を登録できる | — | [test_deploy_migration_lambda](../../../tests/e2e/aws/test_migration_deployment.py#L28) |
| 配布する関数 ZIP と依存 Layer の組み合わせで移行処理が DSQL 方言で全リビジョンを適用し、再実行できる | — | [test_run_packaged_migration_on_postgresql](../../../tests/e2e/aws/test_migration_deployment.py#L79) |
| 配備用コードとLayerだけでモデルを読み込み、外部パッケージの読み込み元を確認する。 | 判定用の依存からネイティブ推論ライブラリを読み込む<br>生成用の依存からモデル取得用SDKを読み込む | [test_model_imports_from_deployment_packages](../../../tests/e2e/aws/test_model_packages.py#L29) |
| 配備用コードとLayerだけでワーカーを読み込み、同梱ガイドを使って回答を生成できる。 | — | [test_agent_imports_from_worker_deployment_package](../../../tests/e2e/aws/test_model_packages.py#L60) |
| Cognitoで識別した2人が画面で承認し、在庫照会・取消・監査まで進める | — | [test_cognito_browser](../../../tests/e2e/aws/test_portal.py#L147) |
| 承認した呼び出しを接続先へ転送し、権限取消後は遮断する | 検証環境の在庫を照会する<br>本番環境の在庫を照会する<br>利用者がLambdaへ接続する<br>システムがLambdaへ接続する<br>利用者がHTTPS先へ接続する | [test_approved_calls_reach_upstream](../../../tests/e2e/aws/test_portal.py#L195) |
| 6種類を個別に登録・公開・承認して実行し、HTTPSの受信・業務応答・監査記録を照合する | — | [test_marketplace_contracts](../../../tests/e2e/aws/test_portal.py#L347) |
| 承認済みのHTTPS接続先が停止したとき、502と監査・アクセスログを同じIDで追跡できる | — | [test_upstream_unavailable](../../../tests/e2e/aws/test_portal.py#L416) |
| AWS Emulatorで氏名付き招待と本人編集を行い、Cognitoの識別子とトークンが継続して使える。 | — | [test_cognito_member_lifecycle](../../../tests/e2e/aws/test_portal.py#L470) |
| 構築したS3・API Gateway・Lambdaのタグを取得し、在庫APIが商品を返す | — | [test_deployed_resources](../../../tests/e2e/aws/test_resources.py#L13) |
| DSQLクラスターが削除保護付きで稼働状態になる | — | [test_create_dsql_cluster](../../../tests/e2e/aws/test_resources.py#L73) |
| 公開時にOpenAPI仕様の世代をS3に個別保存する | — | [test_openapi_archive_versions](../../../tests/e2e/aws/test_resources.py#L86) |
| 登録済みのLambda配布ZIPをCPythonで実行し、全商品のヘルスチェックと業務応答を検証する。 | — | [test_packaged_sample_products](../../../tests/e2e/aws/test_resources.py#L102) |
| EmulatorのCognitoと共有・本人キーでHTTPS接続先を呼び、別人・範囲外・失効を拒否する | — | [test_scoped_keys_reach_https](../../../tests/e2e/aws/test_scoped_keys.py#L61) |
