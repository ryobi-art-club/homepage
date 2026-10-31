"""scripts/fetch_google_content.py のテスト。Google には接続せず、偽の Sheets と Drive で動かす。

実行：python -m unittest discover tests（requirements.txt のライブラリが必要）
"""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import build_site  # noqa: E402
import fetch_google_content as fetch  # noqa: E402


# 管理画面が _PublishedState に書く内容（版2）
CONTENT_V2 = {
    'formatVersion': 2,
    'recruitCalendars': [
        {'year': '2026', 'mediaFolderId': 'fr26', 'mediaFileIds': ['c1', 'c2'], 'published': True},
        {'year': '2025', 'mediaFolderId': 'fr25', 'mediaFileIds': ['c0'], 'published': False},
    ],
    'activityArticles': [
        {'articleId': 'a1', 'title': '記事', 'category': 'record', 'body': '本文', 'mediaFolderId': 'fa1',
         'mediaFileIds': ['p1', 'p2'], 'published': True, 'createdAt': '2026-10-01T00:00:00.000Z'},
        {'articleId': 'a2', 'title': '非公開の記事', 'category': 'event', 'body': '', 'mediaFolderId': '',
         'mediaFileIds': [], 'published': False, 'createdAt': '2026-10-02T00:00:00.000Z'},
    ],
    'exhibitions': [
        {'exhibitionId': 'e1', 'title': '展示', 'subtitle': 'サブ', 'theme': '概要', 'venueName': '会場', 'venueAddress': '神戸市',
         'dateLine': '2026年11月7日(土)', 'timeLine': '10:00〜', 'displayBucket': 'upcoming', 'mediaFolderId': 'fe1',
         'dmFileIds': ['dm1', 'dm2'], 'works': [{'fileId': 'w1', 'title': '一', 'artist': 'A'}, {'fileId': 'w2', 'title': '二', 'artist': 'B'}],
         'published': True, 'startDate': '2026-11-07', 'endDate': '2026-11-08'},
        {'exhibitionId': 'e2', 'title': '過去', 'subtitle': '', 'theme': '', 'venueName': '', 'venueAddress': '', 'dateLine': '',
         'timeLine': '', 'displayBucket': 'archive', 'mediaFolderId': 'fe2', 'dmFileIds': ['dm3'], 'works': [],
         'published': True, 'startDate': '2025-05-01', 'endDate': ''},
    ],
    'requestCases': [
        {'caseId': 'r2', 'title': '二番目に並べた事例', 'body': '', 'mediaFolderId': '', 'mediaFileIds': [], 'published': True},
        {'caseId': 'r1', 'title': '事例', 'body': '本文', 'mediaFolderId': 'fq', 'mediaFileIds': ['q1'], 'published': True},
    ],
}


def published_state_rows(content, chunk=None):
    """_PublishedState のシートの値。chunk を渡すと、管理画面と同じ形でセルを分ける。"""
    text = json.dumps(content, ensure_ascii=False)
    cells = [text]
    if chunk:
        pieces = [json.dumps(text[i:i + chunk], ensure_ascii=False) for i in range(0, len(text), chunk)]
        cells = [json.dumps({'storage_format': 'chunked-json-v1', 'chunk_count': len(pieces)})] + pieces
    headers = ['updated_at', 'revision', 'sha256'] + ['payload_json' if i == 0 else f'payload_json_{i + 1}' for i in range(len(cells))]
    return [headers, ['2026-10-31T00:00:00.000Z', '1', 'hash'] + cells]


class FakeSheets:
    def __init__(self, sheets):
        self.sheets = sheets

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, spreadsheetId, range):
        name = range.split('!')[0].strip("'")
        rows = self.sheets.get(name)
        return FakeRequest(RuntimeError('Unable to parse range') if rows is None else {'values': rows})


