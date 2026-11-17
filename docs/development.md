# コードを直して反映する手順

管理画面（`cms/`）や公開サイトのコードを直し、確かめて、反映するときに読みます。流れは次のとおりです。

1. [開発の環境を整える](#開発の環境を整える最初に1回)（最初の1回だけ）
2. 直す：[コードを読み始めるとき](#コードを読み始めるとき)、[公開サイトの見た目や動きを変えるとき](#公開サイトの見た目や動きを変えるとき)、[ハマりどころ](#ハマりどころ)、[コードを書くときの決まり](coding-rules.md)
3. [確かめる](#確かめる)：テストと、画面の撮影
4. [反映する](#反映する)：管理画面と公開サイトは、反映の方法が別々

## 開発の環境を整える（最初に1回）

手元の PC でコードを直したり、テストや撮影をしたりするための準備です。管理画面で内容を編集・公開するだけなら、ブラウザで開けばよく、ここは要りません。固定の文章や画像（`src/`）を変えるときには、この準備が要ります。

**動作を確かめた版**（2026年11月）：版が違って動かないときは、この版に合わせて試してください。

| 道具 | 手元で確かめた版 | GitHub Actions | 使うところ |
|---|---|---|---|
| Git | — | — | リポジトリの取得・コミット |
| Node.js | 24 | 24 | 管理画面のテスト・プレビュー・撮影、clasp（clasp は 22 以上が必要） |
| Python | 3.14 | 3.12 | 公開サイトのビルドとテスト（3.12 以上ならどれでもよい） |
| clasp | 3.3 | — | 管理画面を GAS に送る |
| Google Chrome | — | — | 撮影（任意） |

**1. 道具を入れる**：Git（<https://git-scm.com/>）、Node.js（<https://nodejs.org/>）、Python（<https://www.python.org/>）を入れます。Windows で Python を入れるときは、最初の画面の「Add python.exe to PATH」にチェックを入れてください。

**2. リポジトリを手元に持ってくる**：次を実行します。変更を push するには、GitHub のアカウントと、このリポジトリへの書き込み権限が必要です。

```bash
git clone https://github.com/ryobi-art-club/homepage.git
cd homepage
```

この PC で初めてコミットする場合は、作成者の名前とメールアドレスも設定します。次の例を自分の情報に置き換えてください。コミットの情報として公開されるので、公開してよい名前・アドレスを使います。

```bash
git config user.name "部員の名前"
git config user.email "member@example.com"
```

**3. コミットの前の確認を有効にする**：このリポジトリは公開しているので、公開してはいけないもの（メールアドレス・管理画面の URL・鍵・Excel など）が入っていたら、コミットを止めます（`tests/test_repository_contents.py`。[公開してはいけないものの確認](#公開してはいけないものの確認)）。クローンするたびに1回だけ実行します。

```bash
git config core.hooksPath .githooks
```

リポジトリの「Settings」→「Advanced Security」→「Secret Protection」の「Push protection」も有効にしておくと、鍵などの形をしたものはプッシュの時点で GitHub が止めます（組織のオーナーが1回だけ設定する）。

**4. Python の仮想環境を作る**：公開サイトのビルドとテストに使うライブラリを、このリポジトリ専用の場所（`.venv`）に入れます。PC 全体の Python を汚さず、ほかの作業の影響も受けません。`.venv` は Git に入りません（`.gitignore`）。

Windows（PowerShell）：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # 「スクリプトの実行が無効」と出たら、先に Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
```

Mac・Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

次からは、作業を始めるたびに2行目（`Activate.ps1` か `source …`）だけを実行します。行の頭に `(.venv)` と出ていれば、仮想環境を使っています。

**5. 撮影の道具を入れる（任意）**：画面の撮影と比べる道具を使うときだけ要ります（[管理画面を手元で確かめる（プレビューと撮影）](#管理画面を手元で確かめるプレビューと撮影)、[公開サイトを手元で作って確かめる（撮影）](#公開サイトを手元で作って確かめる撮影)）。

```bash
npm install --prefix cms/tools/preview
npm install --prefix tools/screenshot
```

Chrome が標準の場所（Windows の `C:/Program Files/Google/Chrome/Application/chrome.exe`）にないときは、撮影のコマンドに `--chrome <chrome の場所>` を付けるか、環境変数 `CHROME_PATH` に場所を入れてください。

**6. 管理画面を GAS に送る準備（反映するときだけ）**

手元のテストとプレビューだけなら、この準備は要りません。

1. 管理画面の GAS プロジェクトを編集・デプロイする Google アカウントで <https://script.google.com/home/usersettings> を開き、「Google Apps Script API」をオンにします。オフのままだと `clasp push` が失敗します。
2. clasp を入れて、同じアカウントでログインします（画面の案内に従って、ブラウザでログインする）。
   ```bash
   npm install -g @google/clasp
   clasp login
   ```
3. ログイン情報（`.clasprc.json`）は PC のホームフォルダに保存されます。リポジトリの中には置かないでください（置いても、コミットの前の確認で止まります）。

**7. 確かめる**：リポジトリの直下で、Python の仮想環境を有効にしてから実行します。Google には接続せず、見本のデータで確認します。

```bash
python -m unittest discover tests
cd cms
node --test tests/*.cjs
node tools/preview/build.cjs
cd ..
```

両方のテストが通ったら、作られた `cms/tools/preview/out/preview.html` をブラウザで開きます。見本の内容が入った管理画面が表示されれば、準備は完了です。撮影は任意です。プレビューの詳しい使い方は [管理画面を手元で確かめる（プレビューと撮影）](#管理画面を手元で確かめるプレビューと撮影)。

**ブランチ**：ふつうは `main` に直接コミットして push して構いません（[設計の判断](decisions.md)）。

## コードを読み始めるとき

初めてコードを読むときは、部員が「公開する」を押してからサイトに出るまでを、1本の線でたどるのがおすすめです。この流れに、管理画面とサイトのほとんどの部分が出てきます。各段階の関数の役割は、括弧の中の資料の表で調べます。

1. **画面を触る**：手元のプレビュー（[管理画面を手元で確かめる（プレビューと撮影）](#管理画面を手元で確かめるプレビューと撮影)）を開き、項目を編集して「公開する」まで押してみる。何ができるシステムかを、先に手でつかみます。
2. **ボタンからサーバーへ**：`cms/UiPublish.html` の `startPublish` → `publishContent`（誤字チェックのあと、`buildPayload()` で作った内容を `serverCall('publishState', …)` で送る）。`serverCall` は `cms/UiCore.html` にあります（[管理画面の仕組み](reference/cms.md) の「`Ui.html` / 画面のスクリプト」）。
3. **公開の処理**：`cms/ContentApi.js` の `publishState` を上から読む。`normalizePayload_`（内容を整える）→ `finalizeManagedFolders_`（Drive）→ `writePublishedState_`・`appendChangeLog_`（シートに保存）→ `clearDrafts_`・`cleanupUnreferencedDraftFolders_`（下書きと下書き用フォルダを整理）→ `appendAdminLog_` → `dispatchGithubWorkflow_`（サイトのビルドを起動）→ `collectGarbage_`（片付け）（[管理画面の仕組み](reference/cms.md) の「`ContentApi.js`」、保存する形は [データの約束](reference/data.md)）。
4. **サイトのビルド**：`.github/workflows/deploy.yml` の手順を上から読む。`scripts/fetch_google_content.py` の `main`（`read_published_content` で内容を読み、`normalize_…` で画像を取る）→ `scripts/build_site.py` の `main` → `scripts/sitebuild/page.py` の `render_page` → `sections.py` の各 `render_…`（[公開サイトの仕組み](reference/site.md) の「ファイルごとの詳細」）。

ログイン（`cms/AppAuth.js`）と画像のアップロード（`cms/MediaApi.js`）は、この流れの外にあります。必要になったときに読めば足ります。

## 公開サイトの見た目や動きを変えるとき

- HTML は `scripts/sitebuild/` が Python で組み立てています（外部のテンプレートの仕組みは使っていません）。HTML は `html()`（`sitebuild/html.py`）で作ります。`{名前}` に入れた値は文字として表示されるように書き換わるので、内容に `<` や `"` があってもページは崩れません。管理画面の画面の作り方（`html`…`` ）と同じ考え方です。
- 見た目を変えないはずの作業（整理など）では、作業の前後で `tools/screenshot/` の撮影を比べます（[公開サイトを手元で作って確かめる（撮影）](#公開サイトを手元で作って確かめる撮影)）。
- 見た目は `src/stylesheet.css`、動き（タブ、写真の拡大表示、スライド）は `src/site.js` です。外部のライブラリは使っていません（アイコンだけ Font Awesome を読み込んでいます）。
- 管理画面の右側の「プレビュー」は、このサイトの見た目をまねて作っています（`cms/UiStyles.html` の「サイトプレビュー」の部分と、`cms/UiPreview.html`）。サイトの見た目を変えたら、管理画面のプレビューも合わせて直すと、部員が公開前に確認しやすくなります。
- 変えたら、手元でビルドして確認します（[公開サイトを手元で作って確かめる（撮影）](#公開サイトを手元で作って確かめる撮影)）。
- 名前の付け方・二重管理をしない・言葉・HTML・CSS の決まりは、管理画面と共通です（[コードを書くときの決まり](coding-rules.md)）。CSS の色や大きさは、`src/stylesheet.css` の先頭の決まった値から役割で選びます。

## 外部のライブラリや道具の版を上げるとき

上げるかどうかの判断は [管理者の手順](operations.md) の「更新を入れるかの判断」。上げたら、[テスト](#テスト) と撮影（`cms/tools/preview/shoot.cjs`・`tools/screenshot/shoot.cjs`）で確かめます。

| もの | 直す場所 | 注意 |
|---|---|---|
| SheetJS（Excel の目録の読み込み） | `cms/UiMedia.html` の `SHEETJS_URL` と `SHEETJS_INTEGRITY` | 2つを一緒に変える。整合性チェックの値は `curl -s <URL> \| openssl dgst -sha384 -binary \| openssl base64 -A` の結果の頭に `sha384-` を付けたもの。`cms/tools/preview/shoot.cjs` が「SheetJS を整合性チェック付きで読み込めた」と出すか確かめる |
| Font Awesome（アイコン） | 管理画面の `cms/Ui.html` と、サイトの `scripts/sitebuild/page.py` | 両方の URL と `integrity` を一緒に変える。値は `curl -s <URL> \| openssl dgst -sha512 -binary \| openssl base64 -A` の結果の頭に `sha512-` を付けたもの（[cdnjs](https://cdnjs.com/libraries/font-awesome) のページにも載っている）。撮影でアイコンが出るか確かめる |
| Python のライブラリ | `requirements.txt` | 大きな版上げで壊れないよう上限（`<3` など）を付けている。上限を上げたら、テストと撮影のあと、手動実行（Run workflow）で本番のビルドが通るか確かめる |
| GitHub Actions の部品 | `.github/workflows/deploy.yml`・`check.yml` の `actions/checkout@v5` など | 上げたら、手動実行（Run workflow）でビルドが通るか確かめる |
| Node.js・Python の版 | `.github/workflows/` の `node-version`・`python-version` と、このページの「動作を確かめた版」の表 | 手元とワークフローの両方で、テストが通るか確かめる |

## ハマりどころ

### 試すための別の環境はない

管理画面にも公開サイトにも、本番とは別の「試す用」の環境はありません（[設計の判断](decisions.md)）。GAS の「デプロイをテスト」（URL の末尾が `/dev`）の管理画面も、**本番のスプレッドシート・Drive・GitHub Actions を使います**。そこで「下書き保存」すれば本番の下書きに入り、「公開する」を押せば本物のサイトが作り直され、全員の下書きも消えます。

- 見た目や動きは、まず手元のプレビューとサンプルデータで確かめます（[管理画面を手元で確かめる（プレビューと撮影）](#管理画面を手元で確かめるプレビューと撮影)、[公開サイトを手元で作って確かめる（撮影）](#公開サイトを手元で作って確かめる撮影)）。
- `/dev` で確かめるのは、手元では再現できないこと（Google のサービスとのやりとり）だけにし、保存や公開を押すときは本番の操作だと思って行います。

### 画面のスクリプトに書いてはいけない文字列がある

画面のスクリプト（`UiCore.html` など5つ）は GAS の HtmlService で `Ui.html` の中に埋め込まれて配信されます。このとき、次の文字列があると `<script>` の中身が壊れ、`Uncaught SyntaxError: Invalid or unexpected token` になります。そうなると関数が1つも定義されず、「確認コードを送信」を押しても何も起きない状態になります。

- `https://`、`http://`、`//`（**`//` のコメントも書けません**。コメントは `/* */` を使う）
- `image/*`
- SVG の `xmlns="http://www.w3.org/2000/svg"`

URL は `URL_PROTOCOL + 'www.example.com/…'` のように組み立て（`URL_PROTOCOL` は `'https:' + String.fromCharCode(47, 47)`）、`image/*` は `'image/' + '*'` と分けて書きます。インライン SVG は `xmlns` なしで表示できます。

`node --test tests/*.cjs` の `ui-script.test.cjs` が、構文エラーとこれらの文字列を自動で確認します。

### スプレッドシートに書くと値が勝手に変わる

スプレッドシートは、`=` で始まる文字を数式、`2026-05-10` を日付、`001` を数字として扱います。内容のシートに書くときは、セルの書式を「書式なしテキスト」（`@`）にしてから書いています（`ContentStore.js` の `writeSheet_`）。新しくシートに書く処理を足すときも同じようにしてください。

### `.claspignore`

GAS に送らないファイルは `.claspignore` に書きます。手元専用のファイル（Node.js 用のツールなど）を足したら、ここにも足してください。足し忘れると GAS に送られ、GAS 側でエラーになることがあります。

### スマホ表示の指定は `AppMain.js` にある

スマホで画面の幅に合わせて表示するための指定（viewport）は、`Ui.html` ではなく `AppMain.js` の `doGet()` で付けています（`addMetaTag`）。HtmlService では `Ui.html` に書いても効かないためです。プレビュー（`tools/preview/build.cjs`）でも同じ指定を足しています。

### ログインの有効期限は、操作しても延びない

ログインの有効期限（`SESSION_TTL_MINUTES`。[Script Properties（設定値）](reference/cms.md#script-properties設定値)）は、**ログインした時点から**数えます。操作していても延長されません。再読み込みしても有効期限の間はログインしたままですが、延長はされません。切れると「セッションが切れています」と出るので、こまめな下書き保存を部員に勧めています。

### Drive を手で直接いじると、次に変更するまで合わせ直されない

公開処理は、前回の公開から変わっていない項目の Drive のフォルダを確認しません（[管理画面の仕組み](reference/cms.md#contentapijs--画面から呼ばれる入口内容と公開)の「変わった分だけ処理する」）。Drive でフォルダ名や共有設定を手で変えても、その項目を管理画面で変更して公開するまでは、そのままになります。ファイルの管理は管理画面の中で行ってください。

### 複数の Google アカウントでログインしていると開けない

部員のブラウザに複数の Google アカウントでログインしていると、「現在、ファイルを開くことができません」と出ることがあります。GAS のウェブアプリでよく知られた問題で、コードでは直せません。対処は [部員からよく聞かれること](troubleshooting.md#部員からよく聞かれること) にあります。

### 改行コード

Windows で作業するとファイルの改行コードが CRLF になります。Git が自動で変換するので、ふつうは気にしなくて大丈夫です。スクリプトでファイルを書き換えるときは、元の改行コードを保ってください。

## 確かめる

### テスト

```bash
cd cms && node --test tests/*.cjs && cd ..   # 管理画面
python -m unittest discover tests             # 公開サイトと、公開してはいけないものの確認
```

どちらも Google には接続しません。管理画面は、保存形式、展示会の画像の扱い、目録の読み取り、誤字チェック、ログイン、エラーの通知、会期表示などを確かめます。公開サイトは、`_PublishedState` の読み方（セルを分けた形を含む）、版が違う内容で止まること、サイトのデータの作り方、更新履歴の表示、画像のキャッシュを確かめます。

GitHub Actions でも、プッシュのたびに両方を動かします（`.github/workflows/check.yml`）。サイトのビルドの前にも、公開サイトのテストを動かし、通らなければビルドを止めます（サイトは前の状態のまま残ります）。

### 管理画面を手元で確かめる（プレビューと撮影）

管理画面の見た目や動きは、GAS に送る前に手元のブラウザで確認できます。サンプルデータを使い、Google には接続しません。詳しくは [`cms/tools/preview/README.md`](../cms/tools/preview/README.md)。

```bash
cd cms
node tools/preview/build.cjs     # tools/preview/out/preview.html を作る
node tools/preview/shoot.cjs     # 全機能を動かして撮影（任意）
cd ..
```

作られた `cms/tools/preview/out/preview.html` をブラウザで開きます。

`shoot.cjs` は、ログインから公開までのボタンをひととおり押し、崩れやすい画面を撮影します（`tools/preview/out/shots/`）。最後に次の内容を表示します。

- 画面が横にはみ出していないか（スマホ・タブレット・横向きの各サイズ）
- 画面の中で JavaScript のエラーが起きていないか
- 画面のスクリプト（`UiCore.html` など5つ）の関数のうち、一度も動かなかったもの（機能を足したら、ここに出ないよう撮影の手順も足す）
- Excel 読み込み用のライブラリ（SheetJS）を、整合性チェック付きで読み込めたか

見た目や動きを変えないはずの作業では、作業の前後の撮影結果を `tools/preview/compare.cjs` で比べます（画像は1画素ずつ、サーバーに送った内容も比べる）。使い方は [`cms/tools/preview/README.md` の「見た目と動きが変わっていないか比べる」](../cms/tools/preview/README.md#3-見た目と動きが変わっていないか比べる作りを整理するとき)。公開サイトの撮影は [公開サイトを手元で作って確かめる（撮影）](#公開サイトを手元で作って確かめる撮影)。

### 公開サイトを手元で作って確かめる（撮影）

公開サイトも管理画面と同じく、手元では見本のデータ（`tools/screenshot/sample-content.json`）だけでサイトを作って確かめます。Google には接続しないので、鍵は要りません（理由は [設計の判断](decisions.md)）。スプレッドシートや Drive から読む部分（`scripts/fetch_google_content.py`）は、Google の代わりに偽物を使う [テスト](#テスト)（`tests/test_fetch_google_content.py`）で確かめます。

```bash
npm install --prefix tools/screenshot                 # 最初の1回だけ
node tools/screenshot/shoot.cjs                       # サイトを作って撮影する
node tools/screenshot/compare.cjs --save <控えのフォルダ>   # 見た目を変えないはずの作業の前に、控えを取る（リポジトリの外に置く）
node tools/screenshot/compare.cjs <控えのフォルダ>          # 作業のあとに、1画素ずつ比べる
```

- `shoot.cjs` は、見本のデータからサイトを作り（`tools/screenshot/out/dist/index.html`。ブラウザで開いて触れる）、パソコン・タブレット・スマホ・スマホ横向きで撮影します（`tools/screenshot/out/shots/`）。画面の横はみ出しと、画面のエラーも報告します。
- Chrome と Node.js と Python の仮想環境、ネット接続（フォントとアイコンを CDN から読むため）が要ります。
- 撮影は、動きを減らす設定（`prefers-reduced-motion`）で行います。スライドショーなどの時間で動く表示が止まり、何度撮っても同じ画像になります。
- 本番で表示崩れが見つかったら、同じ条件のデータを `sample-content.json` に足しておくと、次から手元で確かめられます。

### 公開してはいけないものの確認

このリポジトリは公開しています。`tests/test_repository_contents.py` は、次のものが入っていたら失敗します。コミットの前（`.githooks/pre-commit`）、プッシュのたび（`check.yml`）、サイトのビルドの前（`deploy.yml`）に動きます。

- メールアドレス（見本用に予約されたドメイン（`example.com`・`.test` など）と、サイトに載せている部の連絡先を除く）
- 管理画面の URL（Apps Script のウェブアプリの URL）
- 鍵（サービスアカウントの秘密鍵）
- 部員の情報が入りやすいファイル（スプレッドシートを書き出した Excel、clasp のログイン情報）

`.gitignore` でも、これらの種類のファイルと `tmp/`（作業用のメモや書き出したデータを置く場所）を除いています。

## 変更を確認して送る

リポジトリの直下で作業します。固定の文章・画像を変えるときも、この手順で送ります。

1. 変更したファイルと差分を確認する。
   ```bash
   git status --short
   git diff
   ```
2. [テスト](#テスト) と見本データで確認する。公開サイトの変更は [公開サイトの撮影](#公開サイトを手元で作って確かめる撮影)、管理画面の変更は [プレビューと撮影](#管理画面を手元で確かめるプレビューと撮影) を使う。固定の文章・画像も、公開前に表示を確かめる。
3. 今回変更したファイルだけを選び、送る差分を確認してコミットする。次は `src/site_static.json` を変えた例。ほかのファイルを変えたときは、そのファイル名を指定する。
   ```bash
   git add src/site_static.json
   git diff --cached
   git commit -m "固定の文章を更新"
   ```
4. GitHub に送る。
   ```bash
   git push
   ```

**確かめ方**：GitHub の `main` に今のコミットが表示されれば、送信は完了です。公開サイトと管理画面への反映は、次の手順で別々に行います。

## 反映する

管理画面（GAS）と公開サイト（GitHub Pages）は、同じリポジトリにあっても反映は別々です。

### 管理画面を反映する

`clasp -P cms push` で送るのはテスト用の版だけです。部員が使っている本番の管理画面は、手順4のデプロイまで変わりません。

1. リポジトリの直下で `clasp -P cms push` を実行する（`-P cms` で `cms/.clasp.json` を使う。`cms/` に移らなくてよい）。`cms/.claspignore` に書いたもの（`tests/`・`tools/` など）は送られない。
   ```bash
   clasp -P cms push
   ```
2. 確かめたいときは、GAS エディタの「デプロイ」→「デプロイをテスト」の URL（末尾が `/dev`）で、テスト用の版を開く。**データは本番と同じ**です（[試すための別の環境はない](#試すための別の環境はない)）。
3. GAS エディタで「デプロイ」→「デプロイを管理」を開き、本番のデプロイを選んで「編集」（鉛筆）を押す。
4. バージョンを「新バージョン」にして「デプロイ」を押す。

**確かめ方**：管理画面を再読み込みして、ふだんどおりログインできれば完了です。管理画面の URL は変わりません（部員は再読み込みするだけで新しい版になります）。「新しいデプロイ」を作ると URL が変わってしまうので、使いません。

### 管理画面を元に戻す

1. 今回の変更で保存形式を変えていないか、戻す版が現在のデータを読めるかを確認する（[データの約束](reference/data.md)、[両方を変えるときの順番](#両方を変えるときの順番)）。対応していなければ、その版へは戻さない。
2. GAS エディタで「デプロイ」→「デプロイを管理」を開き、本番のデプロイの「編集」（鉛筆）を押す。
3. バージョンに戻す番号を選んで「デプロイ」を押す。
4. 管理画面を再読み込みしてログインし、内容を読み込めることと、問題になった箇所が回復したことを確認する。

手元のコードを戻さずに、管理画面を前の版に切り替えられます。保存済みの内容は戻りません。

### 公開サイトを反映する

push だけでは、サイトは作り直されません（ビルドのワークフローは「公開する」か手動実行でだけ動きます。理由は [設計の判断](decisions.md)）。

1. [変更を確認して送る](#変更を確認して送る) の手順で、変更をコミットして push する。コードや固定ファイルを変えていない場合は、この手順を省略する。
2. GitHub の「Actions」→「Build and Deploy Ryobi Site」→「Run workflow」で、変更を push した `main` を選んで実行する。

**確かめ方**：「Actions」のビルドが成功し、サイトが変わっていれば完了です。失敗したときは [困ったとき](troubleshooting.md)。

管理画面の「公開する」でもサイトは作り直されます。ただし、管理画面の内容を公開し、全員の下書きも消す操作なので、コードや固定の文章・画像だけを反映するときは、上の手動実行を使います。

### 公開サイトのコードの変更を取り消す

コードを変えて公開したあと、表示や動きに不具合が見つかり、その変更を取り消すときの手順です。固定の文章や画像の間違いは、[固定の文章や画像を変える](operations.md#固定の文章や画像を変える) の手順で修正します。

1. Git の履歴で、原因になった変更のコミットを確かめる。保存するデータの形も変えていた場合は、[データの約束](reference/data.md) と [両方を変えるときの順番](#両方を変えるときの順番) を読み、今のデータを読めるか、管理画面側の変更も戻す必要があるかを先に確認する。
2. `git revert <コミットID>` で、その変更を打ち消すコミットを作る。
3. 手元で [テスト](#テスト) と [公開サイトの撮影](#公開サイトを手元で作って確かめる撮影) を行い、問題がなければ push し、[公開サイトを反映する](#公開サイトを反映する) の手動実行と表示確認まで行う。

ビルドは実行時の掲載内容をスプレッドシートと Drive から読み直します。コードの変更を取り消しても、掲載内容は以前の状態には戻りません。管理画面で公開した内容の間違いは、管理画面で修正してから「公開する」を押します。

### 両方を変えるときの順番

管理画面（GAS）と公開サイト（GitHub Actions）は、同じリポジトリにあっても反映は別々です。スプレッドシートに列を足すなどの変更は、**古いコードでも新しいコードでも読めるように**作っています（列は末尾に足し、使わなくなった列もすぐには消さない）。そのため、ふつうはどちらを先に反映しても壊れません。保存する形を変えるときだけは順番が決まるので、その順番を書き残してください（例：2026年11月の更新履歴の形の変更は、サイトのコードを先に入れた）。
