// 公開したあと、サイトのビルド（GitHub Actions）を起動する

// 起動するリポジトリ・ワークフロー・ブランチ（このリポジトリ自身）。ワークフローの名前を変えたら、ここも一緒に直す
const GH_OWNER = 'ryobi-art-club';

const GH_REPO = 'homepage';

const GH_WORKFLOW_FILE = 'deploy.yml';

const GH_BRANCH = 'main';

// 公開サイトの URL（管理画面の「サイトを開く」のリンク先）
const SITE_URL = 'https://' + GH_OWNER + '.github.io/' + GH_REPO + '/';

function dispatchGithubWorkflow_() {
  const token = getGithubToken_();
  const url = 'https://api.github.com/repos/' + encodeURIComponent(GH_OWNER) + '/' + encodeURIComponent(GH_REPO) + '/actions/workflows/' + encodeURIComponent(GH_WORKFLOW_FILE) + '/dispatches';
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    muteHttpExceptions: true,
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    },
    payload: JSON.stringify({ ref: GH_BRANCH })
  });
  const code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error('GitHub Actions の起動に失敗しました: ' + response.getContentText());
  }
  return {
    actionsUrl: 'https://github.com/' + GH_OWNER + '/' + GH_REPO + '/actions/workflows/' + GH_WORKFLOW_FILE
  };
}

function getGithubToken_() {
  const config = getConfig_();
  if (!config.GH_APP_ID || !config.GH_INSTALLATION_ID || !config.GH_PRIVATE_KEY) {
    throw new Error('GitHub App 用の Script Properties が不足しています。');
  }
  const jwt = createGithubAppJwt_(config.GH_APP_ID, config.GH_PRIVATE_KEY);
  const response = UrlFetchApp.fetch('https://api.github.com/app/installations/' + encodeURIComponent(config.GH_INSTALLATION_ID) + '/access_tokens', {
    method: 'post',
    muteHttpExceptions: true,
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer ' + jwt,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    },
    payload: JSON.stringify({})
  });
  const code = response.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error('GitHub App の installation token 取得に失敗しました: ' + response.getContentText());
  }
  const data = JSON.parse(response.getContentText());
  return data.token;
}

function createGithubAppJwt_(appId, privateKey) {
  const nowSeconds = Math.floor(Date.now() / 1000);
  const header = {
    alg: 'RS256',
    typ: 'JWT'
  };
  const payload = {
    iat: nowSeconds - 60,
    exp: nowSeconds + (9 * 60),
    iss: appId
  };
  const encodedHeader = base64UrlEncodeString_(JSON.stringify(header));
  const encodedPayload = base64UrlEncodeString_(JSON.stringify(payload));
  const unsigned = encodedHeader + '.' + encodedPayload;
  const signatureBytes = Utilities.computeRsaSha256Signature(unsigned, privateKey);
  return unsigned + '.' + base64UrlEncodeBytes_(signatureBytes);
}

function base64UrlEncodeString_(value) {
  return Utilities.base64EncodeWebSafe(value, Utilities.Charset.UTF_8).replace(/=+$/, '');
}

function base64UrlEncodeBytes_(bytes) {
  return Utilities.base64EncodeWebSafe(bytes).replace(/=+$/, '');
}
