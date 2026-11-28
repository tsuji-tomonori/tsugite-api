"""JUnitのテスト結果とブラウザーの画面記録を、日本語の単独で閲覧できるレポートにまとめる。"""

import argparse
import base64
import json
import os
import subprocess
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts"
COMPONENTS = {
    "Database": "データベース・移行",
    "Runtime": "API実行",
    "Gateway": "APIゲートウェイ",
    "Portal": "画面配信",
    "Identities": "認証",
    "Bindings": "接続先設定",
    "Stack": "スタック管理",
}
CSS = """
*{box-sizing:border-box}body{margin:0;color:#142e35;background:#f5f7f5;font:16px/1.65 system-ui,sans-serif}
main{max-width:1100px;margin:auto;padding:32px 24px 60px}header,section{margin-bottom:24px;padding:24px 30px;background:white;border:1px solid #cbd9d6;border-radius:12px}
h1,h2,h3{line-height:1.35;margin:0 0 12px}h1{font-size:clamp(26px,4vw,40px)}h2{font-size:23px}header{border-top:6px solid #146653}
p{margin:8px 0}nav{display:flex;gap:22px;flex-wrap:wrap;margin:14px 0 0}a{color:#075f50}table{width:100%;border-collapse:collapse;font-size:14px}
th,td{padding:9px 8px;border-bottom:1px solid #dde6e3;text-align:left;vertical-align:top}th{background:#edf3f0}td small{display:block;color:#54676d;overflow-wrap:anywhere}
.ok{color:#126048}.bad{color:#a02a2a}.status{white-space:nowrap;font-weight:700}
.numbers{font-size:20px;font-weight:700}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,370px),1fr));gap:14px}
figure{margin:0;padding:12px;background:#f5f8f6;border:1px solid #d6e1dd;border-radius:8px}img{display:block;max-width:100%;height:auto;margin:8px auto}
figcaption{font-size:14px;font-weight:650}details{margin:12px 0}summary{cursor:pointer;font-weight:650;padding:6px 0}code{overflow-wrap:anywhere}.wide{overflow:auto}.wide table{table-layout:fixed}.wide th:first-child{width:55%}.wide td{overflow-wrap:anywhere}.wide th:nth-child(2){width:21%}
@media(max-width:620px){main{padding:12px 8px}header,section{padding:16px 12px}th,td{padding:8px 4px}}
@media print{main,section,header{padding:6px;border:0}nav{display:none}figure,tr{break-inside:avoid}.grid{display:block}img{max-height:300px}header,section{margin-bottom:10px}figure{margin:8px 0}h2,h3,summary{break-after:avoid}small{font-size:9px}nav,td a{display:none}body{font-size:12px;background:white}table{font-size:11px}th,td{padding:4px}.wide{overflow:visible}}
"""


CSS += """
body{color:#182c42;background:#f3f6fa}header{border:0;border-radius:14px;background:#162c44;color:#fff}
header a{color:#c3e2ff}header .numbers{color:#ffe1aa}section{border-color:#cedae5}a{color:#075ca8}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef3f8;padding:12px;font-size:13px}th{background:#edf3f9}tbody th{background:white;font-weight:650}h3{font-size:17px;margin-top:14px}
article{padding:8px 0;border-bottom:1px solid #dfe7ef}li{overflow-wrap:anywhere}figure{background:#f3f6fa;border-color:#d6e1ec}
@media print{header{color:#162c44;background:white}header .numbers{color:#174b34}nav{display:none}}
"""


