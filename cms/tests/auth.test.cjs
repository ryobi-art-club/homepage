// ログイン：確認コードは取り直しても外れを数え続け、上限で止めて管理者に知らせる
const vm = require('node:vm');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const { test } = require('node:test');
const sources = require('./files.cjs');

function setup() {
  const store = new Map();
  const mails = [];
  const sleeps = [];
  const ctx = vm.createContext({
    console: { error() {}, warn() {} },
    CacheService: {
      getScriptCache: () => ({
        get: key => (store.has(key) ? store.get(key) : null),
        put: (key, value) => store.set(key, value),
        remove: key => store.delete(key)
      })
    },
    PropertiesService: { getScriptProperties: () => ({ getProperty: key => (key === 'ERROR_NOTIFY_EMAIL' ? 'admin@example.com' : null) }) },
    MailApp: { sendEmail: mail => mails.push(mail), getRemainingDailyQuota: () => 100 },
    Utilities: { getUuid: () => crypto.randomUUID(), sleep: ms => sleeps.push(ms) }
  });
  sources.loadServer(ctx);
  ctx.getConfig_ = () => ({ OTP_TTL_MINUTES: 10, SESSION_TTL_MINUTES: 30 });
  ctx.readAllowedUser_ = email => (email === 'member@example.com' ? { name: '部員', email } : null);
  ctx.sha256Hex_ = text => crypto.createHash('sha256').update(text).digest('hex');
  const lastCode = () => mails.filter(mail => mail.to === 'member@example.com').pop().htmlBody.match(/>(\d{6})</)[1];
  return { ctx, mails, store, sleeps, lastCode };
}

test('the code has six digits and a correct code opens a session', () => {
  const { ctx, lastCode } = setup();
  ctx.requestOtp('Member@Example.com');
  assert.match(lastCode(), /^[1-9]\d{5}$/);
  assert.ok(ctx.verifyOtp('member@example.com', lastCode()).sessionToken);
});

test('wrong codes are counted across new codes; the tenth one stops login and tells the administrator once', () => {
  const { ctx, mails, lastCode } = setup();
  const wrong = () => String((Number(lastCode()) % 900000) + 100001);
  let failures = 0;
  for (let round = 0; round < 2; round += 1) {
    ctx.requestOtp('member@example.com');
    for (let i = 0; i < 5; i += 1) {
      failures += 1;
      assert.throws(() => ctx.verifyOtp('member@example.com', wrong()), failures < 10 ? /一致しません/ : /しばらくログインできません/);
    }
  }
  assert.throws(() => ctx.requestOtp('member@example.com'), /しばらくログインできません/);
  assert.throws(() => ctx.verifyOtp('member@example.com', '123456'), /しばらくログインできません/);
  const notices = mails.filter(mail => mail.to === 'admin@example.com');
  assert.equal(notices.length, 1);
  assert.match(notices[0].subject, /確認コードの入力が続けて違っていました/);
  assert.match(notices[0].body, /member@example\.com/);
});

test('a correct code clears the count of wrong ones', () => {
  const { ctx, store, lastCode } = setup();
  ctx.requestOtp('member@example.com');
  assert.throws(() => ctx.verifyOtp('member@example.com', '000000'), /一致しません/);
  ctx.verifyOtp('member@example.com', lastCode());
  assert.equal(store.has('otp_fail:member@example.com'), false);
});

test('an address not on the allowlist gets the same answer and the same limit, but no mail', () => {
  const { ctx, mails } = setup();
  const member = ctx.requestOtp('member@example.com');
  const stranger = ctx.requestOtp('stranger@example.com');
  assert.deepEqual(Object.keys(stranger).sort(), Object.keys(member).sort());
  assert.equal(stranger.ok, true);
  assert.equal(mails.filter(mail => mail.to === 'stranger@example.com').length, 0);
  for (let i = 1; i < 5; i += 1) ctx.requestOtp('stranger@example.com');
  assert.throws(() => ctx.requestOtp('stranger@example.com'), /送信回数が上限/);
});

test('an address not on the allowlist answers a code the same way as a member, is never let in, and does not mail the administrator', () => {
  const { ctx, mails, store } = setup();
  ctx.requestOtp('member@example.com');
  ctx.requestOtp('stranger@example.com');
  assert.throws(() => ctx.verifyOtp('member@example.com', '000000'), /一致しません/);
  assert.throws(() => ctx.verifyOtp('stranger@example.com', '000000'), /一致しません/);
  // コードが当たっても通さない
  const record = JSON.parse(store.get('otp:stranger@example.com'));
  record.codeHash = ctx.sha256Hex_('123456');
  store.set('otp:stranger@example.com', JSON.stringify(record));
  assert.throws(() => ctx.verifyOtp('stranger@example.com', '123456'), /一致しません/);
  // 止まるまでの動きも同じで、管理者には知らせない（ここまでで2回違えている。あと8回で10回）
  for (let i = 0; i < 3; i += 1) assert.throws(() => ctx.verifyOtp('stranger@example.com', '000000'), /一致しません/);
  ctx.requestOtp('stranger@example.com');
  for (let i = 0; i < 4; i += 1) assert.throws(() => ctx.verifyOtp('stranger@example.com', '000000'), /一致しません/);
  assert.throws(() => ctx.verifyOtp('stranger@example.com', '000000'), /しばらくログインできません/);
  assert.throws(() => ctx.requestOtp('stranger@example.com'), /しばらくログインできません/);
  assert.equal(mails.filter(mail => mail.to === 'admin@example.com').length, 0);
});

test('for an address not on the allowlist, the answer takes about as long as sending a mail', () => {
  const { ctx, sleeps, store } = setup();
  ctx.requestOtp('stranger@example.com');
  assert.ok(sleeps[0] >= 800 && sleeps[0] <= 1200, 'about one second before any mail has been sent');
  store.set('otp_mail_ms', JSON.stringify([1500, 1700]));
  ctx.requestOtp('member@example.com');
  assert.equal(JSON.parse(store.get('otp_mail_ms')).length, 3, 'the time to send a mail is remembered');
  ctx.requestOtp('other@example.com');
  assert.ok(JSON.parse(store.get('otp_mail_ms')).includes(sleeps[1]), 'waits as long as one of the remembered sends');
  assert.equal(sleeps.length, 2, 'members do not wait');
});
