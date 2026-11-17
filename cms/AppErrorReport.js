// 画面で起きたシステム側のエラーを、管理者にメールで知らせる

const ERROR_MAIL_HOURLY_LIMIT = 5;

const ERROR_MAIL_DUPLICATE_SECONDS = 6 * 60 * 60;

const ERROR_MAIL_QUOTA_RESERVE = 20;

// 実行が途切れた予約は、GAS の実行時間上限より長い10分で再利用できる
const ERROR_MAIL_PENDING_SECONDS = 10 * 60;

// 管理者（ERROR_NOTIFY_EMAIL、カンマ区切り）にメールする。送れなかったときは理由（not_configured・limit）を返す。
// getConfig_ 自体が失敗している場合も送れるように、スクリプト プロパティを直接読む。
// 1日のメールの上限は確認コードと共有なので、確認コードの分を残しておく
function sendAdminMail_(subject, body) {
  const recipient = String(PropertiesService.getScriptProperties().getProperty('ERROR_NOTIFY_EMAIL') || '').trim();
  if (!recipient) return 'not_configured';
  if (MailApp.getRemainingDailyQuota() <= ERROR_MAIL_QUOTA_RESERVE) return 'limit';
  MailApp.sendEmail({ to: recipient, subject: '【凌美会 管理画面】' + subject, body: body });
  return '';
}

// 画面で起きたシステム側のエラーを管理者に知らせる。同じエラーは6時間に1回、全体で1時間に5通まで
function reportError(sessionToken, report) {
  const session = requireSession_(sessionToken);
  const item = normalizeErrorReport_(report);
  console.error('Client error report', JSON.stringify(Object.assign({ reporter: session.email }, item)));
  const cache = CacheService.getScriptCache();
  const duplicateKey = 'error_mail:' + sha256Hex_(item.operation + '\n' + item.message).slice(0, 40);
  const reservation = withCacheLock_(() => reserveErrorMail_(cache, duplicateKey));
  if (reservation.response) return reservation.response;

  let failure;
  try {
    failure = sendAdminMail_('エラー: ' + item.operation + '（' + item.id + '）', buildErrorMailBody_(item, session));
  } catch (error) {
    withCacheLock_(() => finishErrorMail_(cache, reservation, false));
    throw error;
  }
  withCacheLock_(() => finishErrorMail_(cache, reservation, !failure));
  return failure ? { notified: false, reason: failure } : { notified: true };
}

// 送信済み数と予約を同じ値に置き、古い送信の失敗で別の予約を減らさない
function readErrorMailBudget_(cache, hourKey) {
  const value = JSON.parse(cache.get(hourKey) || '0');
  // 以前の版が保存した送信済み数も読む
  return typeof value === 'number' ? { sent: value, pending: [] } : value;
}

function reserveErrorMail_(cache, duplicateKey) {
  const now = Date.now();
  const duplicate = cache.get(duplicateKey);
  if (duplicate === '1') return { response: { notified: true, duplicate: true } };
  if (duplicate && JSON.parse(duplicate).expiresAt > now) {
    return { response: { notified: false, reason: 'failed' } };
  }
  const hourKey = 'error_mail_count:' + Math.floor(now / 3600000);
  const budget = readErrorMailBudget_(cache, hourKey);
  budget.pending = budget.pending.filter(item => item.expiresAt > now);
  if (budget.sent + budget.pending.length >= ERROR_MAIL_HOURLY_LIMIT) {
    return { response: { notified: false, reason: 'limit' } };
  }
  const reservation = { id: Utilities.getUuid(), expiresAt: now + ERROR_MAIL_PENDING_SECONDS * 1000,
    hourKey, duplicateKey };
  budget.pending.push({ id: reservation.id, expiresAt: reservation.expiresAt });
  cache.put(hourKey, JSON.stringify(budget), 3600);
  cache.put(duplicateKey, JSON.stringify({ id: reservation.id, expiresAt: reservation.expiresAt }), ERROR_MAIL_PENDING_SECONDS);
  return reservation;
}

function finishErrorMail_(cache, reservation, sent) {
  const budget = readErrorMailBudget_(cache, reservation.hourKey);
  const position = budget.pending.findIndex(item => item.id === reservation.id);
  if (position >= 0) {
    budget.pending.splice(position, 1);
    if (sent) budget.sent += 1;
    cache.put(reservation.hourKey, JSON.stringify(budget), 3600);
  }
  const raw = cache.get(reservation.duplicateKey);
  if (!raw || raw === '1' || JSON.parse(raw).id !== reservation.id) return;
  if (sent) cache.put(reservation.duplicateKey, '1', ERROR_MAIL_DUPLICATE_SECONDS);
  else cache.remove(reservation.duplicateKey);
}

function normalizeErrorReport_(report) {
  const source = report && typeof report === 'object' ? report : {};
  const field = (value, limit, singleLine) => {
    const text = String(value == null ? '' : value).trim();
    return (singleLine ? text.replace(/\s+/g, ' ') : text).slice(0, limit);
  };
  return {
    id: field(source.id, 40, true) || '-',
    time: field(source.time, 40, true),
    operation: field(source.operation, 60, true) || '操作',
    message: field(source.message, 2000, false) || '不明なエラー',
    panel: field(source.panel, 60, true),
    userAgent: field(source.userAgent, 300, true)
  };
}

function buildErrorMailBody_(item, session) {
  return [
    '凌美会 管理画面でエラーが発生しました。',
    '',
    'エラーID: ' + item.id,
    '日時: ' + item.time,
    '操作: ' + item.operation,
    '内容: ' + item.message,
    '画面: ' + (item.panel || '-'),
    '報告者: ' + (session.name || '-') + ' <' + session.email + '>',
    'ブラウザ: ' + (item.userAgent || '-'),
    '',
    '同じ操作・同じ内容のエラーは6時間に1回だけ通知します。',
    'Apps Script エディタの「実行数」にも同じ内容が記録されています。'
  ].join('\n');
}