CSS += """
.shot-open { display:block; position:relative; width:100%; padding:0; border:0;
  background:transparent; color:inherit; cursor:zoom-in; }
.shot-open img { margin:8px auto 0; }
.shot-open .zoom-label { position:absolute; bottom:6px; right:6px; padding:1px 9px; border-radius:16px;
  background:#252525; color:white; font:600 13px/1.6 system-ui,sans-serif; }
.shot-open:focus-visible, #shot-viewer :focus-visible { outline:3px solid #1674bc; outline-offset:2px; }
#shot-viewer { width:min(96vw,1600px); height:94vh; height:94dvh; max-width:none; max-height:none;
  padding:0; border:1px solid #888; border-radius:12px; background:white; color:#202020; }
#shot-viewer[open] { display:grid; grid-template-rows:auto minmax(0,1fr); }
#shot-viewer::backdrop { background:rgba(16,16,16,.78); }
.viewer-tools { display:flex; align-items:center; flex-wrap:wrap; gap:8px 12px; padding:10px 16px;
  border-bottom:1px solid #aaa; }
.viewer-tools h2 { margin:0 auto 0 0; font-size:16px; }
.viewer-tools select, .viewer-tools button { font:inherit; min-height:44px; border:1px solid #777;
  border-radius:8px; padding:4px 10px; background:white; color:#222; cursor:pointer; }
.shot-stage { overflow:auto; background:#eee; overscroll-behavior:contain; }
.shot-stage:focus-visible { outline-offset:-3px !important; }
.shot-stage img { display:block; margin:0 auto; max-width:none; max-height:none; }
.shot-stage.fit img { width:100%; height:100%; object-fit:contain; }
@media screen { html:has(#shot-viewer[open]) { overflow:hidden; } }
@media (max-width:620px) {
  #shot-viewer { width:100vw; height:100vh; height:100dvh; border-radius:0; border:0; }
  .viewer-tools { padding:8px 12px; }
  .viewer-tools h2 { flex-basis:100%; }
}
@media print {
  #shot-viewer[open], #shot-viewer::backdrop, .zoom-label { display:none !important; }
  .shot-open { cursor:auto; }
}
"""

# Keep the image payload once per screenshot. The viewer reuses the selected thumbnail's data URL.
IMAGE_VIEWER = """
<dialog id="shot-viewer" aria-labelledby="shot-title">
  <div class="viewer-tools"><h2 id="shot-title">画面の拡大</h2>
    <label>表示倍率 <select id="shot-scale"><option value="fit">全体表示</option>
      <option value="1">100%（原寸）</option><option value="2">200%</option></select></label>
    <button type="button" id="shot-close" autofocus>閉じる</button>
  </div>
  <div class="shot-stage fit" tabindex="0" role="region" aria-label="拡大画像"></div>
</dialog>
<script>
const viewer = document.getElementById("shot-viewer");
const title = document.getElementById("shot-title");
const stage = viewer.querySelector(".shot-stage");
const scale = document.getElementById("shot-scale");
let opener;

function resizeImage() {
  const image = stage.querySelector("img");
  if (!image) return;
  stage.classList.toggle("fit", scale.value === "fit");
  image.style.width = scale.value === "fit" ? "" : image.naturalWidth * Number(scale.value) + "px";
}

document.getElementById("screens").addEventListener("click", event => {
  const button = event.target.closest(".shot-open");
  if (!button) return;
  opener = button;
  const source = button.querySelector("img");
  const image = new Image();
  image.alt = source.alt;
  image.addEventListener("load", resizeImage, {once:true});
  stage.replaceChildren(image);
  scale.value = "fit";
  title.textContent = source.alt;
  image.src = source.currentSrc || source.src;
  resizeImage();
  viewer.showModal();
  stage.scrollTo(0, 0);
});
scale.addEventListener("change", resizeImage);
document.getElementById("shot-close").addEventListener("click", () => viewer.close());
viewer.addEventListener("close", () => {
  stage.replaceChildren();
  if (opener) opener.focus({preventScroll:true});
});
let collapsed = [];
window.addEventListener("beforeprint", () => {
  collapsed = Array.from(document.querySelectorAll("#screens details:not([open])"));
  for (const item of collapsed) item.open = true;
});
window.addEventListener("afterprint", () => {
  for (const item of collapsed) item.open = false;
  collapsed = [];
});
</script>
"""


def result(case):
    for tag, label in (("error", "エラー"), ("failure", "失敗"), ("skipped", "スキップ")):
        if case.find(tag) is not None:
            return label
    return "成功"


