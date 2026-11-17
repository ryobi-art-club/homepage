const { test } = require('node:test');
const assert = require('node:assert/strict');
const { runPair, NOW, EMAIL, hash } = require('./concurrent-server.js');

const request = { command: 'requestOtp', args: [EMAIL] };
const verify = code => ({ command: 'verifyOtp', args: [EMAIL, code] });
const report = message => ({ command: 'reportError', args: ['example', { operation: '公開', message }] });
const record = (extra = {}) => JSON.stringify({ email: EMAIL, codeHash: hash('123456'), expiresAt: NOW + 600000, attempts: 0, ...extra });
const otpSeed = extra => ({ ['otp:' + EMAIL]: record(), ...extra });
const hourKey = 'error_mail_count:' + Math.floor(NOW / 3600000);
const duplicateKey = message => 'error_mail:' + hash('公開\n' + message).slice(0, 40);

test('重なった確認コード要求も残り1回の枠を超えない', async () => {
  const result = await runPair([request, request], { seed: { ['otp_req:' + EMAIL]: '4' }, target: 'otp_req:' + EMAIL });
  assert.equal(result.mails.length, 1);
  assert.equal(result.values.get('otp_req:' + EMAIL), '5');
  assert.equal(result.results.filter(item => item.error).length, 1);
});

test('重なった誤入力をコード別・継続失敗の両方で数える', async () => {
  for (const [target, reads] of [['otp:' + EMAIL, 1], ['otp_fail:' + EMAIL, 2]]) {
    const result = await runPair([verify('000000'), verify('000000')], { seed: otpSeed(), target, reads });
    assert.equal(JSON.parse(result.values.get('otp:' + EMAIL)).attempts, 2);
    assert.equal(result.values.get('otp_fail:' + EMAIL), '2');
    assert.ok(result.results.every(item => /一致しません/.test(item.error)));
  }
});

test('同じ正しい確認コードから作れるセッションは1つだけ', async () => {
  const result = await runPair([verify('123456'), verify('123456')], { seed: otpSeed(), target: 'otp:' + EMAIL });
  assert.equal(result.results.filter(item => item.value?.sessionToken).length, 1);
  assert.equal([...result.values.keys()].filter(key => key.startsWith('session:') && key !== 'session:example').length, 1);
  assert.equal(result.values.has('otp:' + EMAIL), false);
});

test('照合中に取り直した新しいコードを古い状態で上書きしない', async () => {
  const result = await runPair([verify('000000'), request], { seed: otpSeed(), target: 'otp:' + EMAIL });
  assert.notEqual(JSON.parse(result.values.get('otp:' + EMAIL)).codeHash, hash('123456'));
});

test('停止へ移った実行だけがロックの外で管理者へ知らせる', async () => {
  const result = await runPair([verify('000000'), verify('000000')], {
    seed: otpSeed({ ['otp_fail:' + EMAIL]: '9' }), target: 'otp_fail:' + EMAIL, reads: 2
  });
  assert.equal(result.values.get('otp_fail:' + EMAIL), '10');
  assert.equal(result.mails.length, 1);
  assert.ok(result.results.every(item => /しばらくログインできません/.test(item.error)));
});

test('送信中の重複を通知済みとせず、同じ内容を1通だけ送る', async () => {
  const result = await runPair([report('見本'), report('見本')], { afterMail: true });
  assert.equal(result.mails.length, 1);
  assert.equal(result.results[0].value.notified, true);
  assert.deepEqual(result.results[1].value, { notified: false, reason: 'failed' });
});

test('時間当たりの残り1通を同時に予約できない', async () => {
  const result = await runPair([report('見本A'), report('見本B')], { seed: { [hourKey]: '4' }, target: hourKey });
  assert.equal(result.mails.length, 1);
  assert.equal(result.results.filter(item => item.value?.reason === 'limit').length, 1);
  const budget = JSON.parse(result.values.get(hourKey));
  assert.equal(budget.sent, 5);
  assert.equal(budget.pending.length, 0);
});

