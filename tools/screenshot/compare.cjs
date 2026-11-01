// 見た目を変えない作業（CSS やビルドの整理など）の確認に使う。shoot.cjs のあとに動かす。
//   node tools/screenshot/compare.cjs --save <控えのフォルダ>   いまの撮影の画像を控えに取る
//   node tools/screenshot/compare.cjs <控えのフォルダ>          控えと1画素ずつ比べる
// 違う画像があれば、違う画素に印を付けた画像を out/diff/ に書き、終了コード 1 で終わる。
const fs = require('node:fs');
const path = require('node:path');
const { PNG } = require('pngjs');
const pixelmatch = require('pixelmatch');

const shotsDir = path.join(__dirname, 'out', 'shots');
const diffDir = path.join(__dirname, 'out', 'diff');
const save = process.argv[2] === '--save';
const baselineDir = process.argv[save ? 3 : 2];
if (!baselineDir) {
  console.error('控えのフォルダを指定してください。');
  process.exit(2);
}

if (save) {
  fs.rmSync(baselineDir, { recursive: true, force: true });
  fs.cpSync(shotsDir, baselineDir, { recursive: true });
  console.log('控えに取りました：' + baselineDir);
  process.exit(0);
}

const pngs = (dir) => fs.readdirSync(dir).filter((name) => name.endsWith('.png')).sort();
const baseline = pngs(baselineDir);
const current = pngs(shotsDir);
const problems = [];
fs.rmSync(diffDir, { recursive: true, force: true });
fs.mkdirSync(diffDir, { recursive: true });
baseline.filter((name) => !current.includes(name)).forEach((name) => problems.push(name + '：撮影されていません'));
current.filter((name) => !baseline.includes(name)).forEach((name) => problems.push(name + '：控えにありません'));
baseline.filter((name) => current.includes(name)).forEach((name) => {
  const before = PNG.sync.read(fs.readFileSync(path.join(baselineDir, name)));
  const after = PNG.sync.read(fs.readFileSync(path.join(shotsDir, name)));
  if (before.width !== after.width || before.height !== after.height) {
    problems.push(`${name}：大きさが違います（${before.width}×${before.height} → ${after.width}×${after.height}）`);
    return;
  }
  const diff = new PNG({ width: before.width, height: before.height });
  const count = pixelmatch(before.data, after.data, diff.data, before.width, before.height, { threshold: 0 });
  if (count) {
    fs.writeFileSync(path.join(diffDir, name), PNG.sync.write(diff));
    problems.push(`${name}：${count}画素が違います`);
  }
});

console.log(`画像${baseline.length}枚を比べました。`);
if (problems.length) {
  problems.forEach((problem) => console.log('  ' + problem));
  if (fs.readdirSync(diffDir).length) console.log('違う場所に印を付けた画像：' + diffDir);
  process.exitCode = 1;
} else {
  console.log('すべて同じです。');
}