def inventory():
    file = ROOT / "packages/infra/cdk.out/TsugiteApi.template.json"
    if not file.exists():
        return "<p>合成テンプレートを取得できませんでした。</p>"
    resources = json.loads(file.read_text())["Resources"]
    rows = []
    count = 0
    for name, r in sorted(resources.items()):
        meta = r.get("Metadata", {}).get("Tsugite", {})
        props = r.get("Properties", {})
        tags = props.get("UserPoolTags", props.get("Tags"))
        if isinstance(tags, list):
            tags = {t["Key"]: t["Value"] for t in tags}
        tagged = tags is not None and bool(meta) and meta.items() <= tags.items()
        count += tagged
        kind = "AWSタグ" if tagged else ("テンプレートの管理情報" if tags is None and meta else "要確認")
        group = meta.get("Component", "未設定")
        rows.append(
            f"<tr><td>{escape(name)}<small>{escape(r['Type'])}</small></td><td>{escape(COMPONENTS.get(group, group))}</td><td>{kind}</td></tr>"
        )
    return (
        f"<p>合成した{len(resources)}件のうち、{count}件で <code>Application=TsugiteAPI</code>、"
        "<code>ManagedBy=AWS-CDK</code> と所属を示す <code>Component</code> がAWSタグに設定されています。"
        "CloudFormationにタグ属性がない型では、同じ3項目をリソースのメタデータに記録します。</p>"
        "<details><summary>リソースごとの確認結果</summary><div class='wide'><table><tr><th>論理IDと型</th><th>所属</th><th>記録先</th></tr>"
        + "".join(rows)
        + "</table></div></details>"
    )


GALLERIES = {
    "test_credentials_console": ("認証方式の選択と更新条件", 3),
    "test_person_operation_console": ("利用者別の操作権限とAPI Docsからの実行", 2),
    "test_provider_policy_console": ("提供者の公開設定と部署リーダーの判断", 2),
    "test_workspace_key_console": ("組織・リーダーの利用状況とAPIキー", 3),
    "test_openapi_key_console": ("API DocsからHTTPSの送料計算を実行", 3),
    "test_governance_console": ("役割別ホーム・通知・アラート・利用監査", 9),
    "test_console_visual_modes": ("AWSコンソールに合わせたライト・ダーク・強制カラー", 4),
    "test_large_catalog": ("公開120件のカタログ", 4),
    "test_cognito_browser": ("AWS Emulatorでの提供者・利用者の画面", 11),
    "test_user_flow": ("ローカルデモでの提供者・利用者の画面", 11),
}

