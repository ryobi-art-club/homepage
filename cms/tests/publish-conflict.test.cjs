// 公開の基準を、下書き保存・同じ内容の再公開・復旧・途中失敗でもすり替えない。
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const crypto = require('node:crypto');
const sources = require('./files.cjs');
const plain = value => JSON.parse(JSON.stringify(value));
const conflict = /公開内容が更新されたか、編集の元の内容を確認できません/;

function setup() {
  let held = false, sequence = 0;
  const properties = new Map();
  const effects = [];
  const drafts = [];
  const ctx = vm.createContext({ console: { log() {}, warn() {} } });
  sources.loadServer(ctx);
  const snapshot = { formatVersion: 2, recruitCalendars: [{ year: '2026', published: true }],
    activityArticles: [{ articleId: 'a', title: '元の記事', category: 'record', body: '本文', createdAt: '2026-01-01' }],
    exhibitions: [], requestCases: [] };
  let published = { payload: snapshot, revision: 1, updatedAt: '2026-11-17', sha256: '' };
  const lock = { waitLock() { assert.equal(held, false); held = true; }, releaseLock() { assert.equal(held, true); held = false; } };
  Object.assign(ctx, {
    LockService: { getScriptLock: () => lock },
    PropertiesService: { getScriptProperties: () => ({ getProperty: key => properties.get(key), setProperty(key, value) {
      assert.equal(held, true); effects.push('generation'); properties.set(key, value);
    } }) },
    Utilities: { getUuid: () => 'id-' + ++sequence },
    requireSession_: () => ({ name: '部員', email: 'member@example.com' }),
    sha256Hex_: value => crypto.createHash('sha256').update(value).digest('hex'),
    isoNow_: () => '2026-11-17T00:00:00.000Z',
    prefetchSheets_: () => { assert.equal(held, true); return {}; },
    readPublishedState_: () => { assert.equal(held, true); return plain(published); },
    readContentState_: (_, info) => ({ ...ctx.contentLists_((info || published).payload), changeLog: [], manualChangeNote: '' }),
    readDrafts_: () => plain(drafts), readAdminLog_: () => [], getDriveMaintenanceSummary_: () => ({}),
    saveDraftRecord_: state => drafts.unshift({ draftId: 'draft-' + drafts.length, payload: plain(ctx.buildDraftPayload_(state)) }),
    finalizeManagedFolders_: () => { effects.push('images'); return []; },
    writePublishedState_: (json, hash) => {
      effects.push('content'); published = { payload: JSON.parse(json), revision: published.revision + 1, updatedAt: 'later', sha256: hash };
    },
    buildChangeLogRows_: () => [],
    clearDrafts_: () => { effects.push('drafts'); drafts.length = 0; },
    cleanupUnreferencedDraftFolders_: () => effects.push('folders'),
    appendAdminLog_: () => { effects.push('log'); return 0; },
    compactContentSheetGrids_: () => effects.push('compact'),
    SpreadsheetApp: { flush: () => effects.push('flush') },
    dispatchGithubWorkflow_: () => { effects.push('dispatch'); return {}; },
    getConfig_: () => ({}), collectGarbage_: () => { effects.push('cleanup'); return {}; }, formatCleanupReport_: () => ''
  });
  published.payload = plain(ctx.buildPublicSnapshot_(ctx.normalizePayload_(snapshot, snapshot)));
  published.sha256 = ctx.sha256Hex_(ctx.stableStringify_(published.payload));
  return { ctx, effects, drafts, properties, bootstrap: () => plain(ctx.getBootstrapData('session').state),
    getPublished: () => plain(published), restore: value => { published = plain(value); },
    isLocked: () => held };
}

test('two editors: the second publication has no effects and releases its lock', () => {
  const env = setup();
  const { ctx, effects, bootstrap } = env;
  const a = bootstrap(), b = bootstrap();
  a.activityArticles[0].title = 'Aの公開';
  ctx.publishState('session', a);
  const before = env.getPublished();
  effects.length = 0;
  env.drafts.push({ draftId: 'other', payload: {} });
  b.activityArticles[0].title = 'Bの未保存';
  assert.throws(() => ctx.publishState('session', b), conflict);
  assert.deepEqual(effects, []);
  assert.deepEqual(env.getPublished(), before);
  assert.equal(env.drafts.length, 1);
  assert.equal(env.isLocked(), false);
  assert.equal(b.activityArticles[0].title, 'Bの未保存');
  assert.ok(ctx.publishState('session', bootstrap()).ok);
});

