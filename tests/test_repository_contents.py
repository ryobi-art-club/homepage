"""リポジトリは公開しているので、公開してはいけないものが入っていないかを確かめる。
コミットの前（.githooks/pre-commit。クローンしたら git config core.hooksPath .githooks を1回）と、プッシュのたび（.github/workflows/check.yml）に動く。

止めるもの：
- メールアドレス（見本用に予約されたドメイン（example.com・.test など）と、サイトに載せている部の連絡先だけはよい）
- 管理画面（Apps Script のウェブアプリ）の URL。部員に直接伝え、どこにも書かない
- 鍵（サービスアカウントの秘密鍵）
- 部員の情報が入りやすいファイル（スプレッドシートを書き出した Excel、clasp のログイン情報）
"""
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}')
FORBIDDEN_TEXT = {
    '管理画面の URL': re.compile(r'script\.google\.com/macros/s/'),
    '秘密鍵': re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----|"private_key"\s*:'),
}
# 見本用に予約されたドメイン（RFC 2606）
EXAMPLE_DOMAIN = re.compile(r'(^|\.)example\.(com|org|net)$|\.(test|example|invalid)$')
# 画像など、文字ではないファイル（中は調べない）
BINARY_FILES = re.compile(r'\.(png|jpe?g|gif|webp|ico|pdf|woff2?|pyc)$', re.I)
FORBIDDEN_FILES = re.compile(r'(\.xlsx|\.xls|(^|/)\.clasprc\.json|service-account[^/]*\.json)$', re.I)


def tracked_files() -> list[str]:
    try:
        # まだ git add していないファイルも見る（.gitignore で除いたものは見ない）
        output = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
                                cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return [line for line in output.splitlines() if line]
    except (OSError, subprocess.CalledProcessError):
        # Git がない所では、作業用のフォルダを除いて全部を見る
        skip = {'.git', 'node_modules', 'out', 'build', 'dist', '__pycache__'}
        return [str(path.relative_to(ROOT)).replace('\\', '/') for path in ROOT.rglob('*')
                if path.is_file() and not skip.intersection(path.relative_to(ROOT).parts)]


def read_text(path: Path) -> str:
    """文字のファイルを読む。Windows の PowerShell が作る UTF-16 や、Shift_JIS のファイルも読む（読めないファイルを飛ばすと見落とすため）。"""
    data = path.read_bytes()
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16')
    for encoding in ('utf-8-sig', 'cp932'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode('latin-1')


def allowed_emails() -> set[str]:
    """サイトに載せている部の連絡先（src/site_static.json）と、Git のリポジトリのアドレス。"""
    static = json.loads((ROOT / 'src' / 'site_static.json').read_text(encoding='utf-8'))
    public = {static['requests_static'].get('contact_email', ''), str(static['social_links'].get('email', '')).removeprefix('mailto:')}
    return {address.lower() for address in public if address} | {'git@github.com'}


class RepositoryContentsTest(unittest.TestCase):
    def test_no_private_information_is_committed(self):
        allowed = allowed_emails()
        problems = []
        for name in tracked_files():
            if FORBIDDEN_FILES.search(name):
                problems.append(f'{name}：公開してはいけない種類のファイル')
                continue
            if BINARY_FILES.search(name) or not (ROOT / name).is_file():
                continue
            text = read_text(ROOT / name)
            for address in EMAIL.findall(text):
                domain = address.lower().split('@')[1]
                if address.lower() not in allowed and not EXAMPLE_DOMAIN.search(domain):
                    problems.append(f'{name}：メールアドレス {address}')
            for label, pattern in FORBIDDEN_TEXT.items():
                if pattern.search(text):
                    problems.append(f'{name}：{label}')
        self.assertEqual(problems, [], '公開してはいけないものが入っています：\n' + '\n'.join(problems))

    def test_text_in_any_windows_encoding_is_read(self):
        # PowerShell の echo は UTF-16 で書く。読めないファイルを飛ばすと見落とすので、どの形でも読めること
        with tempfile.TemporaryDirectory() as folder:
            for encoding in ('utf-8', 'utf-16', 'cp932'):
                path = Path(folder) / encoding
                path.write_text('連絡先 check@example.test', encoding=encoding)
                self.assertEqual(EMAIL.findall(read_text(path)), ['check@example.test'], encoding)


if __name__ == '__main__':
    unittest.main()
