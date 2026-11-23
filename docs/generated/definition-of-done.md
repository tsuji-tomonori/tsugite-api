# 開発完了の定義

`main` 向けのPRは、差分に応じて選ばれた検査に合格することが完了条件です。各テストのリンクから、条件と期待結果を実装で確認できます。

## 全体の行カバレッジ

単体・結合テストとブラウザーE2Eの計測を合算します。分野別の数値は内訳です。合否には対象ブランチの有効なGitHubルールを使います。

| 判定項目 | 基準・対象 |
| --- | --- |
| 全体の最低行カバレッジ | 84%以上 |
| 比較元からの低下幅 | 1ポイント以内 |
| 計測対象 | `packages/backend/src/app`、`packages/database/src/tsugite_db`、`packages/frontend/src/web_app`、`packages/infra`、`packages/agent/src/agent` |
| 計測から除くパターン | `*/tests/*`、`*/cdk.out/*`、`*/__pycache__/*` |

## 分野別の変更と必要な検査

実在するファイルを1つ変更した場合の例です。複数のファイルを変更すると対象が広がります。過去の計測で変更行を通ったスイートも再実行の対象になります。

| 分野 | 変更ファイルの例 | 合格が必要なテスト | 追加の検査・生成 |
| --- | --- | --- | --- |
| エージェント・推論モデル | `packages/agent/src/agent/jobs.py` | エージェント・推論モデル、アーキテクチャ、バックエンド、インフラ、ブラウザーE2E | Ruff（書式・静的解析）、型検査、依存関係・CDK監査、CDK合成・インフラ文書生成、AWSエミュレーターE2E |
| バックエンド | `packages/backend/src/app/apis/catalog/apply/router.py` | エージェント・推論モデル、アーキテクチャ、バックエンド、ブラウザーE2E、開発ツール | Ruff（書式・静的解析）、型検査、API設計書・契約の生成、CDK合成・インフラ文書生成、AWSエミュレーターE2E |
| フロントエンド | `packages/frontend/src/web_app/activity_filters.py` | アーキテクチャ、フロントエンド、ブラウザーE2E | Ruff（書式・静的解析） |
| インフラ | `packages/infra/src/infra_app/bindings.py` | アーキテクチャ、インフラ | Ruff（書式・静的解析）、依存関係・CDK監査、CDK合成・インフラ文書生成、AWSエミュレーターE2E |
| データベース | `packages/database/src/tsugite_db/design_names.py` | エージェント・推論モデル、アーキテクチャ、バックエンド、データベース、ブラウザーE2E、開発ツール | Ruff（書式・静的解析）、型検査、API設計書・契約の生成、CDK合成・インフラ文書生成、AWSエミュレーターE2E |

## CIの検査項目と実行条件

条件欄の `steps.scope.outputs` は、PRの差分からCIが決めた実行計画です。各行のリンクは判定を実行するステップを指します。

