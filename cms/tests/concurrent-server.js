/* 独立した実行をワーカーで動かし、同期的なキャッシュ呼出しとロックの待ちを親側で制御する。Googleには接続しない。 */
const { Worker, isMainThread, parentPort, workerData } = require('node:worker_threads');
const vm = require('node:vm');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const sources = require('./files.cjs');

const NOW = Date.parse('2026-11-17T03:00:00Z');
const EMAIL = 'member@example.test';
const hash = value => crypto.createHash('sha256').update(value).digest('hex');

if (!isMainThread) {
  const state = new Int32Array(workerData.buffer, 0, 2);
  const bytes = new Uint8Array(workerData.buffer, 8);
  const rpc = (operation, ...args) => {
    parentPort.postMessage({ operation, args });
    Atomics.wait(state, 0, 0);
    const response = JSON.parse(Buffer.from(bytes.subarray(0, state[1])).toString('utf8'));
    Atomics.store(state, 0, 0);
    if (response.error) throw new Error(response.error);
    return response.value;
  };
  class Clock extends Date {
    constructor(...args) { super(...(args.length ? args : [NOW])); }
    static now() { return rpc('now'); }
  }
  const ctx = vm.createContext({
    Date: Clock,
    console: { error() {}, warn() {}, log() {} },
    CacheService: { getScriptCache: () => ({
      get: key => rpc('get', key), put: (key, value, ttl) => rpc('put', key, value, ttl),
      remove: key => rpc('remove', key)
    }) },
    LockService: { getScriptLock: () => ({
      waitLock: ms => rpc('lock', ms), tryLock: ms => rpc('tryLock', ms), releaseLock: () => rpc('release')
    }) },
    Utilities: { getUuid: () => crypto.randomUUID(), sleep: ms => rpc('sleep', ms) },
    PropertiesService: { getScriptProperties: () => ({ getProperty: key => rpc('property', key) }) },
    MailApp: { getRemainingDailyQuota: () => rpc('quota'), sendEmail: mail => rpc('mail', mail) }
  });
  sources.loadServer(ctx);
  ctx.sha256Hex_ = hash;
  ctx.getConfig_ = () => ({ SESSION_TTL_MINUTES: 30 });
  ctx.readAllowedUser_ = email => rpc('allowed', email);
  parentPort.on('message', ({ command, args }) => {
    try { parentPort.postMessage({ done: true, value: ctx[command](...args) }); }
    catch (error) { parentPort.postMessage({ done: true, error: error.message }); }
  });
} else {
  async function runPair(commands, options = {}) {
    const values = new Map(Object.entries({
      ['session:example']: JSON.stringify({ email: EMAIL, name: '見本' }),
      ...(options.seed || {})
    }));
    const expirations = new Map();
    const mails = [];
    const results = [];
    const waiters = [];
    const buffers = commands.map(() => new SharedArrayBuffer(256 * 1024));
    const workers = buffers.map(buffer => new Worker(__filename, { workerData: { buffer } }));
    let now = NOW;
    let owner = options.blocked ? '保存処理' : null;
    let startedB = false;
    let reads = 0;
    let pausedRead;
    let pausedMail;
    let putFailed = false;
    let releases = 0;
    const read = key => {
      if ((expirations.get(key) || Infinity) <= now) values.delete(key);
      return values.get(key) ?? null;
    };
    const reply = (index, value = null, error) => {
      const data = Buffer.from(JSON.stringify(error ? { error } : { value }));
      new Uint8Array(buffers[index], 8).set(data);
      const state = new Int32Array(buffers[index], 0, 2);
      state[1] = data.length;
      Atomics.store(state, 0, 1);
      Atomics.notify(state, 0);
    };
    const startB = () => {
      if (!startedB) { startedB = true; workers[1].postMessage(commands[1]); }
    };
    let timer;
    try {
      return await new Promise((resolve, reject) => {
        timer = setTimeout(() => reject(new Error('見本の実行が終了しません')), 15000);
        workers.forEach((worker, index) => {
          worker.on('error', reject);
          worker.on('message', message => {
            try {
              if (message.done) {
                results[index] = message;
                if (index === 0 && options.sequential) startB();
                if (index === 1 && pausedRead) { const resume = pausedRead; pausedRead = null; resume(); }
                if (index === 1 && pausedMail) { const resume = pausedMail; pausedMail = null; resume(); }
                if (results[0] && results[1]) resolve({ results, values, mails, releases, owner });
                return;
              }
              const { operation, args } = message;
              if (operation === 'now') return reply(index, now);
              if (operation === 'lock' || operation === 'tryLock') {
                if (owner !== null) {
                  if (operation === 'tryLock') return reply(index, false);
                  if (options.blocked) return reply(index, null, 'Lock timeout');
                  waiters.push(index);
                  if (pausedRead) { const resume = pausedRead; pausedRead = null; resume(); }
                  return;
                }
                owner = index;
                return reply(index, true);
              }
              if (operation === 'release') {
                assert.equal(owner, index, '自分が取得したロックだけを解放する');
                owner = null;
                releases += 1;
                reply(index);
                if (waiters.length) { owner = waiters.shift(); reply(owner, true); }
                return;
              }
              if (operation === 'get') {
                const value = read(args[0]);
                if (index === 0 && args[0] === options.target && ++reads === (options.reads || 1)) {
                  pausedRead = () => reply(index, value);
                  startB();
                  return;
                }
                return reply(index, value);
              }
              if (operation === 'put' || operation === 'remove') {
                assert.equal(owner, index, '状態の変更はロック内で行う');
                if (!putFailed && options.throwPut === args[0]) {
                  putFailed = true;
                  return reply(index, null, '見本のキャッシュ書込失敗');
                }
                if (operation === 'put') {
                  values.set(args[0], args[1]);
                  expirations.set(args[0], now + args[2] * 1000);
                } else values.delete(args[0]);
                return reply(index);
              }
              assert.notEqual(owner, index, 'シート読込・送信・待機をロック内に入れない');
              if (operation === 'allowed') return reply(index, args[0] === EMAIL ? { email: EMAIL, name: '見本' } : null);
              if (operation === 'property') return reply(index, args[0] === 'ERROR_NOTIFY_EMAIL' ? 'admin@example.test' : null);
              if (operation === 'quota') return reply(index, options.quota ?? 100);
              if (operation === 'sleep') return reply(index);
              if (operation === 'mail') {
                const finish = () => {
                  if (index === 0 && options.failMailA) return reply(index, null, '見本の送信失敗');
                  mails.push({ index, mail: args[0] });
                  reply(index);
                };
                if (index === 0 && options.afterMail) {
                  now += options.advanceMs || 0;
                  pausedMail = finish;
                  startB();
                  return;
                }
                return finish();
              }
              throw new Error('未定義の見本操作: ' + operation);
            } catch (error) { reject(error); }
          });
        });
        workers[0].postMessage(commands[0]);
        if (!options.target && !options.sequential && !options.afterMail) startB();
      });
    } finally {
      clearTimeout(timer);
      await Promise.all(workers.map(worker => worker.terminate()));
    }
  }
  module.exports = { runPair, NOW, EMAIL, hash };
}
