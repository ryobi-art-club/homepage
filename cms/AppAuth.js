// ログイン：確認コード・許可リスト・セッション

// 確認コードの有効期限（分）
const OTP_TTL_MINUTES = 10;

// 確認コードの送信は、1つのアドレスにつき6時間に5通まで（1日でも最大20通）。部員のアドレスを知っている人が送らせ続けても、
// Apps Script の1日のメールの上限（無料のアカウントで100通）を1つのアドレスでは使い切れないようにする。
// 期間は CacheService が覚えておける最長の6時間
const OTP_REQUEST_LIMIT = 5;

const OTP_REQUEST_WINDOW_SECONDS = 6 * 60 * 60;

// 確認コードの外れの数は、コードを取り直しても数え続ける。上限に達したら、そのメールアドレスのログインを止めて管理者に知らせる
// （コードを取り直しながら当て続けられないように）。期間は CacheService が覚えておける最長の6時間
const OTP_FAILURE_LIMIT = 10;

const OTP_FAILURE_WINDOW_SECONDS = 6 * 60 * 60;

const OTP_LOCKED_MESSAGE = '確認コードの入力が続けて違っていたため、しばらくログインできません。時間をおいてから試すか、管理者に連絡してください。';

// 許可リストにないアドレスでは、メールを送る代わりに、最近メールを送るのにかかった時間のどれか1つだけ待つ
// （答えが返るまでの時間で見分けられないように）。記録がないうちは1秒前後
const OTP_MAIL_TIMES_KEPT = 20;

const OTP_MAIL_DEFAULT_MS = 1000;

// 許可リストにないアドレスにも、コードを作って覚えておき、送ったときと同じ答えを返す（メールを送らないだけ）。
// 違うコードを入れたときの表示・回数の上限・ログインを止める動き・答えが返るまでの時間も同じになる。
// 外の人が、部員のアドレスかどうかを確かめられないようにするため
function requestOtp(email) {
  const normalizedEmail = normalizeEmail_(email);
  if (!normalizedEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
    throw new Error('メールアドレスの形式が正しくありません。');
  }
  const cache = CacheService.getScriptCache();
  if (isOtpLocked_(cache, normalizedEmail)) throw new Error(OTP_LOCKED_MESSAGE);
  const reqCountKey = 'otp_req:' + normalizedEmail;
  const reqCount = parseInt(cache.get(reqCountKey) || '0', 10);
  if (reqCount >= OTP_REQUEST_LIMIT) {
    throw new Error('確認コードの送信回数が上限に達しました。しばらく時間をおいてから再試行してください。');
  }
  cache.put(reqCountKey, String(reqCount + 1), OTP_REQUEST_WINDOW_SECONDS);

  const code = generateOtpCode_();
  const record = {
    email: normalizedEmail,
    codeHash: sha256Hex_(code),
    expiresAt: Date.now() + OTP_TTL_MINUTES * 60 * 1000,
    attempts: 0
  };
  cache.put('otp:' + normalizedEmail, JSON.stringify(record), OTP_TTL_MINUTES * 60);

  if (readAllowedUser_(normalizedEmail)) {
    const started = Date.now();
    MailApp.sendEmail({
      to: normalizedEmail,
      subject: '【凌美会】確認コード',
      htmlBody: [
        '<p>凌美会の管理画面にログインするための確認コードです。</p>',
        '<p style="font-size:28px; font-weight:700; letter-spacing:0.2em;">' + code + '</p>',
        '<p>このコードの有効期限は ' + OTP_TTL_MINUTES + ' 分です。</p>'
      ].join('')
    });
    rememberOtpMailTime_(cache, Date.now() - started);
  } else {
    Utilities.sleep(pickOtpMailTime_(cache));
  }
  return { ok: true, email: maskEmail_(normalizedEmail), expiresInMinutes: OTP_TTL_MINUTES };
}

function verifyOtp(email, code) {
  const config = getConfig_();
  const normalizedEmail = normalizeEmail_(email);
  const cache = CacheService.getScriptCache();
  if (isOtpLocked_(cache, normalizedEmail)) throw new Error(OTP_LOCKED_MESSAGE);
  const raw = cache.get('otp:' + normalizedEmail);
  if (!raw) {
    throw new Error('確認コードの有効期限が切れています。もう一度取得してください。');
  }
  const record = JSON.parse(raw);
  if (Date.now() > record.expiresAt) {
    cache.remove('otp:' + normalizedEmail);
    throw new Error('確認コードの有効期限が切れています。');
  }
  if (record.attempts >= 5) {
    cache.remove('otp:' + normalizedEmail);
    throw new Error('確認コードの入力回数が上限に達しました。');
  }
  /* 許可リストにないアドレスは、コードが当たっても通さない（違うコードと同じ扱い） */
  const allowed = readAllowedUser_(normalizedEmail);
  if (!allowed || sha256Hex_(String(code || '').trim()) !== record.codeHash) {
    record.attempts += 1;
    cache.put('otp:' + normalizedEmail, JSON.stringify(record), Math.max(60, Math.floor((record.expiresAt - Date.now()) / 1000)));
    if (countOtpFailure_(cache, normalizedEmail)) throw new Error(OTP_LOCKED_MESSAGE);
    throw new Error('確認コードが一致しません。');
  }

  cache.remove('otp:' + normalizedEmail);
  cache.remove('otp_req:' + normalizedEmail);
  cache.remove('otp_fail:' + normalizedEmail);
  const sessionToken = Utilities.getUuid() + '-' + Utilities.getUuid();
  cache.put('session:' + sessionToken, JSON.stringify({
    email: normalizedEmail,
    name: allowed.name || normalizedEmail,
    issuedAt: Date.now()
  }), config.SESSION_TTL_MINUTES * 60);

  return {
    ok: true,
    sessionToken: sessionToken,
    email: normalizedEmail,
    name: allowed.name || normalizedEmail,
    expiresInMinutes: config.SESSION_TTL_MINUTES
  };
}

