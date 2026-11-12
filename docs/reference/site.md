# 公開サイトの仕組み

公開サイト（リポジトリの直下）のページの決まり・ビルドのワークフロー・ファイルと関数を調べるときに読みます。公開サイトのファイルは、リポジトリの直下（`scripts/`・`src/` など）にあります。作られ方の全体は [README の「公開サイトの作られ方」](../../README.md#公開サイトの作られ方)。見た目を変える手順は [コードを直して反映する手順](../development.md#公開サイトの見た目や動きを変えるとき)。

## ページの構成と表示の決まり

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

- **展示会の住所**は Google マップを開くリンクにしています（会場名と住所で検索）。下線は住所の文字にだけ引き、地図のアイコンには引きません。地図の埋め込みはしていません（理由は [設計の判断](../decisions.md)）。
- **会期**は、管理画面が開始日・終了日から作った表示（`date_line`）をそのまま出します。
- **作品一覧**は、登録した順に行ごとに並べ、1行の高さをそろえて、幅を画像の縦横比に合わせます（`render_work_gallery` と CSS の `.work-gallery`）。
- **記事や事例の写真**は最大10枚まで使い、4枚まで並べて、それ以上は「+N」と表示します。押すと拡大表示（ライトボックス）になります。
- **新歓カレンダー・DM** はスライド表示です。新歓カレンダーは10枚まで出します。枠の縦横比は、横長の画面（パソコンなど）ではいちばん横長の画像に、縦長の画面（スマホなど）ではいちばん縦長の画像に合わせます（16:9〜4:5）。横長の画面では大きさが画面の高さで、縦長の画面では画面の幅で決まるので、こうするとどの画像も切れずに、いちばん大きく表示されます。パワーポイントの横長の画像も、Instagram 用の正方形・縦長の画像も使えます。DM は、画面の高さに収まる大きさにします。
- **更新履歴**は、今も公開中の項目に関係するものだけを表示します。`ChangeLog` には変更の種類と項目の ID だけがあり、文言は表示するときに今のタイトルで作ります（`change_log_text`）。そのため、項目の名前を変えると過去の行も新しい名前で出ます。文言の決まりは [データの約束（スプレッドシートと保存する形）](data.md) の「更新履歴の文言」。
- **日付**（更新履歴・記事の日付・sitemap）は日本時間で出します。管理画面は日時を世界標準時で保存するので、変換しないと、日本時間の0〜9時に公開したものが前の日になります（2026年11月に直しました。管理画面のプレビューは前から日本時間でした）。
- 更新履歴は**すべて載せます**（2026年11月に決めました）。長くなってきたら、直近の期間だけを載せることを考えてください。
- **検索エンジン向け**：タイトル、説明、SNS で共有したときの表示、`sitemap.xml` を自動で作ります。`src/verification/` の HTML は Google Search Console の所有確認用で、そのまま公開されます。

## GitHub Actions とシークレット

サイトのビルドのワークフロー（`.github/workflows/deploy.yml`）は `workflow_dispatch`（手動または管理画面からの起動）だけで動きます。プッシュのたびに動くのは、テストだけのワークフロー（`.github/workflows/check.yml`。公開サイトと管理画面のテスト）です。 ビルドは同時に1つしか動かしません（`concurrency`。公開を続けて押しても、古い内容のビルドが後から終わって新しいサイトを上書きしないように）。

| ジョブ | 内容 |
|---|---|
| `build` | Python の準備 → テスト → 前回の画像のキャッシュを戻す → 内容の取得 → HTML を作る → GitHub Pages 用にまとめる → 画像のキャッシュを保存し、古いキャッシュを消す |
| `deploy` | GitHub Pages に公開する |

### 画像のキャッシュ

ビルドで一番時間がかかるのは、Drive からの画像の取得です（2026年10月の時点で、3分のうち2分40秒）。画像は展示会ごとに増え続けるので、前回のビルドで取得した画像を GitHub Actions のキャッシュ（`drive-images-…`）に取っておき、**新しい画像と、Drive で中身が変わった画像だけ**を取得します（Drive のチェックサム `md5Checksum` で判定）。取得は8枚ずつ同時に行い、ファイルの情報は100件ずつまとめて問い合わせます。

- **キャッシュには、今のサイトに載っている画像だけを入れます。** 公開リポジトリのキャッシュは、プルリクエストを作れる人（GitHub のアカウントがあれば誰でも）なら中身を読めるためです（[GitHub の説明](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching)）。取得の最後に、サイトに使わなかった画像をキャッシュから消し（`prune_cache`）、保存したあとで前回までのキャッシュを消します。非公開にした・削除した画像は、次のビルドでキャッシュからなくなります。
- **すぐに消したいとき**（作品を消してほしいと頼まれたときなど）：管理画面で非公開にして公開したあと、GitHub の「Actions」→ 左のメニューの「Caches」で `drive-images-` のキャッシュを消してください。消しても、次のビルドが画像を全部取得し直すだけで、困ることはありません。古いキャッシュを消す手順が失敗した場合も、使われないキャッシュは7日で GitHub が消します。
- ビルドの記録（ログ）には、`Images: 120 used, 3 downloaded, 117 from cache, 2 removed from cache, 0 no longer in Drive` のように、取得した枚数だけが出ます。最後の数は、内容には登録されているのに Drive にもうない（削除された）画像の数で、その画像はサイトに載りません。画像の情報がそれ以外の理由（共有が外れた、Google の一時的な不調など）で読めないときは、ビルドを止めます（黙って画像を消さないため。サイトは前の状態のまま残ります）。
- 完成したサイト一式（Pages 用にまとめたもの）も、GitHub に1日だけ残ります。中身は公開したサイトそのものです。

リポジトリの「Settings」→「Secrets and variables」→「Actions」に、次のシークレットが必要です。

| 名前 | 内容 |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | サービスアカウントの鍵（JSON ファイルの中身をそのまま貼る） |
| `CONTENT_SPREADSHEET_ID` | コンテンツ用スプレッドシートの ID |

サービスアカウントは、スプレッドシートと Drive を**読み取り専用**で使います。コンテンツ用スプレッドシートと、Drive の4つのルートフォルダを、サービスアカウントのメールアドレス（`…@….iam.gserviceaccount.com`）に「閲覧者」で共有しておく必要があります。

## ファイルごとの詳細

```
（リポジトリの直下。管理画面の cms/ は docs/reference/cms.md）
├── requirements.txt              Python のライブラリ
├── .github/workflows/deploy.yml  ビルドと公開のワークフロー
├── .github/workflows/check.yml   プッシュのたびのテスト
├── .githooks/pre-commit          コミットの前の確認
├── tests/                        テスト（公開してはいけないものの確認を含む）
├── scripts/
│   ├── fetch_google_content.py   スプレッドシート・Drive → JSON と画像
│   ├── build_site.py             JSON → HTML（入口：読み込み・書き出し・コピー）
│   └── sitebuild/
│       ├── html.py               HTML を作る道具（html()・rich_text()）
│       ├── sections.py           部品ごとの HTML（更新履歴・展示会・記事・入部案内・ヒーロー）
│       ├── page.py               ページ全体の組み立てと SEO
│       └── images.py             画像の縦横比の読み取り
├── tools/screenshot/             見本のデータでの撮影と比較（Node.js。公開しない）
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
| `get_sheet_rows()` | シートの各行を、1行目の見出しを名前にして読む |
| `read_published_content()` | `_PublishedState` から公開中の内容を読む（分けて書かれたセルをつなぎ直し、版を確かめる） |
| `referenced_file_ids()` | サイトに載せる画像のファイル ID を集める（情報をまとめて問い合わせるため） |
| `item_images()` | 項目の画像を、登録した順（`mediaFileIds`）に10枚まで取得する |
| `normalize_recruit_calendar()` | 公開中の新歓カレンダーと画像 |
| `normalize_activity_articles()` | 公開中の活動記録と画像 |
| `normalize_requests()` | 公開中のご依頼事例と画像 |
| `normalize_exhibitions()` | 公開中の展示会を開催予定とアーカイブに分け、DM・作品の画像を取得 |
| `normalize_change_log()` | 更新履歴の行（`kind`・`item_id`・`note`） |

読むシートは `_PublishedState` と `ChangeLog` です（各シートの列は [データの約束（スプレッドシートと保存する形）](data.md)）。

- **内容は `_PublishedState` から読みます**（`read_published_content`）。管理画面が公開のたびに、公開した内容全体を JSON で書くシートです。JSON の形（版2）は [データの約束（スプレッドシートと保存する形）](data.md) にあります。1つのセルに入りきらないとき（45,000文字超）は、管理画面が20,000文字ずつ横の列（`payload_json_2`…）に分けて書き、`payload_json` には `{"storage_format": "chunked-json-v1", "chunk_count": n}` を書きます。読むときにつなぎ直します。
- シートが読めないとき（`_PublishedState` がない・壊れている・共有が外れた・Google の一時的な不調など）は、ビルドを止めます。サイトは前の状態のまま残ります（空のサイトを公開しないため。2026年11月までは、読めないと空の内容として扱い、空のサイトを公開してしまう作りでした）。`ChangeLog` だけは、シートがまだないとき（まだ一度も履歴を書いていないとき）に限り、空の履歴として続けます。`ChangeLog` は行数に上限を付けずに全部読みます。
- `formatVersion` が今の版（2）でない内容は読まずに、ビルドを止めます。形を変えるときは、管理画面と一緒に版を上げます（[データの約束（スプレッドシートと保存する形）](data.md) の「形の版」）。
- 並び順は、管理画面で並べた一覧の順番のままです（ご依頼事例・作品）。

### `scripts/build_site.py` と `scripts/sitebuild/`

| 場所 | 関数 | 役割 |
|---|---|---|
| `build_site.py` | `main()` | 全体の流れ。最後に `src/` のファイルを `dist/` にコピーする（[写真を増やすときの注意](../operations.md#写真を増やすときの注意)） |
| `page.py` | `render_page()` | ページ全体を組み立てる |
| `page.py` | `build_seo_context()` / `render_sitemap_xml()` | 検索エンジン向けの情報と sitemap |
| `sections.py` | `render_update_log()` / `change_log_text()` | 更新履歴。日ごとにまとめ、同じ日の同じ文言は1つにする |
| `sections.py` | `render_exhibition_card()`（`render_exhibition_upcoming()` / `_recent()` / `_archive()` から使う） | 展示会のカード（開催予定・直近・過去） |
| `sections.py` | `render_exhibition_meta()` / `render_venue_address()` | 展示会の会期と会場。住所を Google マップへのリンクにする |
| `sections.py` | `render_work_gallery()` | 作品一覧 |
| `sections.py` | `render_activity_cards()` / `render_request_cards()` | 活動記録・ご依頼事例 |
| `sections.py` | `render_image_grid()` / `render_carousel()` / `render_recruit_calendar()` | 写真の並べ方・スライド |
| `sections.py` | `render_timeline()` / `render_info_points()` / `render_material_chips()` | 年間スケジュール・入部の基本情報・画材 |
| `sections.py` | `render_hero()` | ページの先頭（直近の展示会の作品のスライドショー） |
| `html.py` | `html()` / `rich_text()` | HTML を作る。改行を `<br>` に、`[文字](URL)` をリンクにする |
| `images.py` | `image_aspect()` | 画像の縦横比を読む（並べ方の調整に使う） |

管理画面のプレビュー（`cms/UiPreview.html`）は、この部品をまねています。対応する関数は次のとおりです。

| サイト（`sections.py`） | 管理画面のプレビュー（`UiPreview.html`） |
|---|---|
| `render_exhibition_card()` | `buildExhibitionPreviewCardHtml()` |
| `render_exhibition_meta()` | `buildMetaListHtml()` |
| `render_work_gallery()` | `buildWorkGalleryPreviewHtml()` |
| `render_activity_cards()` / `render_request_cards()` | `buildArticlePreviewHtml()` |
| `render_image_grid()` / `render_carousel()` | `buildThumbCarouselHtml()` |
| `render_recruit_calendar()` | `buildRecruitPreviewHtml()` |