test('saving and loading a stale draft preserves its old base; legacy drafts stay unknown', () => {
  const { ctx, bootstrap, drafts, effects } = setup();
  const old = bootstrap();
  ctx.publishState('session', bootstrap());
  ctx.saveDraft('session', old);
  const loaded = ctx.loadDraft('session', drafts[0].draftId);
  assert.equal(loaded.baseVersion, old.baseVersion);
  effects.length = 0;
  assert.throws(() => ctx.publishState('session', loaded), conflict);
  drafts.push({ draftId: 'legacy', payload: { activityArticles: [] } });
  assert.equal(ctx.loadDraft('session', 'legacy').baseVersion, '');
  assert.throws(() => ctx.publishState('session', ctx.loadDraft('session', 'legacy')), conflict);
  for (const baseVersion of [undefined, '', null, 12]) {
    assert.throws(() => ctx.publishState('session', { ...old, baseVersion }), conflict);
  }
  assert.deepEqual(effects, []);
});

test('even publication with unchanged content invalidates older screens and drafts', () => {
  const env = setup();
  const old = env.bootstrap();
  const before = env.getPublished();
  env.ctx.publishState('session', old);
  assert.deepEqual(env.getPublished(), before, '内容のシートは変わらない');
  assert.notEqual(env.bootstrap().baseVersion, old.baseVersion);
  env.effects.length = 0;
  assert.throws(() => env.ctx.publishState('session', old), conflict);
  assert.deepEqual(env.effects, []);
});

test('restoring the entire old row cannot revive a token issued before publication', () => {
  const env = setup();
  const original = env.getPublished(), old = env.bootstrap();
  const changed = plain(old);
  changed.activityArticles[0].title = '更新';
  env.ctx.publishState('session', changed);
  const newer = env.bootstrap();
  env.restore(original);
  env.effects.length = 0;
  assert.throws(() => env.ctx.publishState('session', old), conflict);
  assert.throws(() => env.ctx.publishState('session', newer), conflict);
  assert.deepEqual(env.effects, []);
  assert.ok(env.ctx.publishState('session', env.bootstrap()).ok);
});

test('a manual restore is detected even if the revision and stored hash are unchanged', () => {
  const env = setup(), old = env.bootstrap();
  const restored = env.getPublished();
  restored.payload.activityArticles[0].body = '復旧した本文';
  env.restore(restored);
  assert.throws(() => env.ctx.publishState('session', old), conflict);
  assert.deepEqual(env.effects, []);
});

test('a failed publication invalidates the base before image effects; saving edits remains possible', () => {
  const env = setup(), old = env.bootstrap();
  env.ctx.finalizeManagedFolders_ = () => { env.effects.push('images'); throw new Error('画像処理の失敗'); };
  assert.throws(() => env.ctx.publishState('session', old), /画像処理の失敗/);
  assert.deepEqual(env.effects, ['generation', 'images']);
  env.effects.length = 0;
  assert.throws(() => env.ctx.publishState('session', old), conflict);
  assert.deepEqual(env.effects, []);
  assert.ok(env.ctx.saveDraft('session', old).ok);
});

test('the bootstrap token uses the exact published object returned with the content', () => {
  const env = setup();
  let reads = 0;
  const actualRead = env.ctx.readPublishedState_;
  env.ctx.readPublishedState_ = (...args) => { reads++; return actualRead(...args); };
  const state = env.bootstrap();
  assert.equal(reads, 1);
  assert.equal(state.baseVersion, env.ctx.buildContentBaseVersion_(env.getPublished()));
});

test('draft metadata never reaches the public snapshot and unknown versions are not upgraded', () => {
  const { ctx, bootstrap } = setup();
  const state = bootstrap();
  assert.equal(ctx.buildDraftPayload_(state).baseVersion, state.baseVersion);
  assert.ok(!('baseVersion' in ctx.buildPublicSnapshot_(state)));
  delete state.baseVersion;
  assert.equal(ctx.normalizePayload_(state, {}).baseVersion, '');
  assert.equal(ctx.buildDraftPayload_(state).baseVersion, '');
});

test('invalid input does not advance the generation or mutate images and sheets', () => {
  const env = setup(), payload = env.bootstrap();
  payload.activityArticles[0].title = '';
  assert.throws(() => env.ctx.publishState('session', payload), /タイトル/);
  assert.deepEqual(env.effects, []);
  assert.equal(env.isLocked(), false);
});

test('failure to record the new generation stops before any image or sheet changes', () => {
  const env = setup(), payload = env.bootstrap();
  const original = env.ctx.PropertiesService.getScriptProperties;
  env.ctx.PropertiesService.getScriptProperties = () => ({ ...original(), setProperty() { throw new Error('世代の記録失敗'); } });
  assert.throws(() => env.ctx.publishState('session', payload), /世代の記録失敗/);
  assert.deepEqual(env.effects, []);
  assert.equal(env.isLocked(), false);
});
