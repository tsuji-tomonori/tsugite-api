"""Build a standalone Japanese report from the JUnit results and actual browser captures."""

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

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts"
CASE = {
    "test_persistence_has_no_http_dependencies": "DB層はHTTPのルーターに依存しない",
    "test_published_operations_have_stable_ids": "公開操作のOpenAPI IDと実装が対応する",
    "test_user_flow": "デモの提供者と利用者が公開・申請・承認・実行・権限取消を画面で完了できる",
    "test_invalid_token[bad0]": "発行元が違うトークンを401で拒否する",
    "test_invalid_token[bad1]": "IDトークンをAPIの利用に使用すると401で拒否する",
    "test_invalid_token[bad2]": "登録されていないクライアントを401で拒否する",
    "test_invalid_token[bad3]": "期限切れのトークンを401で拒否する",
    "test_invalid_token[bad4]": "呼び出しスコープのないシステム用トークンを401で拒否する",
    "test_people_and_machines": "人とシステムを識別し、システムのポータル利用を拒否する",
    "test_lifecycle": "承認した環境だけで呼び出せ、取消後の拒否を監査できる",
    "test_reapply": "却下後に再申請でき、古い判断の再適用を拒否する",
    "test_registration_validation": "外部参照、環境違いの接続先、不正な仕様の登録を拒否する",
    "test_route_contract": "OpenAPIの固定パスを優先し、許可された操作だけを通す",
    "test_demo_disabled_on_lambda": "Lambdaではデモ用ログインを無効にする",
    "test_gateway_authorizer_rechecks_each_invocation": "権限を毎回照合し、取消後は同じトークンでも拒否する",
    "test_stack_deletion_preserves_database": "スタック削除イベントでDBを削除しない",
    "test_lambda_adapter": "接続確認の後、呼び出し情報をLambdaへ渡して応答を返す",
    "test_https_adapter": "クエリと認証情報を保持してHTTPSの接続先に転送する",
    "test_failed_probe_keeps_draft": "接続確認に失敗したAPIは下書きのまま残る",
    "test_schema_matches_models_and_replays": "DB定義がモデルと一致し、旧版のデータを移行できる",
    "test_access_boundaries": "非公開S3、呼び出しの認可、キャッシュと配信の設定が設計どおりである",
    "test_every_resource_has_ownership[sample]": "標準構成の全リソースでタグと管理情報を照合する",
    "test_every_resource_has_ownership[custom-project]": "独自プロジェクト構成でも全リソースの管理情報がそろう",
    "test_existing_resources_keep_their_logical_ids": "既存リソースの論理IDと分割後の所属が対応する",
    "test_cognito_browser": "Cognitoで識別した2人が画面で承認し、在庫照会・取消・監査まで進める",
    "test_approved_calls_reach_upstream[cognito-lambda]": "承認した利用者だけがLambdaの在庫を取得できる",
    "test_approved_calls_reach_upstream[machine-lambda]": "システムも承認した環境だけでLambdaを利用できる",
    "test_approved_calls_reach_upstream[cognito-https]": "HTTPS APIに接続用トークンが届き、取消後は呼び出しが届かない",
    "test_deployed_resources": "構築したS3・API Gateway・Lambdaのタグを取得し、在庫APIが商品を返す",
    "test_create_dsql_cluster": "DSQLクラスターが削除保護付きで稼働状態になる",
}
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


def result(case):
    for tag, label in (("error", "エラー"), ("failure", "失敗"), ("skipped", "スキップ")):
        if case.find(tag) is not None:
            return label
    return "成功"


def inventory():
    file = ROOT / "infra/cdk.out/TsugiteApi.template.json"
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


def build():
    counts = Counter()
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
            status = result(case)
            counts[status] += 1
            shots = []
            for prop in case.findall("./properties/property[@name='screenshot']"):
                path, caption = prop.attrib["value"].split("|", 1)
                image = (OUT / path).resolve()
                if not image.is_relative_to((OUT / "screenshots").resolve()) or not image.is_file():
                    missing.append(caption)
                    continue
                encoded = base64.b64encode(image.read_bytes()).decode()
                shots.append(
                    f"<figure><figcaption>{escape(caption)}</figcaption><img loading='lazy' alt='{escape(caption, quote=True)}' src='data:image/png;base64,{encoded}'></figure>"
                )
            if (
                status == "成功"
                and name in ("test_cognito_browser", "test_user_flow")
                and len(shots) < 9
            ):
                missing.append(title + "の画面記録")
            evidence = ""
            if shots:
                anchor = "images-" + str(len(galleries))
                evidence = f" · <a href='#{anchor}'>画面{len(shots)}枚</a>"
                label = "Cognitoの利用者で操作" if name == "test_cognito_browser" else "デモ利用者で操作"
                galleries.append(
                    f"<details id='{anchor}' {'open' if name == 'test_cognito_browser' else ''}><summary>{label}（{len(shots)}枚）</summary><div class='grid'>{''.join(shots)}</div></details>"
                )
            style = "ok" if status == "成功" else "bad"
            rows.append(
                f"<tr><td>{escape(CASE.get(name, name))}<small>{escape(name)}{evidence}</small></td><td class='status {style}'>{status}</td><td>{float(case.get('time', '0')):.2f} 秒</td></tr>"
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
    output = f"""<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>継手API テスト結果</title><style>{CSS}</style><main>
    <header><h1>継手API テスト結果</h1><p>{date} 開始 · 対象コミット <code>{escape(rev[:12])}</code></p>
    <p class="numbers">{summary}</p>{gaps}<nav><a href="#screens">画面の記録</a><a href="#cases">全テストケース</a><a href="#cdk">CDKのタグ</a></nav></header>
    <section id="screens"><h2>申請から利用・取消までの画面</h2>{"".join(reversed(galleries)) or "画面記録はありません。"}</section>
    <section id="cases"><h2>テストケースと実行結果</h2>{"".join(tables)}</section>
    <section id="cdk"><h2>CDKリソースのタグ</h2>{inventory()}</section>
    <section><h2>検証環境</h2><p>画面はChromiumで撮影しました。AWS操作には公式AWS Emulatorを使い、DSQLはクラスターの稼働までを確認します。業務データとDB移行にはSQLite、システム用トークンにはテスト用署名鍵を使います。実AWSへの配備、CloudFront経由の全経路、Cognitoのホスト型ログイン・MFA・OAuth発行は今回の検証範囲外です。</p></section></main></html>"""
    OUT.mkdir(exist_ok=True)
    (OUT / "test-report.html").write_text(output, encoding="utf-8")
    return not missing


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