test('通知の送信失敗後は枠と重複の予約を返して再試行できる', async () => {
  const result = await runPair([report('見本'), report('見本')], { sequential: true, failMailA: true });
  assert.match(result.results[0].error, /送信失敗/);
  assert.equal(result.results[1].value.notified, true);
  assert.equal(result.mails.length, 1);
  assert.deepEqual(JSON.parse(result.values.get(hourKey)), { sent: 1, pending: [] });
});

test('古い送信の失敗で期限後の別の送信を取り消さない', async () => {
  const result = await runPair([report('見本'), report('見本')], { afterMail: true, advanceMs: 11 * 60000, failMailA: true });
  assert.equal(result.results[1].value.notified, true);
  assert.equal(result.values.get(duplicateKey('見本')), '1');
  assert.deepEqual(JSON.parse(result.values.get(hourKey)), { sent: 1, pending: [] });
});

test('遅れて完了した送信も別の予約を確定したり重複計上したりしない', async () => {
  const result = await runPair([report('見本'), report('見本')], { afterMail: true, advanceMs: 11 * 60000 });
  assert.equal(result.mails.length, 2);
  assert.equal(result.values.get(duplicateKey('見本')), '1');
  assert.deepEqual(JSON.parse(result.values.get(hourKey)), { sent: 1, pending: [] });
});

test('登録の有無で重なった誤入力の返答や制限を変えない', async () => {
  const messages = [];
  for (const email of [EMAIL, 'stranger@example.test']) {
    const command = { command: 'verifyOtp', args: [email, '000000'] };
    const result = await runPair([command, command], {
      seed: { ['otp:' + email]: record({ email }) }, target: 'otp_fail:' + email, reads: 2
    });
    assert.equal(result.values.get('otp_fail:' + email), '2');
    assert.equal(result.mails.length, 0);
    messages.push(result.results.map(item => item.error));
  }
  assert.deepEqual(messages[0], messages[1]);
});

test('時刻が次の時間帯へ進んでも失敗した枠だけを解除する', async () => {
  const result = await runPair([report('見本A'), report('見本B')], { afterMail: true, advanceMs: 3600000, failMailA: true });
  const nextKey = 'error_mail_count:' + (Math.floor(NOW / 3600000) + 1);
  assert.equal(result.results[1].value.notified, true);
  assert.equal(JSON.parse(result.values.get(nextKey)).sent, 1);
});

test('保存中にロックを取れなければ状態を変えず送信もしない', async () => {
  const result = await runPair([request, report('見本')], { blocked: true });
  assert.ok(result.results.every(item => /Lock timeout/.test(item.error)));
  assert.equal(result.mails.length, 0);
  assert.equal(result.values.size, 1);
  assert.equal(result.releases, 0);
});

test('キャッシュの例外でもロックを解放し次の処理を進められる', async () => {
  const result = await runPair([request, request], { sequential: true, throwPut: 'otp_req:' + EMAIL });
  assert.match(result.results[0].error, /書込失敗/);
  assert.equal(result.results[1].value.ok, true);
  assert.equal(result.owner, null);
});

test('期限切れと試行上限のコードもロック内で消す', async () => {
  for (const extra of [{ expiresAt: NOW - 1 }, { attempts: 5 }]) {
    const result = await runPair([verify('123456'), verify('123456')], { sequential: true, seed: { ['otp:' + EMAIL]: record(extra) } });
    assert.equal(result.values.has('otp:' + EMAIL), false);
    assert.ok(result.results.every(item => item.error));
    assert.equal(result.owner, null);
  }
});

test('送信枠不足でも予約を残さない', async () => {
  const result = await runPair([report('見本A'), report('見本B')], { sequential: true, quota: 20 });
  assert.ok(result.results.every(item => item.value.reason === 'limit'));
  assert.equal(result.mails.length, 0);
  assert.deepEqual(JSON.parse(result.values.get(hourKey)), { sent: 0, pending: [] });
});
