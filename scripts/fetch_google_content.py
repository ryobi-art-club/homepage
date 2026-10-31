#!/usr/bin/env python3
"""管理画面が公開した内容（スプレッドシート）と画像（Drive）を読み、サイトを作るためのデータにする。"""
from __future__ import annotations

import argparse
import json
import mimetypes
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/spreadsheets.readonly',
]
# 管理画面は、公開した内容全体を _PublishedState に JSON で書く（形は homepage-cms の README「8-4」）
PUBLISHED_STATE_RANGE = "'_PublishedState'"
CHANGE_LOG_RANGE = 'ChangeLog!A1:Z2000'
CONTENT_FORMAT_VERSION = 2
IMAGES_PER_ITEM = 10
WORKS_PER_EXHIBITION = 200

FILE_FIELDS = 'id, name, mimeType, webViewLink, md5Checksum'
DOWNLOAD_WORKERS = 8
BATCH_SIZE = 100


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def build_clients(service_account_json: str, cache_dir: Path | None = None):
    credentials = service_account.Credentials.from_service_account_file(service_account_json, scopes=SCOPES)
    sheets = build('sheets', 'v4', credentials=credentials, cache_discovery=False)
    return sheets, DriveFiles(credentials, cache_dir)


class DriveFiles:
    """ビルドでの Drive の読み取り。ファイルの情報はまとめて問い合わせ、画像は何枚かを同時に取得する。

    取得した画像はビルドをまたいで取っておく（cache_dir/<ファイル ID> と、Drive のチェックサムを書いた
    <ファイル ID>.md5）。このキャッシュは公開リポジトリでは誰でも読めるので、prune_cache で今回サイトに
    載せた画像だけを残す。非公開にした・削除した画像は、次のビルドでキャッシュからなくなる。"""

    def __init__(self, credentials, cache_dir: Path | None):
        self.credentials = credentials
        self.cache_dir = cache_dir
        self.local = threading.local()
        self.meta_by_id: dict[str, dict[str, Any] | None] = {}
        self.cache_jobs: dict[str, Any] = {}
        self.copies: list[tuple[str, Path]] = []
        self.pool = ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS)
        self.downloaded = 0
        self.lock = threading.Lock()
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    # googleapiclient は複数のスレッドで共有できないので、スレッドごとに作る
    def service(self):
        if not hasattr(self.local, 'drive'):
            self.local.drive = build('drive', 'v3', credentials=self.credentials, cache_discovery=False)
        return self.local.drive

    def prefetch_meta(self, file_ids: list[str]) -> None:
        ids = [file_id for file_id in dict.fromkeys(file_ids) if file_id not in self.meta_by_id]
        for start in range(0, len(ids), BATCH_SIZE):
            def remember(request_id, response, exception):
                self.meta_by_id[request_id] = None if exception else response
            batch = self.service().new_batch_http_request(callback=remember)
            for file_id in ids[start:start + BATCH_SIZE]:
                batch.add(self.service().files().get(fileId=file_id, fields=FILE_FIELDS, supportsAllDrives=True), request_id=file_id)
            batch.execute()

    def meta(self, file_id: str) -> dict[str, Any] | None:
        if file_id not in self.meta_by_id:
            try:
                self.meta_by_id[file_id] = self.service().files().get(fileId=file_id, fields=FILE_FIELDS, supportsAllDrives=True).execute()
            except Exception:
                self.meta_by_id[file_id] = None
        return self.meta_by_id[file_id]

    # 取得を始めてすぐ戻る。finish がすべての取得を待ち、指定の場所に写す
    def download(self, file_id: str, destination: Path) -> None:
        if file_id not in self.cache_jobs:
            self.cache_jobs[file_id] = self.pool.submit(self.fetch, file_id)
        self.copies.append((file_id, destination))

    def fetch(self, file_id: str) -> Path:
        checksum = (self.meta_by_id.get(file_id) or {}).get('md5Checksum', '')
        if self.cache_dir:
            target = self.cache_dir / file_id
            stamp = self.cache_dir / f'{file_id}.md5'
            if checksum and target.exists() and stamp.exists() and stamp.read_text().strip() == checksum:
                return target
        else:
            target = Path(f'{file_id}.download')
        partial = target.with_name(target.name + '.part')
        request = self.service().files().get_media(fileId=file_id)
        with partial.open('wb') as fh:
            downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        partial.replace(target)
        if self.cache_dir:
            stamp = self.cache_dir / f'{file_id}.md5'
            if checksum:
                stamp.write_text(checksum)
            elif stamp.exists():
                stamp.unlink()
        with self.lock:
            self.downloaded += 1
        return target

    def finish(self) -> None:
        for file_id, destination in self.copies:
            source = self.cache_jobs[file_id].result()
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        if not self.cache_dir:
            for job in self.cache_jobs.values():
                job.result().unlink(missing_ok=True)
        self.pool.shutdown()

    def prune_cache(self) -> int:
        if not self.cache_dir:
            return 0
        keep = set(self.cache_jobs)
        removed = 0
        for path in self.cache_dir.iterdir():
            file_id = path.name.split('.', 1)[0]
            if file_id not in keep or path.name.endswith('.part'):
                path.unlink()
                removed += path.suffix != '.md5'
        return removed