JOURNEYS = [
    (
        "認証方式・有効期限",
        "提供者から利用者まで上限を引き継ぐ。短期Bearerの更新、アプリによる代理実行、長期間使うシステムのトークン再発行を確かめる。",
        [
            "test_nested_token_lifetime",
            "test_credentials_console",
            "test_persistent_system_and_legacy_expiry",
        ],
    ),
    (
        "人・アプリごとの操作権限",
        "対象APIとOpenAPIの操作を選び、実際のHTTPS応答と受信件数を照合する。権限の取り消しは発行済みトークンにも適用する。",
        ["test_person_operation_console", "test_client_tokens_reach_https"],
    ),
    (
        "組織・利用範囲",
        "管理者が階層と兼務を設定し、リーダーは担当範囲の所属と利用状況を確認して停止・再開できる。",
        ["test_workspace_key_console", "test_delegation_search_and_personal_isolation"],
    ),
    (
        "公開範囲・申請と判断",
        "閲覧可能な商品だけをハイブリッド検索する。提供者のルールに応じ、プロジェクト・個人の申請を自動承認または委任する。",
        [
            "test_hybrid_retrieval",
            "test_visible_openapi_tags_supply_custom_meaning",
            "test_delegation_search_and_personal_isolation",
        ],
    ),
    (
        "キー選択・実呼び出し",
        "キーを発行し、OpenAPIに沿ってパラメーターを入力する。HTTPS接続先の応答・監査を照合し、失効後は転送を拒否する。",
        ["test_scoped_keys_reach_https", "test_openapi_key_console"],
    ),
    (
        "ユーザー管理",
        "所属と役割を指定して追加し、削除後は以前のアクセスも止める。",
        ["test_cognito_member_lifecycle", "test_member_lifecycle"],
    ),
    (
        "掲載内容の変更・削除",
        "説明は掲載中も修正できる。仕様変更時は再承認、削除後は履歴を保持する。",
        ["test_listing_revisions", "test_governance_console"],
    ),
    (
        "通知と利用上限",
        "ベルで対象者に通知し、設定した上限に達すると次の呼び出しを停止する。",
        ["test_notification_scope", "test_alert_window_and_access_logs"],
    ),
    (
        "利用状況とログ",
        "役割別ホームから時系列を絞り込み、同じ期間のログを保存して業務監査を照合する。",
        ["test_governance_console", "test_alert_window_and_access_logs"],
    ),
    (
        "登録・公開",
        "下書きは提供元だけが参照できる。接続失敗は公開を止める。",
        ["test_lifecycle", "test_failed_probe_keeps_draft"],
    ),
    (
        "発見・申請",
        "仕様中の操作名で検索し、プロジェクトと環境を指定して申請する。",
        ["test_cognito_browser", "test_large_catalog"],
    ),
    (
        "却下・再申請",
        "目的の補足を求めて却下し、申請者に理由を返す。却下直後の業務呼び出しは接続先に届かない。",
        ["test_cognito_browser", "test_approved_calls_reach_upstream[cognito-https]"],
    ),
    (
        "取下げ・競合",
        "申請者による取下げと、古い版の承認の拒否を確認する。",
        ["test_reapply", "test_withdrawal_and_audit_visibility"],
    ),
    (
        "承認・利用",
        "承認された組み合わせでGET・POSTを転送する。異なるプロジェクト・環境は403になる。",
        ["test_marketplace_contracts", "test_approved_calls_reach_upstream[machine-lambda]"],
    ),
    (
        "掲載終了・権限取消",
        "掲載終了後は新規申請を止める。既存利用者は権限取消まで呼べ、取消直後から同じトークンで403になる。",
        ["test_cognito_browser", "test_lifecycle"],
    ),
    (
        "監査",
        "呼び出し開始・応答または拒否とHTTPアクセスログのIDが一致する。第三のプロジェクトには記録が見えない。",
        ["test_approved_calls_reach_upstream[cognito-https]", "test_withdrawal_and_audit_visibility"],
    ),
]


