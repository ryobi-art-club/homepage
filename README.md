# homepage — 開発者向けドキュメント

凌美会公式ホームページの**静的サイトジェネレーター**です。  
Google スプレッドシートのデータと Google Drive の画像を取得して、静的 HTML ファイルを生成し GitHub Pages で公開します。

---

## 目次

1. [システム全体の流れ](#1-システム全体の流れ)
2. [ファイル構成](#2-ファイル構成)
3. [各ファイルの詳細](#3-各ファイルの詳細)
4. [ビルドパイプライン詳細](#4-ビルドパイプライン詳細)
5. [静的コンテンツの管理](#5-静的コンテンツの管理)
6. [セットアップ手順](#6-セットアップ手順)
7. [ローカルビルド手順](#7-ローカルビルド手順)
8. [GitHub Actions のシークレット設定](#8-github-actions-のシークレット設定)
9. [ページ構成・UI 仕様](#9-ページ構成ui-仕様)

---

## 1. システム全体の流れ

```
GitHub Actions（workflow_dispatch で起動）
    │
    ├── Step 1: fetch_google_content.py
    │         Google スプレッドシート → content_snapshot.json
    │         Google Drive → assets/ （画像ダウンロード）
    │
    └── Step 2: build_site.py
              site_static.json + content_snapshot.json + assets/
              → dist/ （index.html, stylesheet.css, site.js, logo.png, assets/, sitemap.xml）
                   │
                   └── GitHub Pages へ自動デプロイ
```

ビルドの起動は **homepage-cms の「公開する」ボタン** からトリガーされます（GitHub Actions の `workflow_dispatch` API 経由）。

---

## 2. ファイル構成

```
homepage/
├── requirements.txt              Python 依存パッケージ
├── .github/
│   └── workflows/
│       └── deploy.yml            GitHub Actions ワークフロー定義
│
└── scripts/
│   ├── fetch_google_content.py   Step 1: Sheets/Drive → JSON スナップショット
│   └── build_site.py             Step 2: JSON → 静的 HTML ビルド
│
└── src/
    ├── site_static.json          静的コンテンツ設定（クラブ情報・固定テキスト）
    ├── stylesheet.css            サイトのスタイルシート
    ├── site.js                   フロントエンド JavaScript
    ├── logo.png                  クラブロゴ
    └── verification/
        ├── google0b9354aae6210dec.html  Google Search Console 認証ファイル
        └── google6b8499ef8e62e774.html  同上
```

---

## 3. 各ファイルの詳細

### `scripts/fetch_google_content.py` — コンテンツ取得

Google APIs から情報を取得し、後続の HTML ビルドが使いやすいフォーマット（JSON + ローカル画像ファイル）に変換します。

**主な処理：**

| 関数 | 役割 |
|------|------|
| `build_clients()` | サービスアカウント JSON から Sheets / Drive クライアントを構築 |
| `get_sheet_rows()` | 指定シートの全行をヘッダー付き辞書リストとして取得 |
| `normalize_recruit_calendar()` | `Recruit` シートから公開中の新歓カレンダーを取得し画像ダウンロード |
| `normalize_activity_articles()` | `ActivityArticles` シートから公開記事を取得し画像ダウンロード |
| `normalize_exhibitions()` | `Exhibitions` シートから展示会データを upcoming/archive に分類し画像ダウンロード |
| `normalize_requests()` | `RequestCases` シートから依頼事例を取得し画像ダウンロード |
| `normalize_change_log()` | `ChangeLog` シートの更新履歴を取得 |
| `download_ordered_images_by_ids()` | `media_file_ids` の ID 順で画像をダウンロード（順番制御付き）|
| `download_folder_images()` | フォルダ内の全画像をダウンロード（フォールバック）|

**画像ダウンロード戦略：**
1. まず `media_file_ids` の ID リストが存在すれば、その順番でダウンロード（管理画面で並び順が制御できる）
2. なければ Drive フォルダ内の全画像をファイル名順でダウンロード

**出力フォーマット（`content_snapshot.json`）：**

```json
{
  "meta": { "generated_at": "2026-05-16T..." },
  "recruit_calendar": {
    "label": "2026年度 新歓イベントカレンダー",
    "year": "2026",
    "images": ["assets/recruit/01-calendar.jpg"]
  },
  "activities": [
    {
      "id": "activity-xxxx",
      "title": "記事タイトル",
      "body": "本文",
      "category": "record",
      "created_at": "2026-05-01T...",
      "images": ["assets/activities/activity-xxxx/01-image.jpg"]
    }
  ],
  "exhibitions": {
    "upcoming": [...],
    "archive": [...]
  },
  "requests": [...],
  "change_log": [
    { "timestamp": "2026-05-16T...", "summary": "展示会「〇〇展」の情報を公開" }
  ]
}
```

**取得するシート一覧：**

| シート名 | スプレッドシート上の範囲 |
|---------|------------------------|
| `Recruit` | `Recruit!A1:Z2000` |
| `ActivityArticles` | `ActivityArticles!A1:Z2000` |
| `Exhibitions` | `Exhibitions!A1:Z2000` |
| `RequestCases` | `RequestCases!A1:Z2000` |
| `ChangeLog` | `ChangeLog!A1:Z2000` |

---

### `scripts/build_site.py` — 静的サイトビルド

`content_snapshot.json` と `site_static.json` を読み込み、単一の `index.html` を生成します。  
外部テンプレートエンジンは使わず、Python の f-string で HTML を直接組み立てます。

**主な関数：**

| 関数 | 役割 |
|------|------|
| `render_page()` | ページ全体の HTML を生成するメイン関数 |
| `build_seo_context()` | OGP / Twitter Card / JSON-LD / canonical URL などの SEO メタ情報を構築 |
| `render_sitemap_xml()` | `sitemap.xml` を生成 |
| `render_update_log()` | 更新履歴のリスト HTML を生成。公開中コンテンツに紐づくエントリのみ表示 |
| `render_exhibition_upcoming()` | 開催予定展示会のカードを生成（NEXT EXHIBITION / UPCOMING バッジ付き）|
| `render_exhibition_recent()` | 最新アーカイブ展示会のカード（作品ギャラリー付き）を生成 |
| `render_exhibition_archive()` | 過去の展示会アーカイブリストを生成 |
| `render_activity_cards()` | 活動記事カードを生成 |
| `render_request_cards()` | ご依頼事例カードを生成 |
| `render_carousel()` | 画像カルーセルの HTML を生成（新歓カレンダー・DM 画像用）|
| `render_image_grid()` | 画像グリッド（最大 4 枚表示 + ライトボックス）を生成 |
| `render_work_gallery()` | 展示作品ギャラリーを 2 列バランスレイアウトで生成 |
| `render_recruit_calendar()` | 新歓カレンダーのカルーセルを生成 |
| `render_timeline()` | 年間スケジュールのタイムラインを生成 |
| `render_info_points()` | 部活情報（活動場所・頻度など）を生成 |
| `image_aspect()` | 画像の縦横比を PNG/JPEG/SVG ヘッダーから取得（レイアウト最適化用）|

**作品ギャラリーのレイアウトアルゴリズム（`render_work_gallery`）：**  
縦横比が 2:1 以上のパノラマ作品は全幅で表示し、残りの作品を 2 列に高さバランスよく振り分けます。作品数が 18 枚以下の場合は全パターンを探索して最適な分割を選択、それを超える場合は LPT アルゴリズム（Longest Processing Time）にフォールバックします。

**更新履歴の表示ロジック（`render_update_log`）：**  
変更ログのエントリのうち、現在公開中のコンテンツ（記事・展示会・依頼事例）のタイトルに紐づくものだけを表示します。削除済みのコンテンツに関するログは自動的に非表示になります。

**ビルド出力ファイル：**

```
dist/
├── index.html        サイト本体
├── stylesheet.css    スタイルシート（src/ からコピー）
├── site.js           フロントエンド JS（src/ からコピー）
├── logo.png          ロゴ（src/ からコピー）
├── sitemap.xml       サイトマップ（og_url が設定されている場合のみ生成）
├── google....html    Search Console 認証ファイル（src/verification/ からコピー）
└── assets/           ダウンロードされた画像
    ├── recruit/
    ├── activities/
    ├── exhibitions/
    └── requests/
```

---

### `src/site_static.json` — 静的コンテンツ設定

スプレッドシートではなく、直接 JSON を編集して更新するコンテンツです。  
変更後は Git にコミット・push してください（GitHub Actions の次回実行時に反映されます）。

**フィールド一覧：**

| フィールド | 説明 |
|-----------|------|
| `club_name_jp` | クラブ名（日本語）|
| `club_name_en` | クラブ名（英語）|
| `hero_kicker` | ヒーロー画像のキャッチフレーズ（英語）|
| `hero_title` | ヒーロー画像のメインタイトル |
| `hero_subtitle` | ヒーロー画像のサブタイトル |
| `og_url` | サイトの正規 URL（OGP・canonical・sitemap に使用）|
| `og_image` | OGP 画像のパス（`logo.png` または絶対 URL）|
| `intro_text` | About セクションの紹介文 |
| `information_text` | INFO セクション全体のリード文 |
| `exhibitions_static` | 展示会タブの固定コンテンツ（後述）|
| `activities_static` | 活動記録・告知タブの固定コンテンツ（後述）|
| `recruit_static` | 入部希望ページの固定コンテンツ（後述）|
| `requests_static` | ご依頼ページの固定コンテンツ（後述）|
| `social_links` | Instagram / X / Email のリンク |
| `copyright` | フッターのコピーライト文字列 |

**固定文内リンク：**

本文系の固定文では、次の形式でリンクを埋め込めます。

```text
[表示テキスト](https://example.com)
```

対象は `hero_subtitle`, `intro_text`, `information_text`, `exhibitions_static.summary`, `activities_static.summary`, `recruit_static.summary`, `recruit_static.info_points[].text`, `requests_static.summary` です。タイトル、SEO メタ情報、OGP、alt、SNS URL、メールアドレスには適用しません。

**`exhibitions_static` の詳細：**

| フィールド | 説明 |
|-----------|------|
| `summary` | 展示会タブのリード文 |

**`activities_static` の詳細：**

| フィールド | 説明 |
|-----------|------|
| `summary` | 活動記録・告知タブのリード文 |

**`recruit_static` の詳細：**

| フィールド | 説明 |
|-----------|------|
| `headline` | セクション見出し |
| `summary` | リード文 |
| `info_points` | 基本情報リスト（`label` + `text`の配列）|
| `materials` | 使用可能な材料・道具のリスト |
| `annual_schedule` | 年間スケジュール（`period` + `label` + `accent` の配列）|

`annual_schedule` の `accent` には `yellow` / `blue` / `green` / `white` が指定可能です。

**`requests_static` の詳細：**

| フィールド | 説明 |
|-----------|------|
| `summary` | リード文 |
| `contact_email` | 問い合わせメールアドレス |
| `contact_instagram` | Instagram アカウント名 |
| `contact_x` | X（旧 Twitter）アカウント名 |

---

### `src/site.js` — フロントエンド JavaScript

**機能：**

| 機能 | 実装 |
|------|------|
| タブ切替 | `[data-tab-shell]` / `[data-tab-target]` / `[data-tab-panel]` 属性で制御 |
| ライトボックス | 画像クリックでオーバーレイ表示。ドラッグ・矢印キー・ESC キー対応 |
| 画像カルーセル | スワイプ・ドラッグ対応のスライダー。カルーセル内画像をクリックするとライトボックスが開く |
| 画像グリッドのレイアウト調整 | プライマリ画像の縦横比を `naturalWidth/Height` で取得し CSS クラスを付与 |

外部ライブラリは使用せず、バニラ JavaScript のみです。

---

### `src/stylesheet.css` — スタイルシート

CSS 変数（カスタムプロパティ）ベースのデザインシステムです。  
カラーパレット・タイポグラフィ・レスポンシブ対応はすべてここで定義されています。

---

### `.github/workflows/deploy.yml` — GitHub Actions ワークフロー

`workflow_dispatch` イベントのみで起動（スケジュール起動なし）。  
手動実行または homepage-cms の公開ボタンからトリガーされます。

**ジョブ構成：**

| ジョブ | 処理内容 |
|--------|---------|
| `build` | Python 環境構築 → コンテンツ取得 → 静的サイトビルド → Pages artifact としてアップロード |
| `deploy` | `build` の完了を待って GitHub Pages にデプロイ |

**使用するシークレット：**

| シークレット名 | 説明 |
|--------------|------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google API 認証用サービスアカウントの JSON キー（Drive・Sheets の読み取り権限が必要）|
| `CONTENT_SPREADSHEET_ID` | コンテンツ用スプレッドシートの ID |

---

## 4. ビルドパイプライン詳細

```
GitHub Actions が起動
    │
    ▼
python fetch_google_content.py
  --service-account-json /tmp/service-account.json
  --content-spreadsheet-id {CONTENT_SPREADSHEET_ID}
  --output-json build/runtime/content_snapshot.json
  --assets-dir build/runtime/assets
    │
    │ ① Sheets API でコンテンツデータ取得
    │ ② Drive API で画像ファイルをダウンロード
    │   build/runtime/assets/
    │     ├── recruit/
    │     ├── activities/{article_id}/
    │     ├── exhibitions/{exhibition_id}/
    │     └── requests/{case_id}/
    │ ③ content_snapshot.json を出力
    │
    ▼
python build_site.py
  --static-config src/site_static.json
  --content-snapshot build/runtime/content_snapshot.json
  --assets-root build/runtime/assets
  --output-dir dist
    │
    │ ① site_static.json + content_snapshot.json を読み込み
    │ ② index.html を生成（Python f-string による HTML 組み立て）
    │ ③ sitemap.xml を生成
    │ ④ 静的ファイルを dist/ にコピー（CSS/JS/ロゴ/認証ファイル）
    │ ⑤ assets/ を dist/assets/ にコピー
    │
    ▼
GitHub Pages にデプロイ
```

---

## 5. 静的コンテンツの管理

スプレッドシートで管理するコンテンツと、`site_static.json` で管理するコンテンツがあります。

| コンテンツ | 管理方法 |
|-----------|---------|
| 展示会情報 | スプレッドシート（CMS で更新）|
| 活動記事 | スプレッドシート（CMS で更新）|
| 新歓カレンダー | スプレッドシート + Drive（CMS で更新）|
| ご依頼事例 | スプレッドシート（CMS で更新）|
| クラブ名・紹介文 | `site_static.json`（Git 編集 + push）|
| 入部情報（場所・スケジュール等）| `site_static.json`（Git 編集 + push）|
| 連絡先・SNS リンク | `site_static.json`（Git 編集 + push）|
| コピーライト | `site_static.json`（Git 編集 + push）|
| ロゴ画像 | `src/logo.png`（Git 編集 + push）|
| CSS・JavaScript | `src/`（Git 編集 + push）|

`site_static.json` の変更は CMS の公開ボタンを押さなくても、GitHub Actions を手動で実行するだけで反映されます。

---

## 6. セットアップ手順

### 前提条件
- Python 3.12 以上
- Google Cloud プロジェクト（サービスアカウントを作成できる権限）
- GitHub リポジトリ（GitHub Pages が有効）

### Step 1: Google サービスアカウントの作成

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成（または既存のものを使用）
2. 「API とサービス」→「ライブラリ」で以下の API を有効化：
   - **Google Sheets API**
   - **Google Drive API**
3. 「IAM と管理」→「サービスアカウント」でサービスアカウントを作成
4. キーを作成（JSON 形式）し、ダウンロード

### Step 2: スプレッドシートへのアクセス権付与

コンテンツ用スプレッドシートをサービスアカウントのメールアドレスと共有します（**閲覧者**権限で OK）。  
サービスアカウントのメールアドレスは `{アカウント名}@{プロジェクト}.iam.gserviceaccount.com` の形式です。

展示会の公開フォルダ（アーカイブ）も閲覧できるよう、Drive フォルダにも同様に共有します。

### Step 3: GitHub リポジトリの設定

1. **GitHub Pages の有効化**：リポジトリの「Settings」→「Pages」で Source を「GitHub Actions」に設定
2. **シークレットの設定**（次節参照）

### Step 4: ローカル開発環境の構築

```bash
cd homepage
pip install -r requirements.txt
```

---

## 7. ローカルビルド手順

ローカルで全ビルドを実行する場合：

```bash
cd homepage

# Step 1: コンテンツ取得
python scripts/fetch_google_content.py \
  --service-account-json /path/to/service-account.json \
  --content-spreadsheet-id YOUR_SPREADSHEET_ID \
  --output-json build/runtime/content_snapshot.json \
  --assets-dir build/runtime/assets

# Step 2: 静的サイトビルド
python scripts/build_site.py \
  --static-config src/site_static.json \
  --content-snapshot build/runtime/content_snapshot.json \
  --assets-root build/runtime/assets \
  --output-dir dist
```

ビルド後、`dist/index.html` をブラウザで開いて確認できます。  
（ただし相対パスで参照しているため、`python -m http.server` などのローカルサーバーで確認することを推奨）

```bash
cd dist
python -m http.server 8000
# ブラウザで http://localhost:8000 を開く
```

---

## 8. GitHub Actions のシークレット設定

リポジトリの「Settings」→「Secrets and variables」→「Actions」→「New repository secret」で以下を追加します。

| シークレット名 | 内容 |
|--------------|------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | サービスアカウントの JSON キーファイルの中身をそのまま貼り付ける |
| `CONTENT_SPREADSHEET_ID` | コンテンツ用スプレッドシートの ID（URL の `/d/` 以降）|

---

## 9. ページ構成・UI 仕様

### ページ構成（1 ページ完結の SPA 風構成）

```
ナビゲーションバー（グローバルナビ）
    ├── ロゴ + クラブ名
    ├── ABOUT / INFO へのアンカーリンク
    └── SNS リンク（Instagram / X / Email）

ヒーローセクション（#home）
    └── ロゴ・キャッチフレーズ・タイトル

ABOUT セクション（#about）
    └── 更新履歴ログ（UPDATE LOG）

INFORMATION セクション（#info-tabs）
    タブ切り替え
    ├── 展覧会タブ
    │   ├── 開催予定展示会（upcoming）
    │   ├── 最新アーカイブ展示会（作品ギャラリー付き）
    │   └── 過去の展示会アーカイブリスト
    ├── 活動記録・告知タブ
    ├── 入部希望の方タブ
    │   ├── 基本情報（活動場所・頻度等）
    │   ├── 使用材料リスト
    │   ├── 年間スケジュール（タイムライン）
    │   └── 新歓イベントカレンダー（カルーセル）
    └── ご依頼の方タブ
        ├── 連絡先情報
        └── 過去の取り組み事例

フッター
    └── コピーライト
```

### レスポンシブ対応

CSS の `clamp()` と メディアクエリでモバイル・タブレット・PC に対応しています。  
特定のブレークポイント（例：768px, 1024px など）は `stylesheet.css` 内で定義されています。

### 画像表示コンポーネント

| コンポーネント | 用途 |
|--------------|------|
| カルーセル | 新歓カレンダー・DM 画像（スワイプ対応、ドット付き）|
| 画像グリッド | 活動記事・依頼事例の写真（最大 4 枚表示、5 枚目以降は +N バッジ）|
| ライトボックス | 全画像共通（クリックで全画面表示、前後移動、キーボード操作対応）|
| 作品ギャラリー | 展示会作品（縦横比に応じた 2 列バランスレイアウト）|

### SEO・OGP 設定

- `<title>`、`<meta name="description">`、`<link rel="canonical">` を自動生成
- OGP（`og:title`, `og:image` 等）・Twitter Card メタタグを生成
- `schema.org` の `Organization` / `WebSite` の JSON-LD を埋め込み
- `sitemap.xml` を生成（`og_url` が設定されている場合）
- `lastmod` は `ChangeLog` シートの最新エントリのタイムスタンプを使用

### Google Search Console 認証

`src/verification/` 内の HTML ファイルが `dist/` のルートにコピーされ、  
Google Search Console でのサイト所有権確認に使用されます。  
新たに認証ファイルが必要になった場合はこのディレクトリに追加してください。