def get_sheet_rows(sheets, spreadsheet_id: str, range_name: str) -> list[dict[str, str]]:
    try:
        values = sheets.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute().get('values', [])
    except Exception:
        return []
    if not values:
        return []
    headers = values[0]
    rows = []
    for raw in values[1:]:
        row = {header: raw[index] if index < len(raw) else '' for index, header in enumerate(headers)}
        if any(value != '' for value in row.values()):
            rows.append(row)
    return rows


def read_published_content(sheets, spreadsheet_id: str) -> dict[str, Any]:
    """_PublishedState の内容。まだ公開していなければ空の内容。

    長い内容は管理画面がセルを分けて書く（homepage-cms の ContentStore.js の buildPayloadCells_）。
    payload_json に {"storage_format": "chunked-json-v1", "chunk_count": n} を書き、
    payload_json_2 から n 個の列に、JSON の文字列として分けた中身を置く。
    読めないとき・版が違うときは止める。空のサイトや崩れたサイトを公開しないため。"""
    rows = get_sheet_rows(sheets, spreadsheet_id, PUBLISHED_STATE_RANGE)
    if not rows or not rows[0].get('payload_json'):
        return {}
    row = rows[0]
    content = json.loads(row['payload_json'])
    if content.get('storage_format') == 'chunked-json-v1':
        pieces = [json.loads(row[f'payload_json_{index + 2}']) for index in range(content['chunk_count'])]
        content = json.loads(''.join(pieces))
    if not isinstance(content, dict):
        raise ValueError('_PublishedState の内容が JSON のオブジェクトではありません')
    if content.get('formatVersion') != CONTENT_FORMAT_VERSION:
        raise ValueError(f"_PublishedState の形（formatVersion: {content.get('formatVersion')}）を読めません")
    return content


