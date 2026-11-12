# コードを直して反映する手順

管理画面（`cms/`）や公開サイトのコードを直し、確かめて、反映するときに読みます。流れは次のとおりです。

1. [開発の環境を整える](#開発の環境を整える最初に1回)（最初の1回だけ）
2. 直す：[公開サイトの見た目や動きを変えるとき](#公開サイトの見た目や動きを変えるとき)、[ハマりどころ](#ハマりどころ)、[コードを書くときの決まり](coding-rules.md)
3. [確かめる](#確かめる)：テストと、画面の撮影
4. [反映する](#反映する)：管理画面と公開サイトは、反映の方法が別々

## 開発の環境を整える（最初に1回）

手元の PC でコードを直したり、テストや撮影をしたりするための準備です。内容を編集・公開するだけなら、ブラウザで管理画面を開くだけでよく、ここは要りません。

**動作を確かめた版**（2026年11月）：版が違って動かないときは、この版に合わせて試してください。

| 道具 | 手元で確かめた版 | GitHub Actions | 使うところ |
|---|---|---|---|
| Git | 2.53（Windows） | — | リポジトリの取得・コミット |
| Node.js | 24 | 24 | 管理画面のテスト・プレビュー・撮影、clasp（clasp は 22 以上が必要） |
| Python | 3.14 | 3.12 | 公開サイトのビルドとテスト（3.12 以上） |
| clasp | 3.3 | — | 管理画面を GAS に送る |
| Google Chrome | — | — | 撮影（任意） |

**1. 道具を入れる**：Git（<https://git-scm.com/>）、Node.js（<https://nodejs.org/>）、Python（<https://www.python.org/>）を入れます。Windows で Python を入れるときは、最初の画面の「Add python.exe to PATH」にチェックを入れてください。

**2. リポジトリを手元に持ってくる**：GitHub のアカウントを作り、組織 `ryobi-art-club` のオーナーに招待してもらいます（書き込むには招待が要ります。[引き継ぎのときに渡すもの](operations.md#引き継ぎのときに渡すもの)）。

```bash
git clone https://github.com/ryobi-art-club/homepage.git
cd homepage
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

**6. 管理画面を GAS に送る準備（管理画面を直す人だけ）**

1. 開発用の Google アカウントでログインして <https://script.google.com/home/usersettings> を開き、「Google Apps Script API」をオンにします。オフのままだと `clasp push` が失敗します。
2. clasp を入れて、**開発用の Google アカウント**でログインします（画面の案内に従って、ブラウザでログインする）。個人のアカウントでログインすると、GAS プロジェクトに送れません。
   ```bash
   npm install -g @google/clasp
   clasp login
   ```
3. ログイン情報（`.clasprc.json`）は PC のホームフォルダに保存されます。リポジトリの中には置かないでください（置いても、コミットの前の確認で止まります）。

**7. 確かめる**：[テスト](#テスト) のテストが両方とも通れば、準備は完了です。

**Windows での注意**

- PowerShell の `echo "…" > ファイル` は、文字を UTF-16 という形式で保存します。ふつうはエディタでファイルを作ってください（コミットの前の確認は、UTF-16 のファイルも読めるようにしてあります）。
- 改行コード（CRLF / LF）は Git が自動で変換します（[改行コード](#改行コード)）。

## 公開サイトの見た目や動きを変えるとき

- HTML は `scripts/sitebuild/` が Python で組み立てています（外部のテンプレートの仕組みは使っていません）。HTML は `html()`（`sitebuild/html.py`）で作ります。`{名前}` に入れた値は文字として表示されるように書き換わるので、内容に `<` や `"` があってもページは崩れません。管理画面の画面の作り方（`html`…`` ）と同じ考え方です。
- 見た目を変えないはずの作業（整理など）では、作業の前後で `tools/screenshot/` の撮影を比べます（[公開サイトを手元で作って確かめる（撮影）](#公開サイトを手元で作って確かめる撮影)）。
- 見た目は `src/stylesheet.css`、動き（タブ、写真の拡大表示、スライド）は `src/site.js` です。外部のライブラリは使っていません（アイコンだけ Font Awesome を読み込んでいます）。
- 管理画面の右側の「プレビュー」は、このサイトの見た目をまねて作っています（`cms/UiStyles.html` の「サイトプレビュー」の部分と、`cms/UiPreview.html`）。サイトの見た目を変えたら、管理画面のプレビューも合わせて直すと、部員が公開前に確認しやすくなります。
- 変えたら、手元でビルドして確認します（[公開サイトを手元で作って確かめる（撮影）](#公開サイトを手元で作って確かめる撮影)）。
- 名前の付け方・二重管理をしない・言葉・HTML・CSS の決まりは、管理画面と共通です（[コードを書くときの決まり](coding-rules.md)）。CSS の色や大きさは、`src/stylesheet.css` の先頭の決まった値から役割で選びます。

## ハマりどころ

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

ログインの有効期限（スクリプト プロパティ `SESSION_TTL_MINUTES`、現在の設定は180分）は、**ログインした時点から**数えます。操作していても延長されません。再読み込みしても有効期限の間はログインしたままですが、延長はされません。切れると「セッションが切れています」と出るので、こまめな下書き保存を部員に勧めています。

### Drive を手で直接いじると、次に変更するまで合わせ直されない

公開処理は、前回の公開から変わっていない項目の Drive のフォルダを確認しません（[管理画面の仕組み](reference/cms.md#contentapijs--画面から呼ばれる入口内容と公開)の「変わった分だけ処理する」）。Drive でフォルダ名や共有設定を手で変えても、その項目を管理画面で変更して公開するまでは、そのままになります。ファイルの管理は管理画面の中で行ってください。

### 「公開する」で全員の下書きが消える

公開すると、その時点の内容がサイトに出るのと同時に、保存されていた下書きがすべて消えます（`clearDrafts_`）。複数人で作業するときは、公開の前に声をかけ合う運用にしています。

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
```

`shoot.cjs` は、ログインから公開までのボタンをひととおり押し、崩れやすい画面を撮影します（`tools/preview/out/shots/`）。最後に次の内容を表示します。

- 画面が横にはみ出していないか（スマホ・タブレット・横向きの各サイズ）
- 画面の中で JavaScript のエラーが起きていないか
- 画面のスクリプト（`UiCore.html` など5つ）の関数のうち、一度も動かなかったもの（機能を足したら、ここに出ないよう撮影の手順も足す）
- Excel 読み込み用のライブラリ（SheetJS）を、整合性チェック付きで読み込めたか

見た目や動きを変えないはずの作業では、作業の前後の撮影結果を `tools/preview/compare.cjs` で比べます（画像は1画素ずつ、サーバーに送った内容も比べる）。使い方は [`cms/tools/preview/README.md`](../cms/tools/preview/README.md) の 3。公開サイトの撮影は [公開サイトを手元で作って確かめる（撮影）](#公開サイトを手元で作って確かめる撮影)。

### 公開サイトを手元で作って確かめる（撮影）

手元でビルドするには、サービスアカウントの鍵（JSON）が必要です。鍵は管理者から受け取り、**リポジトリの外**に置いてください（`.gitignore` で `*service-account*.json` などを除外していますが、念のため）。

```bash
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

**見本のデータでの撮影**：鍵がなくても、見本のデータ（`tools/screenshot/sample-content.json`）でサイトを作り、パソコン・タブレット・スマホ・スマホ横向きで撮影できます。Chrome と Node.js が必要です。見た目を変えないはずの作業では、作業の前後の画像を1画素ずつ比べます。

```bash
npm install --prefix tools/screenshot
node tools/screenshot/shoot.cjs                       # tools/screenshot/out/shots/ に保存
node tools/screenshot/compare.cjs --save <控えのフォルダ>   # 作業の前に控えを取る（リポジトリの外に置く）
node tools/screenshot/compare.cjs <控えのフォルダ>          # 作業のあとに比べる
```

撮影は、動きを減らす設定（`prefers-reduced-motion`）で行います。スライドショーなどの時間で動く表示が止まり、何度撮っても同じ画像になります。画面の横はみ出しと、画面のエラーも報告します。

### 公開してはいけないものの確認

このリポジトリは公開しています。`tests/test_repository_contents.py` は、次のものが入っていたら失敗します。コミットの前（`.githooks/pre-commit`）、プッシュのたび（`check.yml`）、サイトのビルドの前（`deploy.yml`）に動きます。

- メールアドレス（見本用に予約されたドメイン（`example.com`・`.test` など）と、サイトに載せている部の連絡先を除く）
- 管理画面の URL（Apps Script のウェブアプリの URL）
- 鍵（サービスアカウントの秘密鍵）
- 部員の情報が入りやすいファイル（スプレッドシートを書き出した Excel、clasp のログイン情報）

`.gitignore` でも、これらの種類のファイルと `tmp/`（作業用のメモや書き出したデータを置く場所）を除いています。

## 反映する

管理画面（GAS）と公開サイト（GitHub Pages）は、同じリポジトリにあっても反映は別々です。

### 管理画面を反映する

`clasp push` で送るのはテスト用の版だけです。部員が使っている本番の管理画面は、手順4のデプロイまで変わりません。

1. `cms/` で `clasp push` を実行する。`.claspignore` に書いたもの（`tests/`・`tools/`・README など）は送られない。
   ```bash
   cd cms
   clasp push
   ```
2. 確かめたいときは、GAS エディタの「デプロイ」→「デプロイをテスト」の URL（末尾が `/dev`）で、テスト用の版を開く。
3. GAS エディタで「デプロイ」→「デプロイを管理」を開き、本番のデプロイを選んで「編集」（鉛筆）を押す。
4. バージョンを「新バージョン」にして「デプロイ」を押す。

**確かめ方**：管理画面を再読み込みして、ふだんどおりログインできれば完了です。管理画面の URL は変わりません（部員は再読み込みするだけで新しい版になります）。「新しいデプロイ」を作ると URL が変わってしまうので、使いません。

### 管理画面を元に戻す

1. GAS エディタで「デプロイ」→「デプロイを管理」を開き、本番のデプロイの「編集」（鉛筆）を押す。
2. バージョンに**前の番号**を選んで「デプロイ」を押す。

コードを戻す必要はなく、すぐに元の版に戻ります。

### 公開サイトを反映する

push だけでは、サイトは作り直されません（ビルドのワークフローは「公開する」か手動実行でだけ動きます。理由は [設計の判断](decisions.md)）。

1. 変更をコミットして push する（その前に手元で確かめるなら、[公開サイトを手元で作って確かめる](#公開サイトを手元で作って確かめる撮影)）。
2. 次のどちらかで、サイトのビルドを起こす。
   - 管理画面で「公開する」を押す（内容が変わっていなくても、ビルドは起きる）
   - GitHub の「Actions」→「Build and Deploy Ryobi Site」→「Run workflow」

**確かめ方**：「Actions」のビルドが成功し、サイトが変わっていれば完了です。失敗したときは [困ったとき](troubleshooting.md)。

### 両方を変えるときの順番

管理画面（GAS）と公開サイト（GitHub Actions）は、同じリポジトリにあっても反映は別々です。スプレッドシートに列を足すなどの変更は、**古いコードでも新しいコードでも読めるように**作っています（列は末尾に足し、使わなくなった列もすぐには消さない）。そのため、ふつうはどちらを先に反映しても壊れません。保存する形を変えるときだけは順番が決まるので、その順番を書き残してください（例：2026年11月の更新履歴の形の変更は、サイトのコードを先に入れた）。
