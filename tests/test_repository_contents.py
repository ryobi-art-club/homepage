"""リポジトリは公開しているので、公開してはいけないものが入っていないかを確かめる。
コミットの前は --staged でコミット予定の内容を、通常のテストでは作業中のファイルを調べる。

止めるもの：
- メールアドレス（見本用に予約されたドメイン（example.com・.test など）と、サイトに載せている部の連絡先だけはよい）
- 管理画面（Apps Script のウェブアプリ）の URL。部員に直接伝え、どこにも書かない
- 鍵（サービスアカウントの秘密鍵）
- 部員の情報が入りやすいファイル（スプレッドシートを書き出した Excel、clasp のログイン情報）
"""
import io
import json
import os
import re
import subprocess
import sys
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
        output = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                                cwd=ROOT, capture_output=True, check=True).stdout
        return [os.fsdecode(name) for name in output.split(b'\0') if name]
    except (OSError, subprocess.CalledProcessError):
        # Git がない所では、作業用のフォルダを除いて全部を見る
        skip = {'.git', 'node_modules', 'out', 'build', 'dist', '__pycache__'}
        return [str(path.relative_to(ROOT)).replace('\\', '/') for path in ROOT.rglob('*')
                if path.is_file() and not skip.intersection(path.relative_to(ROOT).parts)]


def staged_files() -> dict[str, bytes | None]:
    """インデックス全体を読む。削除済み・未追跡のファイルは含めない。"""
    output = subprocess.run(['git', 'ls-files', '--stage', '-z'], cwd=ROOT,
                            capture_output=True, check=True).stdout
    files = {}
    pending = []
    for entry in output.split(b'\0'):
        if not entry:
            continue
        metadata, name_bytes = entry.split(b'\t', 1)
        mode, object_id, stage = metadata.split()
        name = os.fsdecode(name_bytes)
        if stage != b'0':
            raise ValueError(f'{name}：競合を解消してからコミットしてください')
        if mode == b'160000':
            continue  # サブモジュールの内容はこのリポジトリのファイルではない
        files[name] = None
        if not FORBIDDEN_FILES.search(name) and not BINARY_FILES.search(name):
            pending.append((name, object_id))
    if pending:
        # ファイル名をコマンドへ組み込まず、保存済みのオブジェクトをまとめて読む
        contents = subprocess.run(['git', 'cat-file', '--batch'], cwd=ROOT,
                                  input=b''.join(object_id + b'\n' for _, object_id in pending),
                                  capture_output=True, check=True).stdout
        stream = io.BytesIO(contents)
        for name, object_id in pending:
            header = stream.readline().split()
            if len(header) != 3 or header[:2] != [object_id, b'blob']:
                raise ValueError(f'{name}：コミット予定の内容を取得できません')
            size = int(header[2])
            data = stream.read(size)
            if len(data) != size or stream.read(1) != b'\n':
                raise ValueError(f'{name}：コミット予定の内容が欠けています')
            files[name] = data
    return files


def decode_text(data: bytes) -> str:
    """Windows の PowerShell が作る UTF-16 や、Shift_JIS の文字も調べる。"""
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16')
    for encoding in ('utf-8-sig', 'cp932'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode('latin-1')


def read_text(path: Path) -> str:
    return decode_text(path.read_bytes())


def allowed_emails(static_text: str) -> set[str]:
    """検査対象の設定にある公開連絡先と、Git のリポジトリのアドレス。"""
    static = json.loads(static_text)
    public = {static['requests_static'].get('contact_email', ''), str(static['social_links'].get('email', '')).removeprefix('mailto:')}
    return {address.lower() for address in public if address} | {'git@github.com'}


def check_contents(staged: bool = False) -> list[str]:
    index = staged_files() if staged else None
    if index is not None:
        static = index.get('src/site_static.json')
        if static is None:
            raise ValueError('コミット予定の src/site_static.json がありません')
        allowed = allowed_emails(decode_text(static))
    else:
        allowed = allowed_emails(read_text(ROOT / 'src' / 'site_static.json'))
    problems = []
    for name in index if index is not None else tracked_files():
        if FORBIDDEN_FILES.search(name):
            problems.append(f'{name}：公開してはいけない種類のファイル')
            continue
        if BINARY_FILES.search(name):
            continue
        if index is not None:
            text = decode_text(index[name])
        elif (ROOT / name).is_file():
            text = read_text(ROOT / name)
        else:
            continue
        for address in EMAIL.findall(text):
            domain = address.lower().split('@')[1]
            if address.lower() not in allowed and not EXAMPLE_DOMAIN.search(domain):
                problems.append(f'{name}：メールアドレス {address}')
        for label, pattern in FORBIDDEN_TEXT.items():
            if pattern.search(text):
                problems.append(f'{name}：{label}')
    return problems


class RepositoryContentsTest(unittest.TestCase):
    def test_no_private_information_is_committed(self):
        problems = check_contents()
        self.assertEqual(problems, [], '公開してはいけないものが入っています：\n' + '\n'.join(problems))

    def test_text_in_any_windows_encoding_is_read(self):
        # PowerShell の echo は UTF-16 で書く。読めないファイルを飛ばすと見落とすので、どの形でも読めること
        with tempfile.TemporaryDirectory() as folder:
            for encoding in ('utf-8', 'utf-16', 'cp932'):
                path = Path(folder) / encoding
                path.write_text('連絡先 check@example.test', encoding=encoding)
                self.assertEqual(EMAIL.findall(read_text(path)), ['check@example.test'], encoding)


if __name__ == '__main__':
    if sys.argv[1:] == ['--staged']:
        try:
            problems = check_contents(staged=True)
        except (OSError, subprocess.CalledProcessError, ValueError, KeyError) as error:
            print('コミット予定の内容を検査できません：' + str(error), file=sys.stderr)
            sys.exit(1)
        if problems:
            print('公開してはいけないものが入っています：\n' + '\n'.join(problems), file=sys.stderr)
            sys.exit(1)
    else:
        unittest.main()