def review_table(results, entries):
    rows = []
    for area, expected, cases in entries:
        verdict = "確認済み" if all(results.get(name) == "成功" for name in cases) else "要確認"
        evidence = " ".join(
            f'<a href="#case-{escape(name, quote=True)}">試験{i}</a>' for i, name in enumerate(cases, 1)
        )
        rows.append(
            f"<tr><th scope='row'>{area}</th><td>{expected}</td><td>{verdict}<small>{evidence}</small></td></tr>"
        )
    return (
        "<table><thead><tr><th>観点</th><th>確認内容</th><th>結果</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def build():
    counts = Counter()
    results = {}
    findings = []
    tables, galleries, missing, dates = [], [], [], []
    for source, title in (("junit.xml", "アプリ・CDK・デモ画面"), ("aws-emulator.xml", "AWS Emulator")):
        xml = OUT / source
        if not xml.is_file():
            missing.append(title + "の実行結果")
            continue
        root = ElementTree.parse(xml)
        rows = []
        for suite in root.iter("testsuite"):
            if stamp := suite.get("timestamp"):
                dates.append(datetime.fromisoformat(stamp).astimezone(ZoneInfo("Asia/Tokyo")))
        for case in root.iter("testcase"):
            name = case.attrib["name"]
            description = case.find("./properties/property[@name='case_description']")
            title = description.attrib["value"] if description is not None else name
            status = result(case)
            counts[status] += 1
            results[name] = status
            readings = [
                escape(p.attrib["value"]) for p in case.findall("./properties/property[@name='finding']")
            ]
            for sample in case.findall("./properties/property[@name='trace_sample']"):
                value = sample.attrib["value"]
                code = json.loads(value)["HTTPアクセスログ"]["status"]
                findings.append(
                    f"<details><summary>HTTP {code} の業務監査とアクセスログの原文</summary><pre>{escape(value)}</pre></details>"
                )
            for prop in case.findall("./properties/property[@name='access_sample']"):
                logs = json.loads(prop.attrib["value"])
                file = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in logs)
                encoded = base64.b64encode(file.encode()).decode()
                rows_html = "".join(
                    f"<tr><td>{escape(r['at'])}</td><td>{escape(r['actor'])} / {escape(r['project'])}</td><td>{escape(r['method'])} {escape(r['operation'])}</td><td>{r['status']}</td><td>{r['duration_ms']}</td><td><code>{escape(r['request_id'])}</code></td></tr>"
                    for r in logs
                )
                findings.append(
                    f"<h3>利用上限テストのアクセスログ（{len(logs)}件）</h3><p>検証用の利用者が実際に送ったリクエストの記録です。応答コードとリクエストIDで照合できます。</p><table><tr><th>日時（UTC）</th><th>利用者 / 所属</th><th>操作</th><th>HTTP</th><th>ms</th><th>リクエストID</th></tr>{rows_html}</table><a download='access-log.jsonl' href='data:application/x-ndjson;base64,{encoded}'>このアクセスログを保存（JSONL）</a>"
                )
            if readings:
                findings.append(
                    "<article><h3>"
                    + escape(title)
                    + "</h3><ul>"
                    + "".join(f"<li>{v}</li>" for v in readings)
                    + "</ul></article>"
                )
            shots = []
            for prop in case.findall("./properties/property[@name='screenshot']"):
                path, caption = prop.attrib["value"].split("|", 1)
                image = (OUT / path).resolve()
                if not image.is_relative_to((OUT / "screenshots").resolve()) or not image.is_file():
                    missing.append(caption)
                    continue
                encoded = base64.b64encode(image.read_bytes()).decode()
                shots.append(
                    f"<figure><figcaption>{escape(caption)}</figcaption>"
                    f"<button type='button' class='shot-open' aria-haspopup='dialog' aria-controls='shot-viewer' "
                    f"aria-label='{escape(caption, quote=True)}を拡大'>"
                    f"<img loading='lazy' alt='{escape(caption, quote=True)}' src='data:image/png;base64,{encoded}'>"
                    "<span class='zoom-label' aria-hidden='true'>拡大</span></button></figure>"
                )
            if name in GALLERIES and status == "成功" and len(shots) < GALLERIES[name][1]:
                missing.append(title + "の画面記録")
            evidence = ""
            if shots:
                anchor = "images-" + str(len(galleries))
                evidence = f" · <a href='#{anchor}'>画面{len(shots)}枚</a>"
                label = GALLERIES.get(name, (name, 0))[0]
                galleries.append(
                    f"<details id='{anchor}' {'open' if name == 'test_console_visual_modes' else ''}><summary>{escape(label)}（{len(shots)}枚）</summary><div class='grid'>{''.join(shots)}</div></details>"
                )
            style = "ok" if status == "成功" else "bad"
            rows.append(
                f"<tr id='case-{escape(name, quote=True)}'><td>{escape(title)}<small>{escape(name)}{evidence}</small></td><td class='status {style}'>{status}</td><td>{float(case.get('time', '0')):.2f} 秒</td></tr>"
            )
        tables.append(
            f"<h3>{title} · {len(rows)}件</h3><table><tr><th>テストケースと期待結果</th><th>実行結果</th><th>時間</th></tr>{''.join(rows)}</table>"
        )
    rev = (
        os.getenv("GITHUB_SHA")
        or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    )
    date = min(dates).strftime("%Y年%m月%d日 %H:%M JST") if dates else "実行時刻不明"
    summary = "　".join(f"{label} {counts[label]}件" for label in ("成功", "失敗", "エラー", "スキップ"))
    gaps = f"<p class='bad'>未取得：{escape('、'.join(missing))}</p>" if missing else ""
    design = review_table(
        results,
        [
            (
                "11月の表示仕様",
                "グレーを基調とする明暗テーマで文字と背景のコントラスト、主要ボタン、リンクを実画面で照合。配色変更後の入力保持、設定の保存、強制カラーでのフォーカスも確認する。",
                ["test_console_visual_modes"],
            ),
            (
                "探しやすさ",
                "拠点と業務をAPI名で識別し、名前から詳細に移動する。120件を12件ずつ表示し、キーワードと環境で3件に絞る。",
                ["test_large_catalog", "test_cognito_browser"],
            ),
            (
                "判断の伝わり方",
                "承認待ち・却下・利用中・取消済みを文字でも示す。利用者は却下理由を読み、目的を補って再申請できる。",
                ["test_cognito_browser"],
            ),
            (
                "画面幅・キーボード",
                "390px幅と1440px幅で一覧の横はみ出しを調べ、Tabのフォーカス枠、Enterでの検索、空の検索結果を確認する。実行結果の文字と背景のコントラスト比は4.5以上。",
                ["test_large_catalog", "test_user_flow"],
            ),
            (
                "監査への導線",
                "実行結果から対応する記録だけを開ける。ID、主体、環境、結果を表示する。",
                ["test_cognito_browser"],
            ),
        ],
    )
    output = f"""<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>継手API テスト結果</title><style>{CSS}</style><main>
    <header><h1>継手API テスト結果</h1><p>{date} 開始 · 対象コミット <code>{escape(rev[:12])}</code></p>
    <p class="numbers">{summary}</p>{gaps}<nav><a href="#flow">業務フロー</a><a href="#review">デザインレビュー</a><a href="#observed">実行記録</a><a href="#screens">画面の記録</a><a href="#cases">全テストケース</a><a href="#cdk">CDKのタグ</a></nav></header>
    <section id="flow"><h2>公開から利用終了まで</h2>{review_table(results, JOURNEYS)}</section>
    <section id="review"><h2>デザインレビュー</h2><p>Amazon DataZoneの提供者インベントリ、公開カタログ、プロジェクト単位の利用申請を設計の基準にしました。ライトテーマは2026年11月13日（日本時間）に公開されたAWSコンソールの画像を基準にしました。薄いグレーの背景に白いカードを置き、主要操作を濃色、リンクを下線付きで表示します。ダークテーマの色と日本語の書体は継手APIの設計値です。<a href="https://x.com/darkosubotica/status/2121022986144895310">更新後の画面を紹介した投稿</a>。</p>{design}<p>実装画面と操作テストによるレビューです。実利用者によるユーザビリティ調査や同時アクセスの負荷測定は今回の対象外です。</p></section>
    <section id="observed"><h2>業務応答とログの照合記録</h2>{"".join(findings) or "実行記録なし"}</section>
    <section id="screens"><h2>画面の記録</h2>{"".join(reversed(galleries)) or "画面記録はありません。"}</section>
    <section id="cases"><h2>テストケースと実行結果</h2>{"".join(tables)}</section>
    <section id="cdk"><h2>CDKリソースのタグ</h2>{inventory()}</section>
    <section><h2>検証環境</h2><p>画面はChromiumで撮影しました。AWS操作には公式AWS Emulatorを使い、DSQLはクラスターの稼働までを確認します。業務データとDB移行にはSQLite、システム用トークンにはテスト用署名鍵を使います。実AWSへの配備、CloudFront経由の全経路、Cognitoのホスト型ログイン・MFA・OAuth発行は今回の検証範囲外です。</p></section></main>{IMAGE_VIEWER}</html>"""
    OUT.mkdir(exist_ok=True)
    (OUT / "test-report.html").write_text(output, encoding="utf-8")
    return not missing and not any(counts[v] for v in ("失敗", "エラー", "スキップ"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", action="store_true", help="印刷用PDFも作成する")
    args = parser.parse_args()
    complete = build()
    if args.pdf:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
            page = browser.new_page()
            page.goto((OUT / "test-report.html").as_uri())
            page.evaluate("""async () => {
                const firstSection = document.querySelector("#screens");
                firstSection.before(document.querySelector("#cases"));
                document.querySelectorAll('details').forEach(d => d.open = true);
                for (const img of document.images) img.loading = 'eager';
                await Promise.all(Array.from(document.images, img => img.decode()));
                await document.fonts.ready;
            }""")
            page.pdf(
                path=OUT / "test-report.pdf",
                format="A4",
                print_background=True,
                margin={"top": "12mm", "bottom": "12mm", "left": "13mm", "right": "13mm"},
            )
            browser.close()
    raise SystemExit(0 if complete else 1)