class FakeRequest:
    def __init__(self, result):
        self.result = result

    def execute(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class RecordingDrive:
    """取得した画像を記録するだけの Drive。"""

    def __init__(self):
        self.downloads = []
        self.cache_jobs = {}
        self.downloaded = 0

    def prefetch_meta(self, ids):
        self.prefetched = sorted(set(ids))

    def meta(self, file_id):
        return {'id': file_id, 'name': file_id + '.jpg', 'mimeType': 'image/jpeg'}

    def download(self, file_id, destination):
        self.downloads.append((file_id, Path(destination).as_posix().split('/assets/')[-1]))
        self.cache_jobs[file_id] = None

    def finish(self):
        pass

    def prune_cache(self):
        return 0


def build_snapshot(sheet_values):
    """main() を偽の Sheets と Drive で動かし、作られたサイトのデータと取得した画像を返す。"""
    sheets, drive = FakeSheets(sheet_values), RecordingDrive()
    original = fetch.build_clients
    fetch.build_clients = lambda *args: (sheets, drive)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'snapshot.json'
            sys.argv = ['fetch', '--service-account-json', 'key', '--content-spreadsheet-id', 'id',
                        '--output-json', str(output), '--assets-dir', str(Path(tmp) / 'assets')]
            fetch.main()
            snapshot = json.loads(output.read_text(encoding='utf-8'))
    finally:
        fetch.build_clients = original
    del snapshot['meta']
    return snapshot, drive


CHANGE_LOG = [['timestamp', 'kind', 'item_id', 'note', 'actor_name'], ['2026-10-30T00:00:00.000Z', 'exhibition', 'e1', '', 'A']]


class ReadContentTest(unittest.TestCase):
    def test_reads_one_cell_and_split_cells_the_same(self):
        for chunk in (None, 500):
            with self.subTest(chunk=chunk):
                sheets = FakeSheets({'_PublishedState': published_state_rows(CONTENT_V2, chunk)})
                self.assertEqual(fetch.read_published_content(sheets, 'id'), CONTENT_V2)

    def test_no_published_state_is_empty_content(self):
        self.assertEqual(fetch.read_published_content(FakeSheets({}), 'id'), {})

    def test_broken_published_state_stops_the_build(self):
        rows = published_state_rows(CONTENT_V2)
        rows[1][3] = '{broken'
        with self.assertRaises(ValueError):
            fetch.read_published_content(FakeSheets({'_PublishedState': rows}), 'id')

    def test_another_format_version_stops_the_build(self):
        for version in (None, 3):
            content = {k: v for k, v in CONTENT_V2.items() if k != 'formatVersion'}
            if version:
                content['formatVersion'] = version
            with self.subTest(version=version), self.assertRaises(ValueError):
                fetch.read_published_content(FakeSheets({'_PublishedState': published_state_rows(content)}), 'id')


class BuildTest(unittest.TestCase):
    def test_site_data(self):
        snapshot, drive = build_snapshot({'_PublishedState': published_state_rows(CONTENT_V2), 'ChangeLog': CHANGE_LOG})
        self.assertEqual(snapshot['recruit_calendar']['label'], '2026年度 新歓イベントカレンダー')
        self.assertEqual([item['id'] for item in snapshot['activities']], ['a1'], '非公開の記事は載せない')
        self.assertEqual([item['id'] for item in snapshot['requests']], ['r2', 'r1'], '並べた順のまま')
        self.assertEqual([work['title'] for work in snapshot['exhibitions']['upcoming'][0]['works']], ['一', '二'])
        self.assertEqual(snapshot['exhibitions']['archive'][0]['id'], 'e2')
        self.assertEqual(snapshot['change_log'], [{'timestamp': '2026-10-30T00:00:00.000Z', 'kind': 'exhibition', 'item_id': 'e1', 'note': ''}])
        self.assertIn(('w2', 'exhibitions/e1/002-w2.jpg'), drive.downloads)
        self.assertNotIn('c0', drive.prefetched, '公開していない年度の画像は取らない')

    def test_split_cells_make_the_same_site(self):
        whole = build_snapshot({'_PublishedState': published_state_rows(CONTENT_V2), 'ChangeLog': CHANGE_LOG})
        split = build_snapshot({'_PublishedState': published_state_rows(CONTENT_V2, chunk=300), 'ChangeLog': CHANGE_LOG})
        self.assertEqual(split[0], whole[0])
        self.assertEqual(split[1].downloads, whole[1].downloads)


class UpdateLogTest(unittest.TestCase):
    """サイトの更新履歴：ChangeLog の行（1行に1つの変更）から、今の内容のタイトルで文言を作る"""

    def site(self, rows):
        snapshot, _ = build_snapshot({'_PublishedState': published_state_rows(CONTENT_V2), 'ChangeLog': rows})
        return build_site.render_update_log(snapshot['change_log'], snapshot)

    def bullets(self, html_text):
        return [part.split('</li>')[0] for part in html_text.split('<li>')[1:]]

    def test_current_titles_and_only_published_items(self):
        header = ['timestamp', 'kind', 'item_id', 'note', 'actor_name']
        html_text = self.site([header,
                               ['2026-10-01T00:00:00.000Z', 'activity', 'a1', '', 'A'],
                               ['2026-10-01T00:00:00.000Z', 'activity', 'a2', '', 'A'],
                               ['2026-10-01T00:00:00.000Z', 'request', 'deleted', '', 'A'],
                               ['2026-10-01T00:00:00.000Z', 'recruit', '', '', 'A'],
                               ['2026-10-01T00:00:00.000Z', 'note', '', '部室を移りました', 'A'],
                               ['2026-10-01T00:00:00.000Z', 'activity', 'a1', '', 'A'],
                               ['2026-10-02T00:00:00.000Z', 'exhibition', 'e2', '', 'B']])
        self.assertEqual(self.bullets(html_text), [
            '展示会「過去」の情報を公開',
            '活動記録・告知「記事」', '新歓イベントカレンダーを更新', '部室を移りました'])

    def test_the_old_sentence_rows_show_the_same_until_the_cms_rewrites_them(self):
        old = self.site([['timestamp', 'summary', 'actor_name'],
                         ['2026-10-01T00:00:00.000Z', '活動記録・告知「記事」\n活動記録・告知「非公開の記事」', 'A'],
                         ['2026-10-02T00:00:00.000Z', '展示会「過去」の情報を公開', 'B']])
        new = self.site([['timestamp', 'kind', 'item_id', 'note', 'actor_name'],
                         ['2026-10-01T00:00:00.000Z', 'activity', 'a1', '', 'A'],
                         ['2026-10-01T00:00:00.000Z', 'activity', 'a2', '', 'A'],
                         ['2026-10-02T00:00:00.000Z', 'exhibition', 'e2', '', 'B']])
        self.assertEqual(old, new)


class Request:
    def __init__(self, file_id):
        self.file_id = file_id


class CacheDrive:
    """DriveFiles が使う Drive の API の偽物。中身とチェックサムを変えられる。"""

    def __init__(self, files):
        self.files_by_id = files
        self.media_requests = 0
        self.threads = set()
        self.lock = threading.Lock()

    def files(self):
        return self

    def get(self, fileId, fields, supportsAllDrives):
        return FakeRequest(self.files_by_id[fileId]['meta'] if fileId in self.files_by_id else RuntimeError('404'))

    def get_media(self, fileId):
        with self.lock:
            self.media_requests += 1
            self.threads.add(threading.get_ident())
        return Request(fileId)

    def new_batch_http_request(self, callback):
        return Batch(self, callback)


class Batch:
    def __init__(self, drive, callback):
        self.drive, self.callback, self.ids = drive, callback, []

    def add(self, request, request_id):
        self.ids.append(request_id)

    def execute(self):
        for file_id in self.ids:
            known = self.drive.files_by_id.get(file_id)
            self.callback(file_id, known and known['meta'], None if known else RuntimeError('404'))


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.files = {f'id{i}': {'meta': {'id': f'id{i}', 'name': f'p{i}.jpg', 'mimeType': 'image/jpeg', 'md5Checksum': f'sum{i}'},
                                 'data': f'id{i}'.encode()} for i in range(20)}
        self.drive = CacheDrive(self.files)
        files = self.files

        class Download:
            def __init__(self, fh, request, chunksize):
                self.fh, self.request = fh, request

            def next_chunk(self):
                self.fh.write(files[self.request.file_id]['data'])
                return None, True

        self.patches = [(fetch, 'build', lambda *args, **kwargs: self.drive), (fetch, 'MediaIoBaseDownload', Download)]
        self.saved = [(module, name, getattr(module, name)) for module, name, _ in self.patches]
        for module, name, value in self.patches:
            setattr(module, name, value)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        for module, name, value in self.saved:
            setattr(module, name, value)
        self.tmp.cleanup()

    def build(self, ids, out):
        drive = fetch.DriveFiles(None, self.root / 'cache')
        drive.prefetch_meta(ids)
        for index, file_id in enumerate(ids):
            drive.download(file_id, self.root / out / f'{index}.jpg')
        drive.finish()
        return drive, drive.prune_cache()

    def test_only_new_and_changed_images_are_downloaded_and_the_cache_keeps_only_the_site(self):
        first, _ = self.build([f'id{i}' for i in range(10)] + ['id0'], 'out1')
        self.assertEqual(first.downloaded, 10, '同じ画像は1回だけ取る')
        self.assertGreater(len(self.drive.threads), 1, '同時に取る')
        self.assertEqual((self.root / 'out1' / '10.jpg').read_bytes(), b'id0')

        self.files['id3']['meta']['md5Checksum'] = 'changed'
        self.files['id3']['data'] = b'new'
        second, removed = self.build(['id0', 'id3', 'id15'], 'out2')
        self.assertEqual(second.downloaded, 2, '変わった画像と新しい画像だけ取る')
        self.assertEqual((self.root / 'out2' / '1.jpg').read_bytes(), b'new')
        self.assertEqual(removed, 8, 'サイトに使わなくなった画像はキャッシュから消す')
        kept = sorted(path.name for path in (self.root / 'cache').iterdir() if path.suffix != '.md5')
        self.assertEqual(kept, ['id0', 'id15', 'id3'])


if __name__ == '__main__':
    unittest.main()
