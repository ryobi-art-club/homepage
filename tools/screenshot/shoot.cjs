// 見本のデータ（sample-content.json）でサイトを作り、画面の大きさごとに撮影する。
//   npm install --prefix tools/screenshot
//   node tools/screenshot/shoot.cjs [--chrome <chrome.exe の場所>]
// 撮影した画像は tools/screenshot/out/shots/ に保存する。見た目を変えない作業の前後で compare.cjs で比べる。
// Python は PYTHON（なければ python）を使う。フォントとアイコンを CDN から読むので、ネット接続が要る。
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const { PNG } = require('pngjs');
const puppeteer = require('puppeteer-core');

const root = path.join(__dirname, '..', '..');
const outDir = path.join(__dirname, 'out');
const assetsDir = path.join(outDir, 'assets');
const distDir = path.join(outDir, 'dist');
const shotsDir = path.join(outDir, 'shots');
const chromeArg = process.argv.indexOf('--chrome');
const executablePath = chromeArg > 0 ? process.argv[chromeArg + 1]
  : process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';

// isMobile にすると、Chrome が本物のスマホと同じように viewport の指定に従う
const SCREENS = {
  desktop: { width: 1440, height: 900 },
  tablet: { width: 820, height: 1180, isMobile: true, hasTouch: true },
  mobile: { width: 390, height: 844, isMobile: true, hasTouch: true },
  landscape: { width: 844, height: 390, isMobile: true, hasTouch: true }
};
const TABS = ['exhibitions', 'activities', 'recruit', 'requests'];

// 見本の画像：名前の最後の「幅x高さ」の縦横比で、1色の PNG を作る（縦横比はビルドが読むので、小さくしても比は保つ）
function writeSampleImages(content) {
  const names = JSON.stringify(content).match(/assets\/[^"]+?-\d+x\d+\.png/g) || [];
  Array.from(new Set(names)).forEach((name) => {
    const [, width, height] = name.match(/-(\d+)x(\d+)\.png$/);
    const png = new PNG({ width: Math.round(width / 2), height: Math.round(height / 2) });
    let hash = 0;
    for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
    const color = [80 + hash % 150, 80 + (hash >> 8) % 150, 80 + (hash >> 16) % 150];
    for (let i = 0; i < png.data.length; i += 4) png.data.set([...color, 255], i);
    const target = path.join(outDir, name);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, PNG.sync.write(png));
  });
}

function buildSite() {
  fs.rmSync(outDir, { recursive: true, force: true });
  fs.mkdirSync(assetsDir, { recursive: true });
  const content = JSON.parse(fs.readFileSync(path.join(__dirname, 'sample-content.json'), 'utf8'));
  writeSampleImages(content);
  const snapshot = path.join(outDir, 'snapshot.json');
  fs.writeFileSync(snapshot, JSON.stringify(content));
  execFileSync(process.env.PYTHON || 'python', [path.join(root, 'scripts', 'build_site.py'),
    '--static-config', path.join(root, 'src', 'site_static.json'), '--content-snapshot', snapshot,
    '--assets-root', assetsDir, '--output-dir', distDir], { stdio: 'pipe' });
}

(async () => {
  buildSite();
  fs.mkdirSync(shotsDir, { recursive: true });
  const problems = [];
  const browser = await puppeteer.launch({ executablePath, headless: true, defaultViewport: null });
  const page = await browser.newPage();
  page.on('pageerror', (error) => problems.push('画面のエラー: ' + error.message));
  // 時間で動く表示（スライドショー・現れる動き）は、動きを減らす設定のときに止まる作りなので、その設定で撮る
  await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }]);
  await page.evaluateOnNewDocument(() => {
    const style = document.createElement('style');
    style.textContent = '*, *::before, *::after { transition: none !important; animation: none !important; caret-color: transparent !important; }';
    document.addEventListener('DOMContentLoaded', () => document.head.appendChild(style));
  });
  const url = pathToFileURL(path.join(distDir, 'index.html')).href;

  const shot = async (name) => {
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (overflow > 0) problems.push(`${name}: 画面の幅を ${overflow}px はみ出しています`);
    await page.screenshot({ path: path.join(shotsDir, name + '.png'), fullPage: true });
  };
  const ready = () => page.evaluate(async () => {
    await document.fonts.ready;
    // 読み込みに加えて、描ける状態になるまで待つ（decoding="async" の画像は、読み込んだあとに少し遅れて描かれるため）
    await Promise.all(Array.from(document.images).filter((img) => img.src).map((img) => img.decode().catch(() => null)));
  });
  const click = async (selector) => {
    await page.evaluate((query) => document.querySelector(query).click(), selector);
    await new Promise((resolve) => setTimeout(resolve, 200));
  };

  for (const [screenName, screen] of Object.entries(SCREENS)) {
    await page.setViewport(screen);
    await page.goto(url, { waitUntil: 'networkidle0' });
    for (const tab of TABS) {
      await click(`[data-tab-target="${tab}"]`);
      await page.evaluate(() => document.querySelectorAll('img[loading="lazy"]').forEach((img) => { img.loading = 'eager'; }));
      await ready();
      await shot(`${screenName}-${tab}`);
    }
    if (screenName !== 'desktop' && screenName !== 'mobile') continue;
    // 操作したあとの表示：画材の説明・カルーセルの次へ・拡大表示
    await click('[data-tab-target="recruit"]');
    await click('.material-chip.has-note');
    await click('.recruit-carousel .carousel-button.next');
    await page.evaluate(() => window.scrollTo(0, 0));
    await shot(`${screenName}-recruit-actions`);
    await click('[data-tab-target="activities"]');
    await click('.image-grid-item');
    await page.screenshot({ path: path.join(shotsDir, `${screenName}-lightbox.png`) });
  }
  await browser.close();
  console.log(`スクリーンショットを保存しました: ${shotsDir}（${fs.readdirSync(shotsDir).length}枚）`);
  if (problems.length) {
    problems.forEach((problem) => console.log('  ' + problem));
    process.exitCode = 1;
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
