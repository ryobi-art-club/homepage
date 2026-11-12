# データの約束（スプレッドシートと保存する形）

管理画面が書き、公開サイトのビルドが読むデータの形です。項目を足す・変えるときは、ここを見て両方を一緒に直します。

シートは、最初に保存・公開したときに自動で作られます。シート名は `AppConfig.js` の `CONTENT_SHEETS` にあります。列は1行目の見出しの名前で読むので、列の順番は関係ありません。

**内容は `_PublishedState` の1か所に置きます**

公開した内容（新歓カレンダー・活動記録・展示会・ご依頼事例）は、`_PublishedState` に JSON で保存します。管理画面もサイトのビルドも、ここから読みます。

- `_PublishedState` がまだないとき（作り直した直後）は、内容が空のまま始まります。
- `_PublishedState` が壊れていて読めないときは、管理画面もサイトのビルドも空の内容を出さずにエラーで止まります。空のまま公開して、サイトの内容を全部消してしまうのを防ぐためです。スプレッドシートの「ファイル」→「変更履歴」から戻してください。

`_PublishedState` の列

| 列 | 内容 |
|---|---|
| `updated_at` / `revision` | 最後に内容が変わった公開の日時・通し番号 |
| `sha256` | 内容のハッシュ。公開のとき、前回から変わったかを調べる |
| `payload_json`（`_2`、`_3`…） | 内容の JSON（下の「保存形式」） |