// 6桁の確認コード。Math.random は予測されにくさを保証しないので、ランダムな UUID の先頭12桁（48ビット）から作る
function generateOtpCode_() {
  return String(100000 + parseInt(Utilities.getUuid().replace(/-/g, '').slice(0, 12), 16) % 900000);
}

function rememberOtpMailTime_(cache, ms) {
  const times = JSON.parse(cache.get('otp_mail_ms') || '[]').concat([ms]).slice(-OTP_MAIL_TIMES_KEPT);
  cache.put('otp_mail_ms', JSON.stringify(times), OTP_FAILURE_WINDOW_SECONDS);
}

function pickOtpMailTime_(cache) {
  const times = JSON.parse(cache.get('otp_mail_ms') || '[]');
  if (!times.length) return Math.round(OTP_MAIL_DEFAULT_MS * (0.8 + Math.random() * 0.4));
  return times[Math.floor(Math.random() * times.length)];
}

function isOtpLocked_(cache, email) {
  return parseInt(cache.get('otp_fail:' + email) || '0', 10) >= OTP_FAILURE_LIMIT;
}

// 外れを1つ数える。ちょうど上限に達したら、今のコードを無効にして true を返す。
// 管理者に知らせるのは部員のアドレスのときだけ（許可リストにないアドレスを次々に試されて、
// 管理者へのメールで1日のメールの上限を使い切られないように。外から見える動きはどちらも同じ）
function countOtpFailure_(cache, email) {
  const failures = parseInt(cache.get('otp_fail:' + email) || '0', 10) + 1;
  cache.put('otp_fail:' + email, String(failures), OTP_FAILURE_WINDOW_SECONDS);
  if (failures < OTP_FAILURE_LIMIT) return false;
  cache.remove('otp:' + email);
  if (readAllowedUser_(email)) sendAdminMail_('確認コードの入力が続けて違っていました',
    email + ' で、確認コードの入力が ' + OTP_FAILURE_LIMIT + ' 回違っていたため、このメールアドレスのログインを最長6時間止めました。\n' +
    '本人が入力を間違えただけなら、時間をおけばまたログインできます。心当たりがないときは、誰かがこのメールアドレスでログインしようとしている可能性があります。');
  return true;
}

function requireSession_(sessionToken) {
  const raw = CacheService.getScriptCache().get('session:' + String(sessionToken || '').trim());
  if (!raw) {
    throw new Error('セッションが切れています。もう一度認証してください。');
  }
  return JSON.parse(raw);
}

function readAllowedUser_(email) {
  const config = getConfig_();
  const sheet = SpreadsheetApp.openById(config.ALLOWLIST_SPREADSHEET_ID).getSheetByName(ALLOWLIST_SHEET_NAME);
  if (!sheet) throw new Error('allowlist シートが見つかりません。');
  const values = sheet.getDataRange().getValues();
  if (!values.length) return null;
  const header = values[0].map((v) => String(v || '').trim());
  const nameIndex = header.indexOf('name');
  const emailIndex = header.indexOf('email');
  if (emailIndex < 0) throw new Error('allowlist シートの1行目に email 列が必要です。');
  for (let rowIndex = 1; rowIndex < values.length; rowIndex += 1) {
    const rowEmail = normalizeEmail_(values[rowIndex][emailIndex]);
    if (rowEmail && rowEmail === email) {
      return {
        name: nameIndex >= 0 ? String(values[rowIndex][nameIndex] || '').trim() : '',
        email: rowEmail
      };
    }
  }
  return null;
}

function normalizeEmail_(value) {
  return String(value || '').trim().toLowerCase();
}

function maskEmail_(email) {
  const parts = String(email).split('@');
  if (parts.length !== 2) return email;
  const user = parts[0];
  const maskedUser = user.length <= 2 ? user[0] + '*' : user.slice(0, 2) + '*'.repeat(Math.max(1, user.length - 2));
  return maskedUser + '@' + parts[1];
}
