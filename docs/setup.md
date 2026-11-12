# 一から作り直す手順

Google のアカウントや GitHub の設定を失ったときなど、システムを最初から用意し直すときに、上から順に行います。

1. **スプレッドシートを2つ作る**：コンテンツ用（中は空でよい。シートは自動で作られる）と、許可リスト用（`allowlist` シートに `name` / `email` の見出しと、最初の管理者の行を書く）。
2. **Drive にルートフォルダを4つ作る**：新歓・活動記録・展示会・ご依頼。
3. **GAS プロジェクトを用意して、コードを送る**：`clasp login` のあと、`cms/.clasp.json` の `scriptId` を自分のプロジェクトの ID にして、`cms/` で `clasp push`。
4. **スクリプト プロパティを設定する**（[Script Properties（設定値）](reference/cms.md#script-properties設定値)）。
5. **ウェブアプリとしてデプロイする**：GAS エディタの「デプロイ」→「新しいデプロイ」→ 種類「ウェブアプリ」。実行するユーザーは「自分」、アクセスできるユーザーは「Google アカウントを持つ全員」。表示された URL が管理画面の URL です。初回は権限の許可を求められます。
6. **サービスアカウントを作る**：[Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作り、「Google Sheets API」と「Google Drive API」を有効にする。サービスアカウントを作り、鍵（JSON）を作ってダウンロードする。
7. **サービスアカウントに共有する**：コンテンツ用スプレッドシートと Drive の4つのルートフォルダを、サービスアカウントのメールアドレスに「閲覧者」で共有する。
8. **GitHub Pages を有効にする**：リポジトリの「Settings」→「Pages」で、Source を「GitHub Actions」にする。
9. **シークレットを登録する**（[GitHub Actions とシークレット](reference/site.md#github-actions-とシークレット)）。
10. **GitHub App を用意する**：組織の「Settings」→「Developer settings」→「GitHub Apps」で App を作り（権限は `Actions: Read and write`）、このリポジトリにインストールする。App ID、インストール ID、秘密鍵をスクリプト プロパティに設定する。
11. **動かしてみる**：管理画面で「公開する」を押し、Actions が成功してサイトが表示されるか確かめる。管理画面の URL は部員に直接伝える（リポジトリには書かない）。
