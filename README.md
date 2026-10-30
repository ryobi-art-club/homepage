# 凌美会ホームページ 公開サイト（homepage）

凌美会の公開サイト（<https://ryobi-art-club.github.io/homepage/>）を作るリポジトリです。管理画面で保存された内容（Google スプレッドシートと Drive）を読み、HTML を作って GitHub Pages で公開します。

**システム全体の説明・アカウント・運用・トラブルシュートは、管理画面のリポジトリ [homepage-cms の README](https://github.com/ryobi-art-club/homepage-cms) にまとめています。まずそちらを読んでください。** この資料は、公開サイトだけに関わることを書いています。

AI エージェントに作業を頼むときの決まりごとは [`AGENTS.md`](AGENTS.md) にあります。

## 目次

1. [サイトの作られ方](#1-サイトの作られ方)
2. [固定の文章や画像を変えるとき](#2-固定の文章や画像を変えるとき)
3. [デザインや動きを変えるとき](#3-デザインや動きを変えるとき)
4. [手元でのビルドと確認](#4-手元でのビルドと確認)
5. [GitHub Actions とシークレット](#5-github-actions-とシークレット)
6. [ページの構成と表示の決まり](#6-ページの構成と表示の決まり)
7. [定期的な点検](#7-定期的な点検)
8. [ファイルごとの詳細](#8-ファイルごとの詳細)
9. [一から作り直すときのセットアップ手順](#9-一から作り直すときのセットアップ手順)

---

## 1. サイトの作られ方

```
管理画面で「公開する」（または GitHub で手動実行）
    │
    ▼
GitHub Actions（.github/workflows/deploy.yml）
    │
    ├── ① scripts/fetch_google_content.py
    │       スプレッドシート（_PublishedState と ChangeLog）→ build/runtime/content_snapshot.json
    │       Drive の画像 → build/runtime/assets/
    │       （サービスアカウントで、読み取り専用で読む）
    │
    ├── ② scripts/build_site.py
    │       src/site_static.json（固定の文章）＋ ①の結果
    │       → dist/（index.html、CSS、JS、画像、sitemap.xml）
    │
    └── ③ GitHub Pages に公開
```

- **サイトは自動では作り直されません。** このリポジトリに push しただけでは反映されず、管理画面の「公開する」か、GitHub の「Actions」→「Build and Deploy Ryobi Site」→「Run workflow」で作り直します。
- ページは `index.html` の1枚だけで、タブの切り替えなどは `site.js` で行います。

---

## 2. 固定の文章や画像を変えるとき

管理画面で編集できないもの（紹介文、活動場所、年間スケジュール、画材、連絡先、SNS など）は、`src/site_static.json` を直接編集します。編集したら commit・push し、上の方法でサイトを作り直してください。

| 内容 | 編集する場所 |
|---|---|
| 展示会・活動記録・新歓カレンダー・ご依頼事例 | 管理画面（このリポジトリでは編集しない） |
| 部の名前、トップの見出し、紹介文 | `site_static.json` の `club_name_jp`、`hero_…`、`intro_text` など |
| 各タブの説明文 | `site_static.json` の `exhibitions_static.summary` など |
| 入部希望の方：基本情報・画材・年間スケジュール | `site_static.json` の `recruit_static` |
| ご依頼の方：連絡先 | `site_static.json` の `requests_static` |
| SNS のリンク、コピーライト | `site_static.json` の `social_links`、`copyright` |
| ロゴ、部室の写真 | `src/logo.png`、`src/clubroom.jpg` |
| デザイン・動き | `src/stylesheet.css`、`src/site.js`、`scripts/build_site.py`（[3](#3-デザインや動きを変えるとき)） |

### `site_static.json` の項目

| 項目 | 内容 |
|---|---|
| `club_name_jp` / `club_name_en` | 部の名前（日本語・英語） |
| `hero_kicker` / `hero_title` / `hero_subtitle` | トップの小見出し・見出し・説明 |
| `og_url` | サイトの正式な URL（SNS で共有したときの表示、検索エンジン向けの情報、sitemap に使う） |
| `og_image` | SNS で共有したときの画像（`logo.png` または URL） |
| `intro_text` | 紹介文 |
| `information_text` | INFORMATION の説明文 |
| `exhibitions_static.summary` / `activities_static.summary` | 展示会・活動記録タブの説明文 |
| `recruit_static` | 入部希望の方タブ。`headline`（見出し）、`summary`（説明）、`info_points`（基本情報）、`materials`（画材・道具）、`annual_schedule`（年間スケジュール） |
| `requests_static` | ご依頼の方タブ。`summary`、`contact_email`、`contact_instagram`、`contact_x` |
| `social_links` | `instagram` / `x` / `email` |
| `copyright` | フッターの著作権表示 |

**`recruit_static` の中身**

- `info_points`：`label`（項目名）と `text`（内容）の並び。写真を付けるときは `image`（`src/` に置いたファイル名）、地図などへのリンクを付けるときは `link`（`url` と `label`）を足す。
- `materials`：`name`（画材の名前）と `note`（説明）の並び。
- `annual_schedule`：`period`（時期）、`label`（内容）、`accent`（色：`yellow` / `blue` / `green` / `white`）の並び。

**文章の中のリンク**：`hero_subtitle`、`intro_text`、`information_text`、各タブの `summary`、`info_points` の `text` では、`[表示する文字](https://example.com)` と書くとリンクになります。

### 写真を増やすときの注意

`src/` の画像は、ビルドの最後に `build_site.py` の `main()` が**ファイル名を指定して** `dist/` にコピーしています（`logo.png`、`clubroom.jpg`）。写真を増やしたら、ここにもコピーの行を足してください。足さないと、サイトで画像が表示されません。

---

## 3. デザインや動きを変えるとき

- HTML は `scripts/build_site.py` が Python で組み立てています（テンプレートの仕組みは使っていません）。
- 見た目は `src/stylesheet.css`、動き（タブ、写真の拡大表示、スライド）は `src/site.js` です。外部のライブラリは使っていません（アイコンだけ Font Awesome を読み込んでいます）。
- 管理画面の右側の「プレビュー」は、このサイトの見た目をまねて作っています（homepage-cms の `UiStyles.html` の「サイトプレビュー」の部分）。サイトの見た目を変えたら、管理画面のプレビューも合わせて直すと、部員が公開前に確認しやすくなります。
- 変えたら、手元でビルドして確認します（[4](#4-手元でのビルドと確認)）。

---

## 4. 手元でのビルドと確認

手元でビルドするには、サービスアカウントの鍵（JSON）が必要です。鍵は管理者から受け取り、**リポジトリの外**に置いてください（`.gitignore` で `*service-account*.json` などを除外していますが、念のため）。

```bash
cd homepage
pip install -r requirements.txt

# ① 内容と画像を取得
python scripts/fetch_google_content.py \
  --service-account-json <鍵ファイルのパス> \
  --content-spreadsheet-id <コンテンツ用スプレッドシートの ID> \
  --output-json build/runtime/content_snapshot.json \
  --assets-dir build/runtime/assets   --cache-dir build/cache/drive    # 省略できる。付けると、2回目から変わった画像だけを取得する

# ② HTML を作る
python scripts/build_site.py \
  --static-config src/site_static.json \
  --content-snapshot build/runtime/content_snapshot.json \
  --assets-root build/runtime/assets \
  --output-dir dist

# ③ 確認（ブラウザで http://localhost:8000 を開く）
cd dist
python -m http.server 8000
```

`build/` と `dist/` は Git に入りません。

---

## 5. GitHub Actions とシークレット

ワークフロー（`.github/workflows/deploy.yml`）は `workflow_dispatch`（手動または管理画面からの起動）だけで動きます。

| ジョブ | 内容 |
|---|---|
| `build` | Python の準備 → 前回の画像のキャッシュを戻す → 内容の取得 → HTML を作る → GitHub Pages 用にまとめる → 画像のキャッシュを保存し、古いキャッシュを消す |
| `deploy` | GitHub Pages に公開する |

### 画像のキャッシュ

ビルドで一番時間がかかるのは、Drive からの画像の取得です（2026年10月の時点で、3分のうち2分40秒）。画像は展示会ごとに増え続けるので、前回のビルドで取得した画像を GitHub Actions のキャッシュ（`drive-images-…`）に取っておき、**新しい画像と、Drive で中身が変わった画像だけ**を取得します（Drive のチェックサム `md5Checksum` で判定）。取得は8枚ずつ同時に行い、ファイルの情報は100件ずつまとめて問い合わせます。

- **キャッシュには、今のサイトに載っている画像だけを入れます。** 公開リポジトリのキャッシュは、プルリクエストを作れる人（GitHub のアカウントがあれば誰でも）なら中身を読めるためです（[GitHub の説明](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)）。取得の最後に、サイトに使わなかった画像をキャッシュから消し（`prune_cache`）、保存したあとで前回までのキャッシュを消します。非公開にした・削除した画像は、次のビルドでキャッシュからなくなります。
- **すぐに消したいとき**（作品を消してほしいと頼まれたときなど）：管理画面で非公開にして公開したあと、GitHub の「Actions」→ 左のメニューの「Caches」で `drive-images-` のキャッシュを消してください。消しても、次のビルドが画像を全部取得し直すだけで、困ることはありません。古いキャッシュを消す手順が失敗した場合も、使われないキャッシュは7日で GitHub が消します。
- ビルドの記録（ログ）には、`Images: 120 used, 3 downloaded, 117 from cache, 2 removed from cache` のように、取得した枚数だけが出ます。
- 完成したサイト一式（Pages 用にまとめたもの）も、GitHub に1日だけ残ります。中身は公開したサイトそのものです。

リポジトリの「Settings」→「Secrets and variables」→「Actions」に、次のシークレットが必要です。

| 名前 | 内容 |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | サービスアカウントの鍵（JSON ファイルの中身をそのまま貼る） |
| `CONTENT_SPREADSHEET_ID` | コンテンツ用スプレッドシートの ID |

サービスアカウントは、スプレッドシートと Drive を**読み取り専用**で使います。コンテンツ用スプレッドシートと、Drive の4つのルートフォルダを、サービスアカウントのメールアドレス（`…@….iam.gserviceaccount.com`）に「閲覧者」で共有しておく必要があります。

---

## 6. ページの構成と表示の決まり

```
ナビゲーション（ロゴ、ABOUT / INFO へのリンク、SNS）
トップ（#home）
ABOUT（#about）：紹介文と更新履歴（UPDATE LOG）
INFORMATION（#info-tabs）：タブで切り替え
  ├── 展示会：開催予定 → 直近の展示（作品一覧つき）→ 過去の展示
  ├── 活動記録・告知
  ├── 入部希望の方：基本情報、画材、年間スケジュール、新歓カレンダー
  └── ご依頼の方：連絡先、過去の取り組み事例
フッター
```

- **展示会の住所**は Google マップを開くリンクにしています（会場名と住所で検索）。下線は住所の文字にだけ引き、地図のアイコンには引きません。地図の埋め込みはしていません（理由は homepage-cms の README の「設計の判断メモ」）。
- **会期**は、管理画面が開始日・終了日から作った表示（`date_line`）をそのまま出します。
- **作品一覧**は、登録した順に行ごとに並べ、1行の高さをそろえて、幅を画像の縦横比に合わせます（`render_work_gallery` と CSS の `.work-gallery`）。
- **記事や事例の写真**は最大10枚まで使い、4枚まで並べて、それ以上は「+N」と表示します。押すと拡大表示（ライトボックス）になります。
- **新歓カレンダー・DM** はスライド表示です。新歓カレンダーは10枚まで出します。枠の縦横比は、横長の画面（パソコンなど）ではいちばん横長の画像に、縦長の画面（スマホなど）ではいちばん縦長の画像に合わせます（16:9〜4:5）。横長の画面では大きさが画面の高さで、縦長の画面では画面の幅で決まるので、こうするとどの画像も切れずに、いちばん大きく表示されます。パワーポイントの横長の画像も、Instagram 用の正方形・縦長の画像も使えます。DM は、画面の高さに収まる大きさにします。
- **更新履歴**は、今も公開中の項目に関係するものだけを表示します。
- **検索エンジン向け**：タイトル、説明、SNS で共有したときの表示、`sitemap.xml` を自動で作ります。`src/verification/` の HTML は Google Search Console の所有確認用で、そのまま公開されます。

---

## 7. 定期的な点検

| 項目 | 確認すること |
|---|---|
| Python のライブラリ | `requirements.txt` は大きな版上げで壊れないよう上限（`<3` など）を付けています。上限を上げるときは、手元でビルドして確かめてから |
| GitHub Actions の部品 | 実行結果に古い版の警告が出たら、`deploy.yml` の `actions/checkout@v5` などを上げる |
| Font Awesome | `build_site.py` で 6.4.2 を読み込んでいる |
| サービスアカウントの鍵 | 使えなくなったら新しい鍵を作り、シークレット `GOOGLE_SERVICE_ACCOUNT_JSON` を入れ替える |

---

## 8. ファイルごとの詳細

```
homepage/
├── requirements.txt              Python のライブラリ
├── .github/workflows/deploy.yml  ビルドと公開のワークフロー
├── scripts/
│   ├── fetch_google_content.py   スプレッドシート・Drive → JSON と画像
│   └── build_site.py             JSON → HTML
└── src/
    ├── site_static.json          固定の文章
    ├── stylesheet.css            見た目
    ├── site.js                   動き
    ├── logo.png / clubroom.jpg   画像
    └── verification/             Google Search Console の所有確認ファイル
```

### `scripts/fetch_google_content.py`

| 関数 | 役割 |
|---|---|
| `build_clients()` | サービスアカウントの鍵から、スプレッドシートと Drive を読む準備をする（読み取り専用） |
| `DriveFiles` | Drive の読み取り。ファイルの情報をまとめて問い合わせ（`prefetch_meta`）、画像を同時に取得し（`download`・`finish`）、キャッシュを整理する（`prune_cache`） |
| `referenced_file_ids()` | シートの行が指している画像のファイル ID を集める（情報をまとめて問い合わせるため） |
| `get_sheet_rows()` | シートの各行を、1行目の見出しを名前にして読む |
| `normalize_recruit_calendar()` | 公開中の新歓カレンダーと画像 |
| `normalize_activity_articles()` | 公開中の活動記録と画像 |
| `normalize_exhibitions()` | 公開中の展示会を開催予定とアーカイブに分け、DM・作品の画像を取得 |
| `normalize_requests()` | 公開中のご依頼事例と画像 |
| `normalize_change_log()` | 更新履歴 |
| `download_ordered_images_by_ids()` | 管理画面で並べた順（`media_file_ids`）に画像を取得 |
| `download_folder_images()` | 並び順の情報がないときに、フォルダの画像をまとめて取得 |
| `read_published_payload()` | `_PublishedState` から公開中の内容を読む（分けて書かれたセルをつなぎ直す） |
| `tables_from_published()` | 読んだ内容を、以前の内容のシートの行と同じ形にする |

読むシートは `_PublishedState` と `ChangeLog` です（各シートの列は homepage-cms の README の「スプレッドシートの構成」）。

- **内容は `_PublishedState` から読みます**（`read_published_payload`）。管理画面が公開のたびに、公開した内容全体を JSON で書くシートです。1つのセルに入りきらないとき（45,000文字超）は、管理画面が20,000文字ずつ横の列（`payload_json_2`…）に分けて書き、`payload_json` には `{"storage_format": "chunked-json-v1", "chunk_count": n}` を書きます。読むときにつなぎ直します。
- 読んだ内容は `tables_from_published` で、以前の内容のシート（`Recruit`・`ActivityArticles`・`Exhibitions`・`RequestCases`）の行と同じ形に直し、`normalize_…` の関数に渡します。
- `_PublishedState` がない・読めないときは、以前の内容のシートから読みます（ビルドの記録に `Content: content sheets` と出ます）。管理画面がまだ以前の版のときや、移行の途中のための逃げ道です。
- 2026年10月に、同じ内容から両方の読み方で作ったサイトのデータが一致することを、本番のデータで確かめました。

### `scripts/build_site.py`

| 関数 | 役割 |
|---|---|
| `render_page()` | ページ全体を組み立てる |
| `build_seo_context()` / `render_sitemap_xml()` | 検索エンジン向けの情報と sitemap |
| `render_update_log()` | 更新履歴 |
| `render_exhibition_upcoming()` / `render_exhibition_recent()` / `render_exhibition_archive()` | 展示会（開催予定・直近・過去） |
| `render_exhibition_meta()` / `render_venue_address()` | 展示会の会期と会場。住所を Google マップへのリンクにする |
| `render_work_gallery()` | 作品一覧 |
| `render_activity_cards()` / `render_request_cards()` | 活動記録・ご依頼事例 |
| `render_image_grid()` / `render_carousel()` / `render_recruit_calendar()` | 写真の並べ方・スライド |
| `render_timeline()` / `render_info_points()` | 年間スケジュール・入部の基本情報 |
| `image_aspect()` | 画像の縦横比を読む（並べ方の調整に使う） |
| `main()` | 全体の流れ。最後に `src/` のファイルを `dist/` にコピーする（[写真を増やすときの注意](#写真を増やすときの注意)） |

---

## 9. 一から作り直すときのセットアップ手順

1. **Google Cloud でサービスアカウントを作る**：[Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作り、「Google Sheets API」と「Google Drive API」を有効にする。サービスアカウントを作り、鍵（JSON）を作ってダウンロードする。
2. **共有する**：コンテンツ用スプレッドシートと Drive の4つのルートフォルダを、サービスアカウントのメールアドレスに「閲覧者」で共有する。
3. **GitHub Pages を有効にする**：リポジトリの「Settings」→「Pages」で、Source を「GitHub Actions」にする。
4. **シークレットを登録する**（[5](#5-github-actions-とシークレット)）。
5. **管理画面から動かしてみる**：管理画面で「公開する」を押し、Actions が成功してサイトが表示されるか確かめる。