| 検査 | 確認内容 | 実行条件 |
| --- | --- | --- |
| [完了の定義を生成](../../.github/workflows/check.yml#L27) | 分野別のテスト定義と有効なカバレッジ基準から完了の定義を生成できる。 | すべてのPR |
| [要件別の受入テスト定義を検査](../../.github/workflows/check.yml#L39) | 各要件に実在する受入テストと証跡の取得方法が定義されている。 | すべてのPR |
| [要件一覧と用語一覧を生成し、feat ブランチの新規要件を検査](../../.github/workflows/check.yml#L42) | 要件文・必須の節・共通語彙を検査する。feat ブランチには新しい要件が1件以上ある。 | すべてのPR |
| [Markdown文書の表題を検証](../../.github/workflows/check.yml#L78) | 文書の最初のレベル1見出しに日本語がある。 | `steps.scope.outputs.documents == 'true'` |
| [変更ファイルの文字コードと改行を検査](../../.github/workflows/check.yml#L82) | 変更したテキストはUTF-8（BOMなし）・LFで、末尾の改行が1つある。 | `steps.scope.outputs.full != 'true'` |
| [task lint](../../.github/workflows/check.yml#L98) | 全体のRuff書式検査・静的解析と、Git管理対象のテキスト検査が通る。 | `steps.scope.outputs.full == 'true'` |
| [変更したPythonファイルの書式と静的検査](../../.github/workflows/check.yml#L101) | 追加・変更したPythonファイルにRuffの書式違反やルール違反がない。 | `steps.scope.outputs.lint == 'true' && steps.scope.outputs.full != 'true'` |
| [task types](../../.github/workflows/check.yml#L110) | 設定対象のPyrightとmypyの型検査がともに通る。 | `steps.scope.outputs.types == 'true'` |
| [task test:hooks](../../.github/workflows/check.yml#L113) | Gitフックが機密情報を含むコミットや保護対象ブランチへの不正なプッシュを拒否する。 | `steps.scope.outputs.hooks == 'true'` |
| [task synth](../../.github/workflows/check.yml#L122) | 配布物をビルドし、CDKからCloudFormationテンプレートを合成できる。 | `steps.scope.outputs.synth == 'true'` |
| [同じロックから再ビルドしたLambda LayerのSHA-256を照合](../../.github/workflows/check.yml#L125) | 依存ロックまたはビルダーの変更時は、再生成した3つのLambda LayerのSHA-256が一致する。 | `steps.scope.outputs.synth == 'true'` |
| [uv run --locked --all-packages python tools/packaging/build_frontend.py](../../.github/workflows/check.yml#L136) | フロントエンドの配布物を生成できる。 | `steps.scope.outputs.frontend_build == 'true'` |
| [task docs:infra:render](../../.github/workflows/check.yml#L139) | 合成済みテンプレートからリソース一覧とパラメーターシートを生成できる。 | `steps.scope.outputs.synth == 'true'` |
| [task contracts docs:api](../../.github/workflows/check.yml#L142) | OpenAPI・テーブル定義・API設計書を生成できる。 | `steps.scope.outputs.design == 'true'` |
| [task audit](../../.github/workflows/check.yml#L145) | CDKの監査結果を出力し、Lambda実行時依存に対するpip-auditが通る。 | `steps.scope.outputs.audit == 'true'` |
| [対象テストを実行し、全体カバレッジを集計](../../.github/workflows/check.yml#L148) | 差分に応じて選ばれたテストが成功し、比較元の計測結果と合わせて全体を集計できる。 | `steps.scope.outputs.suites != '[]'` |
| [task test:aws](../../.github/workflows/check.yml#L153) | AWSエミュレーターで対象のE2Eが成功する。 | `${{ !cancelled() && (success() \|\| steps.suites.outcome == 'failure') && steps.scope.outputs.aws == 'true' && steps.scope.outputs.aws_portal_only != 'true' }}` |
| [task test:aws -- -k test_cognito_browser](../../.github/workflows/check.yml#L156) | ポータルに限定した検証ではCognitoを使うブラウザーテストが成功する。 | `${{ !cancelled() && (success() \|\| steps.suites.outcome == 'failure') && steps.scope.outputs.aws_portal_only == 'true' }}` |
| [行カバレッジをブランチルールと照合](../../.github/workflows/check.yml#L159) | 全体の行カバレッジが、対象ブランチの下限と許容低下幅を満たす。 | `steps.scope.outputs.coverage == 'true'` |
| [今回のJUnit・画面証跡から要件別の合否を判定](../../.github/workflows/check.yml#L184) | 今回の実行対象となった要件について、JUnit結果と指定された証跡から合否を判定できる。 | `${{ !cancelled() }}` |
| [Build screenshot report](../../.github/workflows/check.yml#L200) | JUnit結果とスクリーンショットからレポートを生成できる。 | `${{ !cancelled() && steps.scope.outputs.report == 'true' && hashFiles('artifacts/junit.xml') != '' }}` |

### 静的解析の設定

| ツール | ルール・対象 |
| --- | --- |
| Ruff | `E4`、`E7`、`E9`、`F`、`I`、`F631`、`PT011`、`PT012` |
| Pyright | `packages/agent`、`packages/backend/src/app`、`packages/database/src/tsugite_db` |
| Pyright（strict） | `packages/database/src/tsugite_db/models.py`、`packages/backend/src/app/apis/schemas.py` |
| mypy（strict=True） | `packages/database/src/tsugite_db/models.py`、`packages/backend/src/app/apis/schemas.py` |

## テストが確認する条件と期待結果

分野ごとにテスト関数を1行ずつ掲載します。条件別の確認内容はテストに付けた日本語の説明から取得します。

### エージェント・推論モデル（14項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| 同じ受付番号の再送はワーカーを増やさず、本人が有効期間内に結果を取得できる。 | — | [test_worker_dispatch_and_result_lifecycle](../../packages/agent/tests/test_agent_jobs.py#L9) |
| モデルの辞書応答を返し、設定漏れ・関数エラー・壊れた応答では空の候補で処理を続ける。 | — | [test_worker_model_result_and_unavailable_model](../../packages/agent/tests/test_agent_jobs.py#L49) |
| 期限ちょうどのジョブは失敗として返し、遅れて届いたワーカーが上書きしない。 | — | [test_expired_job_returns_error_without_invoking_models](../../packages/agent/tests/test_agent_jobs.py#L70) |
| 語句が一致しない質問も日本語埋め込みで公開商品に結び付ける。 | — | [test_model_resolves_paraphrase_with_hybrid_retrieval](../../packages/agent/tests/test_agent_retrieval.py#L9) |
| 生成モデルに架空の案内文や無効な出典を渡されても、実在するガイドに戻す。 | — | [test_manual_answer_rejects_generated_text_outside_evidence](../../packages/agent/tests/test_agent_retrieval.py#L38) |
| 対象外と判定した質問はおすすめという語を含んでも検索・生成を呼ばない。 | — | [test_strong_outside_decision_prevents_tools_and_generation](../../packages/agent/tests/test_agent_retrieval.py#L53) |
| 指示の上書きを拒否し、質問の語が含まれない生成クエリは元の質問に戻す。 | — | [test_agent_blocks_prompt_instructions_and_keeps_query_grounded](../../packages/agent/tests/test_agent_retrieval.py#L69) |
| 生成クエリだけに一致する商品は意味検索の候補から外す。 | — | [test_rewritten_similarity_needs_support_from_original_question](../../packages/agent/tests/test_agent_retrieval.py#L80) |
| 重複する入力の埋め込みを再利用し、空のバッチは推論前に拒否する。 | — | [test_embedding_reuses_vectors_and_validates_batch](../../packages/agent/tests/test_model_workers.py#L29) |
| 検索モデルへの選択肢を許可された操作に限定し、候補が空ならモデルを呼び出さない。 | — | [test_completion_limits_tool_choices](../../packages/agent/tests/test_model_workers.py#L50) |
| モデルのハッシュが異なる場合は一時ファイルを破棄し、正しいモデルを取得した後は再利用する。 | — | [test_model_download_verifies_digest_before_reuse](../../packages/agent/tests/test_model_workers.py#L63) |
| 起動済みの生成モデルを再利用し、提示した資料の範囲と決定的な生成条件を渡す。 | — | [test_generation_returns_grounded_result_from_warm_process](../../packages/agent/tests/test_model_workers.py#L82) |
| 応答しない生成プロセスを停止し、同じモデルをCPUで再起動して準備完了を待つ。 | — | [test_model_process_recovers_from_failed_health_check](../../packages/agent/tests/test_model_workers.py#L105) |
| 埋め込みモデルと長さ制限付きトークナイザーを初回だけ読み込む。 | — | [test_embedding_load_reuses_cpu_model_and_tokenizer](../../packages/agent/tests/test_model_workers.py#L125) |

### アーキテクチャ（35項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| DB層はHTTPのルーターに依存しない | — | [test_persistence_has_no_http_dependencies](../../tests/architecture/test_boundaries.py#L4) |
| 公開操作のOpenAPI IDと実装が対応する | — | [test_published_operations_have_stable_ids](../../tests/architecture/test_boundaries.py#L14) |
| 全層の単体テスト・アーキテクチャテスト・E2Eに簡潔な日本語の説明がある。 | — | [test_test_cases_have_japanese_descriptions](../../tests/architecture/test_case_descriptions.py#L18) |
| 各パッケージの依存宣言から逆依存をたどり、変更元と利用側の単体テストを選ぶ。 | — | [test_workspace_dependency_changes_verify_consumers](../../tests/architecture/test_ci_scope.py#L15) |
| 実装が他の配布単位から読み込むモジュールを解析し、変更時に利用側のテストが選ばれる。 | — | [test_imported_modules_verify_their_actual_consumers](../../tests/architecture/test_ci_scope.py#L43) |
| PR説明・CSS・各層のテスト変更で、キャッシュがなくても無関係な層やCDKを起動しない。 | — | [test_verify_skips_unrelated_packages_even_without_coverage](../../tests/architecture/test_ci_scope.py#L66) |
| AWSエミュレーターは合成済みテンプレートを使い、モデル定義の変更はCDKの単体テストでも検証する。 | — | [test_emulator_and_model_manifest_verify_deployment_inputs](../../tests/architecture/test_ci_scope.py#L82) |
| Verifyが差分判定の出力を使い、対象外のCDK合成・AWS・ブラウザー・単体テストを起動しない。 | — | [test_workflow_runs_expensive_steps_only_for_selected_outputs](../../tests/architecture/test_ci_scope.py#L95) |
| 全実装のインポートを調べ、配布単位を越える未許可の依存を検出する。 | — | [test_runtime_dependencies_respect_layer_boundaries](../../tests/architecture/test_dependencies.py#L6) |
| 設計解析とその補助モジュールで外部辞書の読み込みと正規表現を検出する。 | — | [test_design_analysis_uses_only_python_sources_and_syntax_trees](../../tests/architecture/test_design_sources.py#L97) |
| コードやスタイルシートを読む開発ツールで正規表現による解析を検出する。 | — | [test_project_tools_do_not_parse_source_files_with_regex](../../tests/architecture/test_design_sources.py#L102) |
| 廃止した用語集の復活と設計書生成パッケージへの外部辞書の追加を検出する。 | — | [test_design_source_directories_contain_no_sidecar_data](../../tests/architecture/test_design_sources.py#L121) |
| 別名や相対インポートを経由した正規表現と外部辞書も呼び出し元から検出する。 | — | [test_analysis_policy_follows_renamed_helpers_and_relative_imports](../../tests/architecture/test_design_sources.py#L133) |
| 同名項目の和名を各モデルから取得し、文字列中の偽コメントや通常の注釈を無視する。 | — | [test_schema_field_uses_only_the_comment_on_its_declaration](../../tests/architecture/test_design_sources.py#L148) |
| 拡張子を変更した外部辞書をコメントの入力として読み込めない。 | — | [test_non_python_source_cannot_supply_business_names](../../tests/architecture/test_design_sources.py#L160) |
| 全API項目とDBカラムに業務用の和名がある | — | [test_business_names_cover_every_operation_field_and_database_column](../../tests/architecture/test_design_sources.py#L171) |
| 定義元のコメントだけを変更するとOpenAPI、API詳細、DB定義書、AWS操作表に反映される。 | — | [test_editing_declaration_comments_changes_openapi_and_design_pages](../../tests/architecture/test_design_sources.py#L208) |
| 要件・設計書・生成文書・各層の説明書は、日本語を含む表題で目的を示す。 | — | [test_markdown_documents_have_japanese_titles](../../tests/architecture/test_documents.py#L25) |
| 全要件のファイル名・要件文・四つの節・共通語彙を索引生成と同じ規則で検査する。 | — | [test_requirements_follow_the_project_vocabulary](../../tests/architecture/test_documents.py#L38) |
| 全画面で機能ごとの定義を検査し、共通コードへの画面登録と個別画面間の直接依存を検出する。 | — | [test_portal_screens_keep_their_feature_boundaries](../../tests/architecture/test_frontend_screens.py#L7) |
| 一つの機能が補助モジュールを共有し、通常URLと詳細URLを持つ構成を許可する。 | — | [test_feature_can_share_helpers_and_serve_related_routes](../../tests/architecture/test_frontend_screens.py#L17) |
| 画面定義の欠落、空の宣言、別モジュールからの丸ごと転送を検出する。 | — | [test_feature_requires_local_screen_declaration](../../tests/architecture/test_frontend_screens.py#L29) |
| 共通コードに移した画面一覧と、別名で取り込んだ個別画面の両方を検出する。 | — | [test_shared_code_cannot_own_or_import_an_individual_screen](../../tests/architecture/test_frontend_screens.py#L36) |
| 画面間の相対インポートと共通レイアウトへの逆向き依存を行番号付きで検出する。 | — | [test_feature_cannot_depend_on_another_screen_or_the_shell](../../tests/architecture/test_frontend_screens.py#L45) |
| 共通レイアウトへのURL別の条件分岐を検出し、通知やガイドへのリンクを許可する。 | — | [test_shared_layout_delegates_route_dispatch](../../tests/architecture/test_frontend_screens.py#L55) |
| 遷移時の状態破棄を許可し、共通ナビゲーションに戻した画面別API取得を検出する。 | — | [test_page_loading_stays_in_the_feature](../../tests/architecture/test_frontend_screens.py#L68) |
| 各層の違反をインポートの別名・相対参照・完全修飾名でも行番号付きで報告する。 | — | [test_boundary_checker_rejects_cross_layer_imports](../../tests/architecture/test_rule_checks.py#L14) |
| APIのジョブ受付、エージェントのガイド共有、モデル内の参照を許可する。 | — | [test_boundary_checker_accepts_supported_collaboration](../../tests/architecture/test_rule_checks.py#L39) |
| 所属する層を定義していない新規パッケージを検査対象から漏らさない。 | — | [test_new_package_requires_layer_rules](../../tests/architecture/test_rule_checks.py#L52) |
| コード例の日本語を表題に数えず、例の後に続く日本語の表題を採用する。 | — | [test_document_checker_uses_title_outside_code_examples](../../tests/architecture/test_rule_checks.py#L58) |
| 新しい配下の文書と生成設計書を自動で検査し、ビルドの一時コピーを除外する。 | — | [test_project_discovery_includes_new_components](../../tests/architecture/test_rule_checks.py#L65) |
| 取得元が可変または重みのハッシュが不正なモデルについて両方の原因を報告する。 | — | [test_model_checker_rejects_unpinned_weight](../../tests/architecture/test_rule_checks.py#L79) |
| クラス内の非同期テストも説明の検査対象に含め、補助関数を除く。 | — | [test_case_discovery_includes_async_class_methods](../../tests/architecture/test_rule_checks.py#L87) |
| 正常な説明を受け付け、英語だけの説明・複数行・短すぎる説明を検出する。 | — | [test_case_explanation_requires_one_japanese_sentence](../../tests/architecture/test_rule_checks.py#L96) |
| 三つの役割がそろった配布物は通過し、一つでも定義が欠けると失敗する。 | — | [test_model_distribution_requires_all_three_roles](../../tests/architecture/test_rule_checks.py#L103) |

### バックエンド（43項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| 条件を満たさないアクセストークンを401で拒否する | 発行元が設定値と異なる<br>IDトークンを送った場合<br>未登録クライアントから送信<br>有効期限を過ぎている<br>システム用トークンに呼び出しスコープがない | [test_invalid_token](../../packages/backend/tests/test_auth.py#L70) |
| 人とシステムを識別し、システムのポータル利用を拒否する | — | [test_people_and_machines](../../packages/backend/tests/test_auth.py#L77) |
| 承認した環境だけで呼び出せ、取消後の拒否を監査できる | — | [test_lifecycle](../../packages/backend/tests/test_catalog.py#L10) |
| 却下後に再申請でき、古い判断の再適用を拒否する | — | [test_reapply](../../packages/backend/tests/test_catalog.py#L88) |
| 外部参照、環境違いの接続先、不正な仕様の登録を拒否する | — | [test_registration_validation](../../packages/backend/tests/test_catalog.py#L123) |
| OpenAPIの固定パスを優先し、許可された操作だけを通す | — | [test_route_contract](../../packages/backend/tests/test_catalog.py#L140) |
| Lambdaではデモ用ログインを無効にする | — | [test_demo_disabled_on_lambda](../../packages/backend/tests/test_catalog.py#L149) |
| 未申請・取下げ後の権限を拒否し、他プロジェクトに監査記録を開示しない | — | [test_withdrawal_and_audit_visibility](../../packages/backend/tests/test_catalog.py#L162) |
| チャットが公開中の商品だけを勧め、別の利用者や取り下げ後の閲覧を拒む。 | — | [test_chat_only_returns_currently_visible_products](../../packages/backend/tests/test_chat_api.py#L15) |
| 操作の質問に実際の手順を返し、使い方ガイドを参照できる。 | — | [test_chat_cites_authored_guide_steps](../../packages/backend/tests/test_chat_api.py#L31) |
| ワーカーの手順番号が文字列でも、閲覧できるガイドの最初の手順を案内する。 | — | [test_invalid_worker_step_returns_first_visible_guide_step](../../packages/backend/tests/test_chat_api.py#L40) |
| 問い合わせの案内だけでは未送信で、送信後の回答は本人と管理者にだけ表示する。 | — | [test_inquiry_requires_explicit_submission_and_private_reply](../../packages/backend/tests/test_chat_api.py#L55) |
| APIが受け付けた質問をワーカーがDBで検索し、本人の受付番号で公開商品を取得できる。 | — | [test_async_chat_resolves_public_product_through_worker](../../packages/backend/tests/test_chat_api.py#L78) |
| 提供者・部署・プロジェクトの上限、更新と失効の秒境界、発行後の上限短縮を確認する | — | [test_nested_token_lifetime](../../packages/backend/tests/test_credential_lifecycle.py#L12) |
| 60日後もシステム資格で再発行でき、古いアクセストークン・従来キーは失効する | — | [test_persistent_system_and_legacy_expiry](../../packages/backend/tests/test_credential_lifecycle.py#L84) |
| 権限を毎回照合し、取消後は同じトークンでも拒否する | — | [test_gateway_authorizer_rechecks_each_invocation](../../packages/backend/tests/test_gateway_event.py#L6) |
| スタック削除イベントでDBを削除しない | — | [test_stack_deletion_preserves_database](../../packages/backend/tests/test_gateway_event.py#L61) |
| API Gateway用の認可関数で、本人キー・別ユーザー・失効の判定を確認する | — | [test_gateway_scoped_key_authorizer](../../packages/backend/tests/test_gateway_event.py#L68) |
| 管理者が追加・削除し、同一メールで再登録しても旧利用権を復活させない | — | [test_member_lifecycle](../../packages/backend/tests/test_governance.py#L10) |
| 掲載内容の修正と仕様の変更を区別し、競合を検知し、削除後も監査を保持する | — | [test_listing_revisions](../../packages/backend/tests/test_governance.py#L34) |
| 管理者・提供者の通知先を制御し、同じプロジェクトでも既読状態を利用者ごとに保持する | — | [test_notification_scope](../../packages/backend/tests/test_governance.py#L75) |
| 同時実行の上限、通知のみ・停止・解除、次期間の回復、メトリクス集計とログの閲覧範囲を確認する | — | [test_alert_window_and_access_logs](../../packages/backend/tests/test_governance.py#L103) |
| 同じ時刻の251件を複数ページに分けて全件取得し、重複・欠落と時差を確認する | — | [test_log_download_pages](../../packages/backend/tests/test_governance.py#L165) |
| 管理者が同時刻の501件をカーソル非対応のDBで集計しても、失敗や二重計上が起きない。 | — | [test_admin_metrics_across_pages](../../packages/backend/tests/test_governance.py#L210) |
| 接続確認の後、呼び出し情報をLambdaへ渡して応答を返す | — | [test_lambda_adapter](../../packages/backend/tests/test_integrations.py#L11) |
| クエリと認証情報を保持してHTTPSの接続先に転送する | — | [test_https_adapter](../../packages/backend/tests/test_integrations.py#L38) |
| 接続確認に失敗したAPIは下書きのまま残る | — | [test_failed_probe_keeps_draft](../../packages/backend/tests/test_integrations.py#L71) |
| 移行時は public のスキーマ権限を変更せず、実行ロールに対象テーブルの権限を付与する | 既存の実行ロールだけを設定する<br>チャット用の読取ロールも設定する | [test_grants_public_tables_without_altering_the_schema](../../packages/backend/tests/test_migrate.py#L16) |
| 内部参照の連鎖とJSON Pointerのエスケープを解決し、パス順を保つ。 | — | [test_resolves_path_item_references_in_order](../../packages/backend/tests/test_openapi.py#L5) |
| 解決できないパスと拡張項目を飛ばし、有効なパスを返す。 | 自分自身を参照している<br>参照先が存在しない<br>外部ドキュメントを参照している<br>パス項目が配列になっている | [test_skips_invalid_path_item_without_losing_valid_paths](../../packages/backend/tests/test_openapi.py#L33) |
| 公開範囲、委任判断、個人・プロジェクト別申請、部署・役職の自動承認を確認する | — | [test_delegation_search_and_personal_isolation](../../packages/backend/tests/test_org_access.py#L39) |
| Cognitoグループの除外が有効で、ポータルで新設したプロジェクトへの招待も反映される | — | [test_invitation_respects_identity_source](../../packages/backend/tests/test_org_access.py#L151) |
| 環境別の承認条件を守り、複数の承認を指定の順序で行う | — | [test_three_environments_and_ordered_reviews](../../packages/backend/tests/test_product_offers.py#L7) |
| 公開仕様の履歴を保持し、保管に失敗した公開を確定しない | — | [test_publication_history_and_archive_failures](../../packages/backend/tests/test_product_offers.py#L83) |
| 同じ内部参照を使う複数のOpenAPIパスで操作を解決できる | — | [test_internal_path_item_reference_is_invokable](../../packages/backend/tests/test_product_offers.py#L139) |
| HTTPの結果と原因から重要度を決め、対象APIと画面を安全に記録する。 | 正常に応答した呼び出しを記録する<br>権限不足の呼び出しを利用者起因に分類する<br>未処理例外をサーバー障害に分類する<br>保存仕様が壊れたときにデータ修正の手順を残す<br>入力値の型が違うときに利用者起因に分類する | [test_http_log](../../packages/backend/tests/test_request_logs.py#L69) |
| 入口で拒否しても追跡IDを返し、未検証の利用者や画面を記録しない。 | — | [test_origin_denial](../../packages/backend/tests/test_request_logs.py#L96) |
| 履歴の出力時にも記録時点の復旧手順を保ち、旧形式の行も読み出せる。 | — | [test_export_preserves_repair](../../packages/backend/tests/test_request_logs.py#L109) |
| ポータル停止後のCognito障害では、操作した管理者と対象利用者を分けて復旧方法を記録する。 | — | [test_member_partial_deletion](../../packages/backend/tests/test_request_logs.py#L127) |
| モデル呼び出しの失敗を元のAPI・画面・利用者に結び付け、質問本文を記録しない。 | — | [test_model_worker_error_has_request_context](../../packages/backend/tests/test_request_logs.py#L182) |
| モデルにも同じJSON形式を同梱し、重み不一致時は復元作業を記録する。 | — | [test_packaged_model_reports_weight_repair](../../packages/backend/tests/test_request_logs.py#L208) |
| 語句・意味の両方で業務APIを検索し、同義語を含めて順位付けする | — | [test_hybrid_retrieval](../../packages/backend/tests/test_search_rank.py#L17) |
| 閲覧可能なOpenAPIタグの説明だけを意味検索に使う | — | [test_visible_openapi_tags_supply_custom_meaning](../../packages/backend/tests/test_search_rank.py#L32) |

### フロントエンド（28項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| ログ取得に失敗したときも認証ヘッダーを送り、ダウンロードを中止して理由を表示する。 | — | [test_failed_log_download_reports_error](../../packages/frontend/tests/test_access_log_download.py#L8) |
| 承認済みの申請だけを候補にし、失効した商品の直接指定では仕様を取得しない。 | — | [test_console_reads_only_approved_spec](../../packages/frontend/tests/test_api_client.py#L8) |
| 本人に許可された操作と承認環境を選べ、操作制限のある委任認証は候補から外れる。 | — | [test_only_allowed_operations_and_environments](../../packages/frontend/tests/test_api_client.py#L27) |
| 本人の認証ではログイントークンを使い、委任認証では本人確認後に短期トークンを取得する。 | — | [test_identity_and_delegated_token](../../packages/frontend/tests/test_api_client.py#L58) |
| URL直接指定では入力したヘッダーと本文だけを使い、Cookieとリダイレクトを無効にする。 | — | [test_manual_request_uses_only_entered_headers](../../packages/frontend/tests/test_api_client.py#L74) |
| 送信先やヘッダーの形式が不正な場合やGETに本文がある場合は送信前にエラーになる。 | — | [test_invalid_manual_requests_are_rejected](../../packages/frontend/tests/test_api_client.py#L103) |
| チャットの候補と操作手順に、対応する商品・ガイドのリンクが付く。 | — | [test_chat_product_and_guide_are_linked](../../packages/frontend/tests/test_components.py#L27) |
| 提供者の検索結果で一致したガイドを先頭に表示し、件数を読み上げる。 | — | [test_guide_results_render_matching_cards_only](../../packages/frontend/tests/test_components.py#L54) |
| ガイドの条件をクリアすると全件に戻り、検索欄にフォーカスする。 | — | [test_guide_reset_restores_role_and_keyboard_focus](../../packages/frontend/tests/test_components.py#L68) |
| ユーザー管理の手順は閲覧でき、管理画面へのボタンは管理者にだけ表示する。 | — | [test_guide_article_shows_admin_navigation_only_to_admins](../../packages/frontend/tests/test_components.py#L102) |
| OpenAPIの型定義を参照し、クエリ入力欄に既定値の例を表示する。 | — | [test_operation_parameter_renders_openapi_default](../../packages/frontend/tests/test_components.py#L117) |
| パスの予約文字をエンコードし、配列とオブジェクトを指定形式で送る。 | — | [test_operation_location_encodes_path_and_query_values](../../packages/frontend/tests/test_components.py#L127) |
| 必須のクエリ入力が空なら、入力項目名を示して送信を止める。 | — | [test_operation_location_requires_mandatory_query](../../packages/frontend/tests/test_components.py#L147) |
| 公開履歴に版番号と変更された操作を表示し、差分がない種類は省く。 | — | [test_publication_history_shows_release_changes](../../packages/frontend/tests/test_components.py#L154) |
| ログインフォームに入力ラベルと自動入力の用途を示し、Enterで送信できる。 | — | [test_login_form_uses_native_labels_and_keyboard_submit](../../packages/frontend/tests/test_components.py#L182) |
| 管理者のメトリクス取得が失敗しても件数とログを表示し、再読み込みでグラフが戻る。 | — | [test_dashboard_recovers_from_metrics_failure](../../packages/frontend/tests/test_dashboard.py#L13) |
| JSON Pointerを解決し、同名のパス共通パラメーターを操作側で上書きする | — | [test_operation_overrides_path_parameter_and_resolves_pointer](../../packages/frontend/tests/test_openapi_fields.py#L4) |
| 初回パスワードの変更から認証アプリ登録まで、各応答のセッションを次の処理に渡す。 | — | [test_invitation_and_totp_setup](../../packages/frontend/tests/test_portal_login.py#L13) |
| 登録済みの利用者は確認コードを間違えても同じ画面で再入力できる。 | — | [test_returning_user_retries_mfa](../../packages/frontend/tests/test_portal_login.py#L61) |
| 再設定コードを受け取った利用者は新しいパスワードを設定してログイン画面に戻れる。 | — | [test_reset_returns_to_signin](../../packages/frontend/tests/test_portal_login.py#L83) |
| パスワードは認証サービスへのPOST本文だけで送信し、エラーは日本語で表示する。 | — | [test_credentials_sent_to_identity_service](../../packages/frontend/tests/test_portal_login.py#L104) |
| 画面内の入力不備と不具合を区別し、商品と本人の識別子だけを残す。 | — | [test_screen_error_context](../../packages/frontend/tests/test_screen_logs.py#L7) |
| API呼び出しには登録済み画面の識別子だけを付加する。 | — | [test_request_carries_screen](../../packages/frontend/tests/test_screen_logs.py#L25) |
| 独立した画面ファイルを追加すると配布物に入り、URLからデータ取得と描画までできる。 | — | [test_new_screen_is_packaged_loaded_and_rendered](../../packages/frontend/tests/test_screen_registry.py#L12) |
| 既存の固定・詳細URLを解決し、役割に応じたメニューを従来の順序で表示する。 | — | [test_existing_routes_and_role_menus](../../packages/frontend/tests/test_screen_registry.py#L64) |
| 別の画面が登録済みのURLを使うと重複したパスを示して失敗する。 | — | [test_duplicate_screen_path_is_rejected](../../packages/frontend/tests/test_screen_registry.py#L94) |
| 部署を10件ずつ表示し、次ページとプロジェクト一覧では該当する対象だけを開ける。 | — | [test_directory_pages_filter_before_paginating](../../packages/frontend/tests/test_workspace_screens.py#L38) |
| 権限と種類が一致する対象だけの利用統計を取得し、管理者専用の編集フォームを分離する。 | — | [test_scoped_monitor_and_edit_routes](../../packages/frontend/tests/test_workspace_screens.py#L56) |

### インフラ（11項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| 標準構成のリソース型と論理ID、スタック出力をスナップショットと照合する。 | — | [test_cloudformation_structure_matches_snapshot](../../packages/infra/tests/test_cdk_regression.py#L27) |
| AWS Solutionsの全ルールを実行し、記録済み以外の指摘がないことを確認する。 | — | [test_cdk_nag_detects_no_new_findings](../../packages/infra/tests/test_cdk_regression.py#L49) |
| ロジック変更で関数だけが更新され、依存変更で共有Layerだけが更新される。 | — | [test_backend_layer_changes_only_with_dependencies](../../packages/infra/tests/test_cdk_regression.py#L65) |
| モデルコードの変更ではLayerが変わらず、判定依存の変更は生成モデルに波及しない。 | — | [test_model_layer_changes_are_isolated](../../packages/infra/tests/test_cdk_regression.py#L104) |
| 判定・ツール選択・生成の各関数の配備が完了してからDB移行を開始する。 | — | [test_schema_waits_for_chat_models](../../packages/infra/tests/test_cdk_regression.py#L142) |
| 常時稼働の構成を置かず、Lambdaのメモリ・タイムアウトとログ保存期間を制限する。 | — | [test_cost_drivers_are_bounded](../../packages/infra/tests/test_cost.py#L8) |
| チャット処理と3モデルを分離し、予約枠を要求せず所定のメモリと作業領域で実行する。 | — | [test_chat_uses_separate_on_demand_python_functions](../../packages/infra/tests/test_cost.py#L32) |
| 非公開S3、呼び出しの認可、キャッシュと配信の設定が設計どおりである | — | [test_access_boundaries](../../packages/infra/tests/test_stack.py#L10) |
| すべてのリソースに管理情報を付け、タグ対応リソースには同じ値を付ける | サンプル付きの標準構成を検証<br>独自プロジェクト構成を検証 | [test_every_resource_has_ownership](../../packages/infra/tests/test_stack.py#L107) |
| 既存リソースの論理IDと分割後の所属が対応する | — | [test_existing_resources_keep_their_logical_ids](../../packages/infra/tests/test_stack.py#L142) |
| 在庫サンプルが操作に応じたステータスとJSON応答を返す。 | 登録されている商品の在庫一覧を返す<br>指定した商品の在庫を返す<br>未登録の商品は該当なしと返す | [test_stock_response](../../packages/infra/tests/test_stock_lambda.py#L34) |

### データベース（3項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| Aurora DSQL では公開スキーマの現行カラム名をシステムカタログから取得する | — | [test_dsql_column_names_use_the_system_catalog](../../packages/database/tests/test_migration_columns.py#L6) |
| DB定義がモデルと一致し、旧版のデータを移行できる | — | [test_schema_matches_models_and_replays](../../packages/database/tests/test_migrations.py#L8) |
| Aurora DSQL 接続では Amazon ルート CA を含むバンドルで証明書とホスト名を検証する。 | — | [test_dsql_uses_a_bundled_ca_for_full_tls_verification](../../packages/database/tests/test_session.py#L8) |

### ブラウザーE2E（20項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| OpenAPIの型からパス・クエリ・JSONを入力し、選択したキーでHTTPSの送料計算を実行する | — | [test_openapi_key_console](../../tests/e2e/browser/test_api_docs.py#L135) |
| ブラウザーで3方式を発行し、実時計で1分後に更新、シークレット変更・失効まで確認する | — | [test_credentials_console](../../tests/e2e/browser/test_credentials_console.py#L17) |
| 提供者が公開・自動承認・委任の条件を保存し、部署リーダーが個人申請を画面から却下する | — | [test_provider_policy_console](../../tests/e2e/browser/test_delegation_console.py#L13) |
| 提供者が利用者の操作を選び、送料1,400円のHTTPS応答と権限変更直後の転送停止を照合する | — | [test_person_operation_console](../../tests/e2e/browser/test_operation_console.py#L15) |
| デモの提供者と利用者が公開・申請・承認・実行・権限取消を画面で完了できる | — | [test_user_flow](../../tests/e2e/browser/test_portal.py#L24) |
| ホームで商品と手順を調べ、運営への問い合わせを明示的に送信できる。 | — | [test_home_chat_and_inquiry](../../tests/e2e/browser/test_portal.py#L29) |
| 6業務・20拠点の公開120件を全件照合し、PC・スマートフォンの検索とページ送りを確認する | — | [test_large_catalog](../../tests/e2e/browser/test_portal.py#L62) |
| 11月の外観変更を反映した明暗テーマの文字コントラストとキーボード操作を確認する | — | [test_console_visual_modes](../../tests/e2e/browser/test_portal.py#L133) |
| 3役で利用状況、ユーザー管理、通知、ログ保存、掲載終了を確認する | — | [test_governance_console](../../tests/e2e/browser/test_portal.py#L236) |
| スマートフォンでログインし、確認コードを入力して元のカタログへ戻れる。 | — | [test_portal_login_on_mobile](../../tests/e2e/browser/test_portal.py#L345) |
| 商品を公開し、利用者が商品詳細から利用申請できる | — | [test_publish_and_apply_from_product_page](../../tests/e2e/browser/test_product_publication.py#L15) |
| 実行レポートの画像をオフラインで拡大し、キーボード・タッチ・印刷でも確認できる | — | [test_report_image_viewer](../../tests/e2e/browser/test_report_images.py#L12) |
| 利用者が承認待ちの申請を取り下げると画面に反映され、同じ環境に再申請できる。 | — | [test_withdraw_pending](../../tests/e2e/browser/test_requirement_flows.py#L49) |
| 利用者が商品画面で旧版と新版の版番号、追加された操作と提供者の説明を確認できる。 | — | [test_release_history](../../tests/e2e/browser/test_requirement_flows.py#L71) |
| 部署リーダーの判断が済むまで提供者は承認できず、最終承認後に呼び出しが成功する。 | — | [test_ordered_review](../../tests/e2e/browser/test_requirement_flows.py#L96) |
| 拒否を記録した対象APIを管理者が一時停止し、許可済みの呼び出しだけを対象別に止められる。 | — | [test_admin_stops_target_after_denial](../../tests/e2e/browser/test_requirement_flows.py#L156) |
| 監査担当が他の利用者のアクセスと業務監査を同じIDで照合し、両方の記録を保存できる。 | — | [test_auditor_cross_checks_exports](../../tests/e2e/browser/test_requirement_flows.py#L192) |
| 提供者が商品ごとのトークンの上限を短縮すると、利用者による上限超過の発行を拒否する。 | — | [test_provider_shortens_token_lifetime](../../tests/e2e/browser/test_requirement_flows.py#L224) |
| 役割と検索語で使い方を絞り込み、手順から対象画面を開ける | — | [test_usage_guide](../../tests/e2e/browser/test_usage_guide.py#L13) |
| 管理者が組織階層と兼務を設定し、リーダーがキー・利用状況・停止と再開を操作する | — | [test_workspace_key_console](../../tests/e2e/browser/test_workspace_console.py#L28) |

### 開発ツール（55項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| 管理者がいないときだけメールで招待し、作成したユーザーの識別子を次のジョブに渡す。 | — | [test_invite_delivers_password_by_email](../../tools/tests/test_bootstrap_admin.py#L27) |
| 管理者が既にいるときは招待と権限付与の両方を省く。 | — | [test_existing_admin_skips_writes_in_both_jobs](../../tools/tests/test_bootstrap_admin.py#L53) |
| 同名ユーザーが存在して作成に失敗したときは権限付与用の出力を残さない。 | — | [test_collision_never_adopts_an_existing_account](../../tools/tests/test_bootstrap_admin.py#L62) |
| 招待と同じプールとユーザーなら初回ログイン用の管理権限を付与する。 | — | [test_grant_only_invited_user](../../tools/tests/test_bootstrap_admin.py#L73) |
| 招待後に同名の別ユーザーに置き換わったときは権限を付与しない。 | — | [test_replaced_user_cannot_be_promoted](../../tools/tests/test_bootstrap_admin.py#L95) |
| 招待後にスタックのプールが置き換わったときはユーザーを操作しない。 | — | [test_pool_replacement_stops_grant](../../tools/tests/test_bootstrap_admin.py#L106) |
| 招待先を設定していないときはアカウントを作成しない。 | — | [test_missing_recipient_stops_before_creation](../../tools/tests/test_bootstrap_admin.py#L115) |
| AWS CLI の照会結果を読み取り、グループ追加で応答が空でも成功する。 | — | [test_cli_returns_json_and_handles_empty_responses](../../tools/tests/test_bootstrap_admin.py#L124) |
| AWS CLI が失敗したときは操作名を示し、引数の招待先を例外に含めない。 | — | [test_cli_error_hides_invitation_address](../../tools/tests/test_bootstrap_admin.py#L137) |
| 説明文のみの変更は既存の全体カバレッジを引き継ぎ、実行環境の準備を省ける。 | — | [test_docs_reuse_complete_report](../../tools/tests/test_ci_scope.py#L17) |
| 単体テストの変更は該当層に絞り、複数層の変更は両方を選ぶ。 | — | [test_component_tests_and_mixed_changes](../../tools/tests/test_ci_scope.py#L25) |
| CSSは画面の検証を行い、認証クライアントの変更ではCognitoの画面操作も確認する。 | — | [test_css_and_authentication_have_different_consumers](../../tools/tests/test_ci_scope.py#L37) |
| 画面のビルド処理を変えるとCSS解析とコード解析の規則も検査する。 | — | [test_frontend_builder_runs_stylesheet_and_design_policy_tests](../../tools/tests/test_ci_scope.py#L47) |
| インフラの実装変更ではCDK・監査・AWSの画面連携に必要な環境を用意する。 | — | [test_infra_and_aws_require_browser_and_assets](../../tools/tests/test_ci_scope.py#L56) |
| 計測対象コードの変更時は以前に実行行を記録した層も再計測する。 | — | [test_measured_source_invalidates_suites_that_executed_it](../../tools/tests/test_ci_scope.py#L65) |
| 保存結果がない層は比較元での補完対象にし、PRの実行対象とは区別する。 | — | [test_missing_coverage_never_becomes_a_partial_baseline](../../tools/tests/test_ci_scope.py#L74) |
| 未知の領域・依存ロック・CI定義を変更した場合は全検証を選ぶ。 | — | [test_unknown_or_shared_input_runs_all_checks](../../tools/tests/test_ci_scope.py#L86) |
| 日本語と空白を含むパスの移動と削除を移動元も含めて判定する。 | — | [test_git_diff_includes_deleted_and_both_renamed_paths](../../tools/tests/test_ci_scope.py#L100) |
| 全領域の実行行と未実行行を区別し、未読込のモデルとインフラの入口も分母に含める。 | — | [test_coverage_includes_all_runtime_layers_and_unexecuted_files](../../tools/tests/test_ci_scope.py#L122) |
| 画面変更時はその画面を実行した別の層を再計測し、無関係な層の結果を再利用する。 | — | [test_changed_screen_invalidates_only_suites_that_executed_it](../../tools/tests/test_ci_scope.py#L163) |
| 旧形式または異なる計測条件の結果は再利用せず、同じ条件の結果だけを使う。 | — | [test_cache_requires_same_coverage_policy](../../tools/tests/test_ci_scope.py#L177) |
| 比較元でブラウザーのタイムアウトだけが起きた場合に限り再計測する。 | — | [test_baseline_retry_requires_only_browser_timeouts](../../tools/tests/test_ci_scope.py#L188) |
| エージェントとモデルの変更で単体・API結合・構造・型・配布物の検査を選ぶ。 | — | [test_agent_sources_select_agent_consumers_and_deployment_checks](../../tools/tests/test_ci_scope.py#L203) |
| 移動前と同じ範囲の総カバレッジを比較に使い、古いパスのスイート別結果は再利用しない。 | — | [test_moved_agent_reuses_only_aggregate_baseline](../../tools/tests/test_ci_scope.py#L215) |
| 間接依存の更新は利用パッケージに絞り、移動した依存は変更前と変更後の両方を検証する。 | — | [test_lock_changes_follow_transitive_old_and_new_consumers](../../tools/tests/test_ci_scope.py#L232) |
| PRテンプレートだけの差分はキャッシュがなくても準備やテストを起動せず、空の計測を公開しない。 | — | [test_template_plan_never_bootstraps_coverage](../../tools/tests/test_ci_scope.py#L261) |
| 検査の直前の説明と実行条件を対応付け、シェル文字列内の偽コメントを無視する。 | — | [test_workflow_comments_follow_steps](../../tools/tests/test_completion.py#L8) |
| ブランチの下限・低下幅を合成し、非同期テストとクラスの説明を定義行から取得する。 | — | [test_rule_changes_and_test_edits_reach_document](../../tools/tests/test_completion.py#L28) |
| 旧方式で測った成果物は比較元に階層付き画面がなく計測器の他の部分が一致するときだけ使う。 | — | [test_flat_baseline_requires_equivalent_file_selection](../../tools/tests/test_coverage_baseline.py#L6) |
| コミットフックが規約に沿った件名を許可し、規約外の件名を理由付きで拒否する。 | — | [test_commit_message_hook](../../tools/tests/test_delivery_contracts.py#L12) |
| mainへのマージを検証した後だけOIDCで配備し、PRでは検証を実行する。 | — | [test_merge_deploy_workflow](../../tools/tests/test_delivery_contracts.py#L30) |
| 変異後のアサーション失敗を検出に数え、収集エラーやスキップを検出件数から除く。 | — | [test_mutation_verdict](../../tools/tests/test_delivery_contracts.py#L57) |
| 全APIの入出力を出力し、再生成時に不要な文書を取り除く | — | [test_all_routes_inputs_outputs_and_cleanup](../../tools/tests/test_design.py#L8) |
| CRUD表の全APIを個別設計書の根拠と照合できる | — | [test_crud_matrices_cover_all_routes_and_match_per_api_evidence](../../tools/tests/test_design.py#L43) |
| ORMの操作と条件付きAWS書き込みを設計解析で追跡できる | — | [test_sqlalchemy_and_conditional_aws_writes](../../tools/tests/test_design.py#L78) |
| 相対インポートと再帰をたどり、動的SQLを識別できる | — | [test_sql_sources_relative_import_recursion_and_dynamic_sql](../../tools/tests/test_design.py#L97) |
| UTF-8の正常な文書を許可し、異常な符号化や改行を検出する | — | [test_text_policy](../../tools/tests/test_design.py#L117) |
| OpenAPIの通信上の項目名を保ち、用途に応じた和名を表示する | — | [test_openapi_preserves_wire_names_and_labels_them_in_context](../../tools/tests/test_design.py#L124) |
| 過去に保存した独自項目を返しつつ、公開する入れ子の型をフィールド宣言から取得する。 | — | [test_nested_contracts_preserve_legacy_records_and_follow_field_annotations](../../tools/tests/test_design.py#L150) |
| 各リソースを所属別に掲載し、配列・参照・埋め込みJSONを項目ごとの行に展開する。 | — | [test_component_parameter_sheet](../../tools/tests/test_infrastructure_docs.py#L8) |
| 所属が欠けたリソースは論理IDを示して生成を止める。 | — | [test_missing_component_identifies_resource](../../tools/tests/test_infrastructure_docs.py#L55) |
| 同じ依存を別の場所で同期してもLayerが一致し、依存を更新したときだけ内容が変わる。 | — | [test_layer_rebuild_is_reproducible](../../tools/tests/test_lambda_layer.py#L28) |
| 各Layerが対応する依存群をロックから取り出し、正しいPythonの版で同期する。 | — | [test_each_lambda_layer_exports_its_locked_dependencies](../../tools/tests/test_lambda_layer.py#L53) |
| 実行予定の単体テストにJUnit結果がなければ、要件を未実行として不合格にする。 | — | [test_unexecuted_requirement_fails](../../tools/tests/test_requirement_evidence.py#L11) |
| 同じ要件の一部の条件だけをスキップしても要件を合格にしない。 | — | [test_skipped_requirement_fails](../../tools/tests/test_requirement_evidence.py#L20) |
| ブラウザーの成功結果には対応する実画像を必要とし、画像を相対リンクから参照できる。 | — | [test_required_browser_capture](../../tools/tests/test_requirement_evidence.py#L32) |
| 差分対象外を成功から区別し、テスト未登録の要件と消えた関数を検知する。 | — | [test_scope_and_missing_definition](../../tools/tests/test_requirement_evidence.py#L63) |
| 収集エラーや破損したJUnitがあれば、取得済みの結果を残してCIを失敗させる。 | — | [test_junit_errors_survive_reporting](../../tools/tests/test_requirement_evidence.py#L82) |
| 収集した条件の一部だけが成功したJUnitでは、実行予定の要件を合格にしない。 | — | [test_missing_parameter_result_fails](../../tools/tests/test_requirement_evidence.py#L94) |
| 本文の定義を一度だけ掲載し、両方の一覧から日本語名の要件を開ける。 | — | [test_indexes_follow_sources](../../tools/tests/test_requirements.py#L23) |
| 条件または操作で未定義の用語を使うと、その用語を示して失敗する。 | — | [test_undefined_term_in_condition_or_result_fails](../../tools/tests/test_requirements.py#L45) |
| 別々の要件で同じ用語を再定義すると失敗する。 | — | [test_duplicate_definition_fails](../../tools/tests/test_requirements.py#L53) |
| 見出しと異なるファイル名と、理由が空欄の要件をそれぞれ拒否する。 | — | [test_wrong_filename_and_empty_section_fail](../../tools/tests/test_requirements.py#L61) |
| 実際のPR相当の差分で編集・改名・テンプレートを除外し、新規要件だけを受け付ける。 | — | [test_feature_requires_added_requirement](../../tools/tests/test_requirements.py#L73) |
| テーマ生成はCSSの文字列とコメントを除外し、入れ子の変数と代替値を取得する。 | — | [test_stylesheet_uses_only_variable_references](../../tools/tests/test_stylesheet.py#L4) |

### AWSエミュレーターE2E（14項目）

| 確認内容 | 条件別の確認内容 | テスト定義 |
| --- | --- | --- |
| AWS EmulatorのCognito利用者とシステムのトークンを発行し、HTTPS到達・拒否・秘密更新を確認する | — | [test_client_tokens_reach_https](../../tests/e2e/aws/test_credential_tokens.py#L37) |
| 合成したテンプレートから移行 Lambda を構築し、関数 ZIP と依存 Layer を登録できる | — | [test_deploy_migration_lambda](../../tests/e2e/aws/test_migration_deployment.py#L27) |
| 配布する関数 ZIP と依存 Layer の組み合わせで移行処理が DSQL 方言で全リビジョンを適用し、再実行できる | — | [test_run_packaged_migration_on_postgresql](../../tests/e2e/aws/test_migration_deployment.py#L78) |
| 配備用コードとLayerだけでモデルを読み込み、外部パッケージの読み込み元を確認する。 | 判定用の依存からネイティブ推論ライブラリを読み込む<br>生成用の依存からモデル取得用SDKを読み込む | [test_model_imports_from_deployment_packages](../../tests/e2e/aws/test_model_packages.py#L28) |
| 配備用コードとLayerだけでワーカーを読み込み、同梱ガイドを使って回答を生成できる。 | — | [test_agent_imports_from_worker_deployment_package](../../tests/e2e/aws/test_model_packages.py#L59) |
| Cognitoで識別した2人が画面で承認し、在庫照会・取消・監査まで進める | — | [test_cognito_browser](../../tests/e2e/aws/test_portal.py#L144) |
| 承認した呼び出しを接続先へ転送し、権限取消後は遮断する | 検証環境の在庫を照会する<br>本番環境の在庫を照会する<br>利用者がLambdaへ接続する<br>システムがLambdaへ接続する<br>利用者がHTTPS先へ接続する | [test_approved_calls_reach_upstream](../../tests/e2e/aws/test_portal.py#L192) |
| 6種類を個別に登録・公開・承認して実行し、HTTPSの受信・業務応答・監査記録を照合する | — | [test_marketplace_contracts](../../tests/e2e/aws/test_portal.py#L337) |
| 承認済みのHTTPS接続先が停止したとき、502と監査・アクセスログを同じIDで追跡できる | — | [test_upstream_unavailable](../../tests/e2e/aws/test_portal.py#L399) |
| AWS EmulatorのCognitoでユーザー追加・所属・削除・既発行トークンの停止を確認する | — | [test_cognito_member_lifecycle](../../tests/e2e/aws/test_portal.py#L452) |
| 構築したS3・API Gateway・Lambdaのタグを取得し、在庫APIが商品を返す | — | [test_deployed_resources](../../tests/e2e/aws/test_resources.py#L9) |
| DSQLクラスターが削除保護付きで稼働状態になる | — | [test_create_dsql_cluster](../../tests/e2e/aws/test_resources.py#L67) |
| 公開時にOpenAPI仕様の世代をS3に個別保存する | — | [test_openapi_archive_versions](../../tests/e2e/aws/test_resources.py#L80) |
| EmulatorのCognitoと共有・本人キーでHTTPS接続先を呼び、別人・範囲外・失効を拒否する | — | [test_scoped_keys_reach_https](../../tests/e2e/aws/test_scoped_keys.py#L60) |
