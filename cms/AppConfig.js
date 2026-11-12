// 設定：スクリプト プロパティとシートの名前

const CONTENT_SHEETS = {
  changeLog: 'ChangeLog',
  publishedState: '_PublishedState',
  drafts: '_Drafts',
  adminLog: '_AdminLog',
  proofreadChecked: '_ProofreadChecked'
};

const ALLOWLIST_SHEET_NAME = 'allowlist';

// 管理画面を動かしながら変えることがある設定の、今の値。スクリプト プロパティに同じ名前で値を書くと、
// デプロイし直さずにそちらが使われる。デプロイのときに変えればよい値は、使うファイルの先頭の定数にする
const CONFIG_DEFAULTS = {
  // 部員から「すぐ切れる」「長すぎる」と言われたときに変える
  SESSION_TTL_MINUTES: '180',
  // モデルの提供は急に終わることがある
  GEMINI_MODEL: 'gemini-3.1-flash-lite',
  // 'trash' なら公開のあとの片付けの対象を Drive のゴミ箱に入れる。それ以外（例：'log'）は _AdminLog に一覧を書くだけ。
  // 片付けがおかしいときに、すぐ止められるように
  CLEANUP_MODE: 'trash'
};

// スクリプト プロパティに必ず置く値（作り直すと変わる ID）。ほかに GitHub App の値・Gemini の API キーもプロパティから読む
const CONFIG_REQUIRED = [
  'CONTENT_SPREADSHEET_ID',
  'ALLOWLIST_SPREADSHEET_ID',
  'ROOT_RECRUIT_FOLDER_ID',
  'ROOT_ACTIVITY_FOLDER_ID',
  'ROOT_EXHIBITION_FOLDER_ID',
  'ROOT_REQUEST_FOLDER_ID'
];

function getConfig_() {
  const props = PropertiesService.getScriptProperties();
  const read = (key) => String(props.getProperty(key) || CONFIG_DEFAULTS[key] || '').trim();
  const config = {};
  CONFIG_REQUIRED.concat(Object.keys(CONFIG_DEFAULTS), ['GH_APP_ID', 'GH_INSTALLATION_ID', 'GEMINI_API_KEY'])
    .forEach((key) => { config[key] = read(key); });
  const missing = CONFIG_REQUIRED.filter((key) => !config[key]);
  if (missing.length) {
    throw new Error('Script Properties が不足しています: ' + missing.join(', '));
  }
  config.SESSION_TTL_MINUTES = parseInt(config.SESSION_TTL_MINUTES, 10);
  config.CLEANUP_MODE = config.CLEANUP_MODE.toLowerCase();
  config.GH_PRIVATE_KEY = String(props.getProperty('GH_PRIVATE_KEY') || '').replace(/\\n/g, '\n');
  return config;
}
