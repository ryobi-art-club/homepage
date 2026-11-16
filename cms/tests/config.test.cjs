const vm = require('node:vm');
const assert = require('node:assert/strict');
const { test } = require('node:test');
const sources = require('./files.cjs');

const IDS = {
  CONTENT_SPREADSHEET_ID: 'content',
  ALLOWLIST_SPREADSHEET_ID: 'allowlist',
  ROOT_RECRUIT_FOLDER_ID: 'recruit',
  ROOT_ACTIVITY_FOLDER_ID: 'activity',
  ROOT_EXHIBITION_FOLDER_ID: 'exhibition',
  ROOT_REQUEST_FOLDER_ID: 'request'
};

function configWith(props) {
  const ctx = vm.createContext({
    console,
    PropertiesService: { getScriptProperties: () => ({ getProperty: key => (key in props ? props[key] : null) }) }
  });
  sources.loadServer(ctx);
  return ctx.getConfig_();
}

test('only the IDs are needed; everything else falls back to the defaults', () => {
  const config = configWith(IDS);
  assert.equal(config.SESSION_TTL_MINUTES, 180);
  assert.equal(config.GEMINI_MODEL, 'gemini-3.1-flash-lite');
  assert.equal(config.CLEANUP_MODE, 'trash');
  assert.equal(config.GEMINI_API_KEY, '');
});

test('a script property overrides the default', () => {
  const config = configWith({ ...IDS, SESSION_TTL_MINUTES: '240', CLEANUP_MODE: 'log', GH_PRIVATE_KEY: 'a\\nb' });
  assert.equal(config.SESSION_TTL_MINUTES, 240);
  assert.equal(config.CLEANUP_MODE, 'log');
  assert.equal(config.GH_PRIVATE_KEY, 'a\nb');
});

test('values fixed at deploy time cannot be overridden by script properties', () => {
  const ctx = vm.createContext({
    console,
    PropertiesService: { getScriptProperties: () => ({ getProperty: key => ({ ...IDS, GH_REPO: 'other' })[key] || null }) }
  });
  sources.loadServer(ctx);
  assert.equal(ctx.getConfig_().GH_REPO, undefined);
  assert.equal(vm.runInContext('SITE_URL', ctx), 'https:' + '//ryobi-art-club.github.io/homepage/');
  assert.equal(vm.runInContext('OTP_TTL_MINUTES', ctx), 10);
});

test('a missing ID stops with the names of the missing properties', () => {
  const { ROOT_REQUEST_FOLDER_ID, ...rest } = IDS;
  assert.throws(() => configWith(rest), /ROOT_REQUEST_FOLDER_ID/);
});