def published_items(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [item for item in items or [] if item.get('published', True) and item.get('title')]


def published_recruit_calendar(calendars: list[dict[str, Any]]) -> dict[str, Any]:
    return next((item for item in calendars if item.get('published') is True), calendars[0] if calendars else {})


# サイトに載せる画像のファイル ID。ファイルの情報をまとめて問い合わせるために集める
def referenced_file_ids(content: dict[str, Any]) -> list[str]:
    calendar = published_recruit_calendar(content.get('recruitCalendars') or [])
    ids = list((calendar.get('mediaFileIds') or [])[:IMAGES_PER_ITEM])
    for name in ('activityArticles', 'requestCases'):
        for item in published_items(content.get(name)):
            ids.extend((item.get('mediaFileIds') or [])[:IMAGES_PER_ITEM])
    for item in published_items(content.get('exhibitions')):
        ids.extend((item.get('dmFileIds') or [])[:2])
        ids.extend(work['fileId'] for work in (item.get('works') or [])[:WORKS_PER_EXHIBITION])
    return ids


def image_meta(drive, file_id: str) -> dict[str, Any] | None:
    meta = drive.meta(file_id)
    return meta if meta and meta.get('mimeType', '').startswith('image/') else None


def asset_path(target: Path, assets_root: Path) -> str:
    return target.relative_to(assets_root.parent).as_posix()


def file_extension(meta: dict[str, Any]) -> str:
    name = meta.get('name', '')
    if '.' in name:
        return '.' + name.rsplit('.', 1)[1].lower()
    return mimetypes.guess_extension(meta.get('mimeType') or '') or '.bin'


def safe_slug(text: str) -> str:
    slug = ''.join(ch if ch.isalnum() else '-' for ch in text.lower()).strip('-')
    while '--' in slug:
        slug = slug.replace('--', '-')
    return slug or 'item'


# 登録した画像を、並べた順に10枚まで
def item_images(drive, item: dict[str, Any], assets_root: Path, group: str) -> list[str]:
    images = []
    for number, file_id in enumerate((item.get('mediaFileIds') or [])[:IMAGES_PER_ITEM], start=1):
        meta = image_meta(drive, file_id)
        if not meta:
            continue
        target = assets_root / group / f"{number:02d}-{safe_slug(Path(meta.get('name', 'image')).stem)}{file_extension(meta)}"
        drive.download(file_id, target)
        images.append(asset_path(target, assets_root))
    return images


# 更新履歴（ChangeLog）の版2は、1行に1つの変更（kind・item_id・note）。表示する文言は build_site.py が作る。
# 版1（summary の文章）は、管理画面が次の公開で版2に書き直すまでのあいだだけ読む（書き直したら版1の分は消す）
def normalize_change_log(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    items = []
    for row in rows:
        if not row.get('timestamp'):
            continue
        if 'kind' in row:
            if row.get('kind'):
                items.append({'timestamp': row['timestamp'], 'kind': row['kind'], 'item_id': row.get('item_id', ''), 'note': row.get('note', '')})
        elif row.get('summary'):
            items.append({'timestamp': row['timestamp'], 'summary': row['summary']})
    # 同じ日時の行（1回の公開の変更）は、シートの順のまま
    return sorted(items, key=lambda x: x['timestamp'], reverse=True)


def normalize_recruit_calendar(calendars: list[dict[str, Any]], drive, assets_root: Path) -> dict[str, Any]:
    calendar = published_recruit_calendar(calendars)
    year = str(calendar.get('year', '')).strip()
    return {
        'label': f'{year}年度 新歓イベントカレンダー' if year else '新歓イベントカレンダー',
        'year': year,
        'images': item_images(drive, calendar, assets_root, 'recruit'),
    }


def normalize_activity_articles(articles: list[dict[str, Any]], drive, assets_root: Path) -> list[dict[str, Any]]:
    items = []
    for article in published_items(articles):
        article_id = article.get('articleId') or safe_slug(article['title'])
        items.append({
            'id': article_id,
            'title': article['title'],
            'body': article.get('body', ''),
            'category': article.get('category') or 'record',
            'created_at': article.get('createdAt') or now_iso(),
            'images': item_images(drive, article, assets_root, f'activities/{article_id}'),
        })
    return sorted(items, key=lambda x: x['created_at'], reverse=True)


# 並び順は、管理画面で並べた一覧の順番のまま
def normalize_requests(cases: list[dict[str, Any]], drive, assets_root: Path) -> list[dict[str, Any]]:
    items = []
    for case in published_items(cases):
        case_id = case.get('caseId') or safe_slug(case['title'])
        items.append({
            'id': case_id,
            'title': case['title'],
            'body': case.get('body', ''),
            'images': item_images(drive, case, assets_root, f'requests/{case_id}'),
        })
    return items


def normalize_exhibitions(exhibitions: list[dict[str, Any]], drive, assets_root: Path) -> dict[str, Any]:
    upcoming = []
    archive = []
    for exhibition in published_items(exhibitions):
        ex_id = exhibition.get('exhibitionId') or safe_slug(exhibition['title'])
        folder = assets_root / 'exhibitions' / ex_id

        dm_images = []
        for file_id in (exhibition.get('dmFileIds') or [])[:2]:
            meta = image_meta(drive, file_id)
            if not meta:
                continue
            target = folder / f'DM{len(dm_images) + 1}{file_extension(meta)}'
            drive.download(file_id, target)
            dm_images.append(asset_path(target, assets_root))

        works = []
        for number, work in enumerate((exhibition.get('works') or [])[:WORKS_PER_EXHIBITION], start=1):
            meta = image_meta(drive, work['fileId'])
            if not meta:
                continue
            target = folder / f"{number:03d}-{safe_slug(Path(meta.get('name', 'work')).stem)}{file_extension(meta)}"
            drive.download(work['fileId'], target)
            works.append({'image': asset_path(target, assets_root), 'title': work.get('title', ''), 'artist': work.get('artist', '')})

        folder_id = exhibition.get('mediaFolderId', '')
        payload = {
            'id': ex_id,
            'title': exhibition['title'],
            'subtitle': exhibition.get('subtitle', ''),
            'theme': exhibition.get('theme', ''),
            'venue_name': exhibition.get('venueName', ''),
            'venue_address': exhibition.get('venueAddress', ''),
            'date_line': exhibition.get('dateLine', ''),
            'time_line': exhibition.get('timeLine', ''),
            'folder_id': folder_id,
            'folder_url': f'https://drive.google.com/drive/folders/{folder_id}' if folder_id else '',
            'dm_image': dm_images[0] if dm_images else '',
            'dm_images': dm_images,
            'works': works,
            'start_date': exhibition.get('startDate', ''),
        }
        (upcoming if exhibition.get('displayBucket') == 'upcoming' else archive).append(payload)

    upcoming.sort(key=lambda x: x['start_date'])
    archive.sort(key=lambda x: x['start_date'], reverse=True)
    return {'upcoming': upcoming, 'archive': archive}


def main() -> None:
    parser = argparse.ArgumentParser(description='Read Google Sheets/Drive content and create a normalized site snapshot.')
    parser.add_argument('--service-account-json', required=True, help='Service account credential JSON path.')
    parser.add_argument('--content-spreadsheet-id', required=True, help='Spreadsheet ID for the content workbook.')
    parser.add_argument('--output-json', required=True, help='Destination path for normalized snapshot JSON.')
    parser.add_argument('--assets-dir', required=True, help='Directory where downloaded assets will be written.')
    parser.add_argument('--cache-dir', help='Directory that keeps downloaded images between builds (optional).')
    args = parser.parse_args()

    sheets, drive = build_clients(args.service_account_json, Path(args.cache_dir) if args.cache_dir else None)
    output_json = Path(args.output_json)
    assets_dir = Path(args.assets_dir)
    if assets_dir.exists():
        shutil.rmtree(assets_dir)
    assets_dir.mkdir(parents=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    content = read_published_content(sheets, args.content_spreadsheet_id)
    drive.prefetch_meta(referenced_file_ids(content))
    snapshot = {
        'meta': {'generated_at': now_iso()},
        'recruit_calendar': normalize_recruit_calendar(content.get('recruitCalendars') or [], drive, assets_dir),
        'activities': normalize_activity_articles(content.get('activityArticles'), drive, assets_dir),
        'requests': normalize_requests(content.get('requestCases'), drive, assets_dir),
        'exhibitions': normalize_exhibitions(content.get('exhibitions'), drive, assets_dir),
        'change_log': normalize_change_log(get_sheet_rows(sheets, args.content_spreadsheet_id, CHANGE_LOG_RANGE)),
    }
    drive.finish()
    removed = drive.prune_cache()
    print(f'Images: {len(drive.cache_jobs)} used, {drive.downloaded} downloaded, {len(drive.cache_jobs) - drive.downloaded} from cache, {removed} removed from cache')
    output_json.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote snapshot to {output_json}')


if __name__ == '__main__':
    main()