**内容の JSON の形（版2）**：管理画面とサイトのビルドの約束です。項目を変えるときは、管理画面の `cms/ContentModel.js` の `CONTENT_FIELDS` と、サイトの `scripts/fetch_google_content.py` を一緒に直します（サイトが読む項目は [`scripts/fetch_google_content.py`](site.md#scriptsfetch_google_contentpy)）。

```json
{
  "formatVersion": 2,
  "recruitCalendars": [{ "year": "2026", "mediaFolderId": "…", "mediaFileIds": ["…"], "published": true }],
  "activityArticles": [{ "articleId": "activity-…", "title": "…", "category": "record", "body": "…",
                         "mediaFolderId": "…", "mediaFileIds": ["…"], "published": true, "createdAt": "2026-10-30T07:50:18.481Z" }],
  "exhibitions": [{ "exhibitionId": "exhibition-…", "title": "…", "subtitle": "…", "theme": "…",
                    "venueName": "…", "venueAddress": "…", "dateLine": "…", "timeLine": "…",
                    "displayBucket": "upcoming", "mediaFolderId": "…", "dmFileIds": ["…"],
                    "works": [{ "fileId": "…", "title": "…", "artist": "…" }],
                    "published": true, "startDate": "2026-11-07", "endDate": "" }],
  "requestCases": [{ "caseId": "request-…", "title": "…", "body": "…", "mediaFolderId": "", "mediaFileIds": [], "published": true }]
}
```

| 種類 | 項目の決まり |
|---|---|
| 全体 | 名前は `mediaFolderId` のように単語の頭を大文字にしてつなぐ。1つの値には1つの名前だけ。ほかの値から決まる値は保存しない。並び順は一覧（配列）の順番そのもの |
| 新歓カレンダー | 年度の新しい順。`published` が `true` なのは1つだけ（なければ、サイトにも管理画面のプレビューにも新歓カレンダーは出ない）。表示名（「2026年度 新歓イベントカレンダー」）は年度から作る（`recruitCalendarLabel_`） |
| 活動記録・告知 | 作成日（`createdAt`。初回公開日として表示）の新しい順。`title` は120字、`body` は4000字まで。`category` は `record` / `event` / `other` |
| 展示会 | 開催予定→アーカイブ、それぞれ開始日の順。`title` は140字、`theme`（概要）は1000字まで。`dmFileIds`（DM＝案内はがきの画像）は表・裏の2つまで。`works`（作品）は表示する順に並べる。`dateLine`（会期）はふつう管理画面が開始日・終了日から作る。`startDate`・`endDate` は `yyyy-MM-dd`（1日だけの展示は終了日が空） |
| ご依頼事例 | 管理画面で並べた順。`title` は120字、`body` は4000字まで |
| 画像 | `mediaFileIds`（展示会は `dmFileIds` と `works`）が、その項目で使う画像。フォルダにあっても、ここにない画像は使わない |

**下書き**（`_Drafts`）も同じ形です。展示会には、日付のない下書きを並べるための `draftCreatedAt` が付きます。ほかに、更新履歴のメモ（`manualChangeNote`）を持ちます。

**形の版**：`formatVersion` が今の版（2）でない内容は読まずに、エラーで止めます（管理画面の `requireContentFormat_`、サイトのビルドの `read_published_content`）。形を変えるときは版を上げ、古い版を新しい版に直す処理をこの2か所に足します。直す処理を入れて一度公開し、古い版のデータが残っていないことを確かめてから、その処理を消します。

**そのほかのシート**

| シート | 内容 | サイトのビルドが読むか |
|---|---|---|
| `ChangeLog` | サイトの更新履歴。1行に1つの変更：`timestamp`（公開日時）、`kind`（`recruit` 新歓カレンダー・`activity`・`exhibition`・`request`・`note` 更新履歴メモ）、`item_id`（項目の ID。新歓とメモは空）、`note`（メモの1行）、`actor_name`（公開した人）。下の「更新履歴の文言」も参照。ビルドが読むので、メールアドレスは置かない | 読む |
| `_Drafts` | 下書き。公開すると全部消える | 読まない |
| `_AdminLog` | 操作ログ（誰がいつ公開し、何を変えたか。メールアドレスも残る）。ホームの「公開履歴」に出る | 読まない |
| `_ProofreadChecked` | 誤字チェック済みの文章のハッシュ。シートを消すと、全文章が次の公開で再チェックされる | 読まない |

**更新履歴に行を足すとき**（`buildChangeLogRows_`）：初めて公開した項目、公開中の年度の新歓カレンダーの差し替え、更新履歴メモ（1行ずつ）。非公開から公開に戻した項目は、前に公開したときの行がまた表示されるだけで、行は足しません（「初めて」かどうかは、更新履歴にその項目の行がすでにあるかで決めます）。内容を直しただけでも足しません。

**更新履歴の文言**：タイトルは保存せず、表示するときに今の内容から ID で引いて作ります（管理画面の `changeLogText_`、サイトのビルドの `change_log_text`）。項目の名前を変えると、過去の行も新しい名前で出ます。非公開・削除した項目の行は出しません。同じ日の同じ文言は1つにまとめます。

| kind | 文言 |
|---|---|
| `recruit` | 新歓イベントカレンダーを更新 |
| `activity` | 活動記録・告知「（タイトル）」 |
| `exhibition` | 展示会「（タイトル）」の情報を公開 |
| `request` | 取り組み「（タイトル）」 |
| `note` | （メモの文） |

この表は管理画面（`cms/ContentHistory.js` の `CHANGE_LOG_ITEM_LISTS`）とサイトのビルド（`scripts/sitebuild/sections.py` の `CHANGE_LOG_TEXT`）の2か所にあります。言語が違うので1つにはできません。変えるときは両方を一緒に直します。

**下書きと公開内容の保存形式**：`_Drafts` と `_PublishedState` は内容を JSON でセルに保存します。1つのセルには5万字までしか入らないため、45,000字を超えたら20,000字ずつ `payload_json_2`、`payload_json_3`、… の列に分けて保存し（`buildPayloadCells_`）、`payload_json` には `{"storage_format":"chunked-json-v1","chunk_count":n}` を書きます。読むときにつなげます（`parsePayloadCells_`。サイトのビルドでは `read_published_content`）。列は自動で増えます。

**スプレッドシートまわりの制約**（2026年10月に確認）

| 制約 | 値 | このシステムでの状況 |
|---|---|---|
| 1つのセルの文字数 | 50,000字（超えて書き込むとエラー） | 上のとおり分けて保存する。書き込む前にも確かめる（`validateSheetCellLengths_`） |
| 1つのスプレッドシートの大きさ | 2,000万セル、または100MB | 内容全体で3万字ほど（2026年10月）。増えるのは年に1〜2万字ほどの見込みで、当たらない |
| Sheets API の読み取り回数 | 1分あたりプロジェクト全体で300回・1人60回 | 管理画面を開くたびに1回 |
| Sheets API の1回の大きさ | 2MB 以下を推奨 | 同上の見込みで、何十年も当たらない |
| GAS の1回の処理時間 | 6分 | 公開は変更がなければ20秒ほど |

**シートの書き込み方**：先に全部消してから書くのではなく、範囲をまとめて上書きし、余った部分を空欄にします。公開のたびに、内容のシートの末尾の空いた行・列を片付けます。

**許可リスト用スプレッドシート**：`allowlist` シート（`AppConfig.js` の `ALLOWLIST_SHEET_NAME`）。1行目が `name` / `email` の見出し。
