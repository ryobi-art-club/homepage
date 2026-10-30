#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
import sys
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


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def load_service_account(service_account_json: str):
    return service_account.Credentials.from_service_account_file(service_account_json, scopes=SCOPES)


def build_clients(service_account_json: str, cache_dir: Path | None = None):
    credentials = load_service_account(service_account_json)
    sheets = build('sheets', 'v4', credentials=credentials, cache_discovery=False)
    drive = DriveFiles(credentials, cache_dir)
    return sheets, drive


FILE_FIELDS = 'id, name, mimeType, webViewLink, md5Checksum'
DOWNLOAD_WORKERS = 8
BATCH_SIZE = 100


class DriveFiles:
    """Drive access for the build: metadata in batches, downloads in parallel, and a cache of images
    between builds (`cache_dir/<file id>`, with its Drive checksum in `<file id>.md5`).

    The cache is saved by GitHub Actions and anyone who can open a pull request on the public repository
    can read it, so `prune_cache` keeps only the images this build put on the site: an image that was
    unpublished or deleted leaves the cache at the next build."""

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
            ensure_dir(cache_dir)

    # googleapiclient objects are not thread-safe, so each thread builds its own
    def service(self):
        if not hasattr(self.local, 'drive'):
            self.local.drive = build('drive', 'v3', credentials=self.credentials, cache_discovery=False)
        return self.local.drive

    def prefetch_meta(self, file_ids: list[str]) -> None:
        ids = [file_id for file_id in dict.fromkeys(file_ids) if file_id and file_id not in self.meta_by_id]
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

    def list_folder(self, folder_id: str) -> list[dict[str, Any]]:
        files = []
        page_token = None
        while True:
            response = self.service().files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields=f'nextPageToken, files({FILE_FIELDS})',
                orderBy='name_natural',
                pageToken=page_token,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                corpora='allDrives',
            ).execute()
            files.extend(response.get('files', []))
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        for file_meta in files:
            self.meta_by_id.setdefault(file_meta['id'], file_meta)
        return files

    # Starts the download and returns at once; `finish` waits for every download and copies the files.
    def download(self, file_id: str, destination: Path) -> None:
        if file_id not in self.cache_jobs:
            self.cache_jobs[file_id] = self.pool.submit(self.fetch, file_id)
        self.copies.append((file_id, destination))

    def cached_path(self, file_id: str) -> Path:
        return self.cache_dir / file_id

    def fetch(self, file_id: str) -> Path:
        checksum = (self.meta_by_id.get(file_id) or {}).get('md5Checksum', '')
        if self.cache_dir:
            target = self.cached_path(file_id)
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
            ensure_dir(destination.parent)
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
        values = (
            sheets.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
            .get('values', [])
        )
    except Exception:
        return []
    if not values:
        return []
    headers = values[0]
    rows = []
    for raw in values[1:]:
        row = {}
        for index, header in enumerate(headers):
            row[header] = raw[index] if index < len(raw) else ''
        if any(v != '' for v in row.values()):
            rows.append(row)
    return rows


def safe_slug(text: str) -> str:
    slug = ''.join(ch if ch.isalnum() else '-' for ch in text.lower()).strip('-')
    while '--' in slug:
        slug = slug.replace('--', '-')
    return slug or 'item'


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def file_extension_from_name(name: str, mime_type: str) -> str:
    if '.' in name:
        return '.' + name.rsplit('.', 1)[1].lower()
    guessed = mimetypes.guess_extension(mime_type or '')
    return guessed or '.bin'


def download_file(drive, file_id: str, destination: Path) -> None:
    drive.download(file_id, destination)


def get_file_meta(drive, file_id: str) -> dict[str, Any] | None:
    if not file_id:
        return None
    return drive.meta(file_id)


def list_folder_files(drive, folder_id: str) -> list[dict[str, Any]]:
    return drive.list_folder(folder_id)


def read_published_content(sheets, spreadsheet_id: str) -> dict[str, Any]:
    """_PublishedState の内容。まだ公開していなければ空の内容。

    長い内容は管理画面がセルを分けて書く（homepage-cms の Store.js の buildPayloadCells_）。
    payload_json に {"storage_format": "chunked-json-v1", "chunk_count": n} を書き、
    payload_json_2 から n 個の列に、JSON の文字列として分けた中身を置く。
    読めないときは止める。空のサイトを作って公開してしまわないため。"""
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
    return content


def upgrade_content(content: dict[str, Any]) -> dict[str, Any]:
    """版1（formatVersion がない、2026年10月までの形）を版2に直す。古い形を読む処理はここだけに置く。
    管理画面の upgradeContent_ と同じ直し方。版2で最初に公開したあとは要らなくなる（設計書 段階3）。"""
    if content.get('formatVersion') == CONTENT_FORMAT_VERSION:
        return content

    def with_folder(item: dict[str, Any]) -> dict[str, Any]:
        folder = item.get('mediaFolderId') or item.get('driveFolderId') or item.get('photoFolderId') or item.get('folderId') or ''
        return {**item, 'mediaFolderId': folder}

    def in_stored_order(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def order(item: dict[str, Any]) -> int:
            return int(item.get('sortOrder') or item.get('sort_order') or sys.maxsize)
        return sorted(items or [], key=order)

    return {
        **content,
        'formatVersion': CONTENT_FORMAT_VERSION,
        'recruitCalendars': [with_folder(item) for item in content.get('recruitCalendars') or []],
        'activityArticles': [with_folder(item) for item in content.get('activityArticles') or []],
        'exhibitions': [{
            **with_folder(item),
            'works': [{
                'fileId': work.get('fileId') or work.get('file_id') or '',
                'title': work.get('title') or work.get('workTitle') or '',
                'artist': work.get('artist') or work.get('artistName') or '',
            } for work in in_stored_order(item.get('workFiles') or item.get('works'))],
        } for item in content.get('exhibitions') or []],
        'requestCases': [with_folder(item) for item in in_stored_order(content.get('requestCases'))],
    }


# サイトに載せる画像のファイル ID。ファイルの情報をまとめて問い合わせるために集める
def referenced_file_ids(content: dict[str, Any]) -> list[str]:
    calendar = published_recruit_calendar(content.get('recruitCalendars') or [])
    ids = list((calendar.get('mediaFileIds') or [])[:10])
    for name in ('activityArticles', 'requestCases'):
        for item in published_items(content.get(name)):
            ids.extend((item.get('mediaFileIds') or [])[:10])
    for item in published_items(content.get('exhibitions')):
        ids.extend((item.get('dmFileIds') or [])[:2])
        ids.extend(work['fileId'] for work in item.get('works') or [])
    return [str(file_id).strip() for file_id in ids if str(file_id).strip()]


def published_items(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [item for item in items or [] if item.get('published', True) and item.get('title')]


def download_folder_images(drive, folder_id: str, output_root: Path, logical_group: str, max_images: int | None = None) -> list[str]:
    if not folder_id:
        return []
    files = list_folder_files(drive, folder_id)
    image_files = [f for f in files if f.get('mimeType', '').startswith('image/')]
    if max_images is not None:
        image_files = image_files[:max_images]
    copied_paths = []
    for file_meta in image_files:
        ext = file_extension_from_name(file_meta.get('name', ''), file_meta.get('mimeType', ''))
        target = output_root / logical_group / f"{safe_slug(Path(file_meta.get('name', 'image')).stem)}{ext}"
        download_file(drive, file_meta['id'], target)
        copied_paths.append(str(target.relative_to(output_root.parent)).replace(os.sep, '/'))
    return copied_paths


def download_ordered_images_by_ids(
    drive,
    file_ids: list[str],
    output_root: Path,
    logical_group: str,
    max_images: int | None = None,
) -> list[str]:
    copied_paths = []
    ids = [str(file_id).strip() for file_id in file_ids if str(file_id).strip()]
    if max_images is not None:
        ids = ids[:max_images]
    for index, file_id in enumerate(ids, start=1):
        file_meta = get_file_meta(drive, file_id)
        if not file_meta or not file_meta.get('mimeType', '').startswith('image/'):
            continue
        ext = file_extension_from_name(file_meta.get('name', ''), file_meta.get('mimeType', ''))
        target = output_root / logical_group / f'{index:02d}-{safe_slug(Path(file_meta.get("name", "image")).stem)}{ext}'
        download_file(drive, file_id, target)
        copied_paths.append(str(target.relative_to(output_root.parent)).replace(os.sep, '/'))
    return copied_paths


def normalize_change_log(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    items = []
    for row in rows:
        if not row.get('timestamp') or not row.get('summary'):
            continue
        items.append({'timestamp': row['timestamp'], 'summary': row['summary']})
    return sorted(items, key=lambda x: x['timestamp'], reverse=True)


def normalize_activity_articles(articles: list[dict[str, Any]], drive, assets_root: Path) -> list[dict[str, Any]]:
    items = []
    for article in published_items(articles):
        article_id = article.get('articleId') or safe_slug(article['title'])
        images = item_images(drive, article, assets_root, f'activities/{article_id}')
        items.append({
            'id': article_id,
            'title': article['title'],
            'body': article.get('body', ''),
            'category': article.get('category') or 'record',
            'created_at': article.get('createdAt') or now_iso(),
            'images': images,
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


def published_recruit_calendar(calendars: list[dict[str, Any]]) -> dict[str, Any]:
    return next((item for item in calendars if item.get('published') is True), calendars[0] if calendars else {})


def normalize_recruit_calendar(calendars: list[dict[str, Any]], drive, assets_root: Path) -> dict[str, Any]:
    calendar = published_recruit_calendar(calendars)
    year = str(calendar.get('year', '')).strip()
    return {
        'label': f'{year}年度 新歓イベントカレンダー' if year else '新歓イベントカレンダー',
        'year': year,
        'images': item_images(drive, calendar, assets_root, 'recruit'),
    }


def item_images(drive, item: dict[str, Any], assets_root: Path, logical_group: str) -> list[str]:
    """登録した画像を、並べた順に10枚まで。画像の登録ができる前に保存した項目（一覧が空）は、
    フォルダの画像を名前の順に使う（管理画面の fillUnregisteredMediaIds_ と同じ扱い）。"""
    images = download_ordered_images_by_ids(drive, item.get('mediaFileIds') or [], assets_root, logical_group, max_images=10)
    if not images:
        images = download_folder_images(drive, item.get('mediaFolderId', ''), assets_root, logical_group, max_images=10)
    return images


def normalize_exhibitions(exhibitions: list[dict[str, Any]], drive, assets_root: Path) -> dict[str, Any]:
    upcoming = []
    archive = []
    for exhibition in published_items(exhibitions):
        ex_id = exhibition.get('exhibitionId') or safe_slug(exhibition['title'])
        folder_id = exhibition.get('mediaFolderId', '')
        dm_files = [get_file_meta(drive, file_id) for file_id in (exhibition.get('dmFileIds') or [])[:2]]
        dm_images = []
        for dm_index, dm_file in enumerate((file for file in dm_files if file and file.get('mimeType', '').startswith('image/')), start=1):
            dm_ext = file_extension_from_name(dm_file.get('name', ''), dm_file.get('mimeType', ''))
            dm_target = assets_root / 'exhibitions' / ex_id / f'DM{dm_index}{dm_ext}'
            download_file(drive, dm_file['id'], dm_target)
            dm_images.append(str(dm_target.relative_to(assets_root.parent)).replace(os.sep, '/'))

        works = []
        for work_index, work in enumerate((exhibition.get('works') or [])[:200], start=1):
            file_meta = get_file_meta(drive, work['fileId'])
            if not file_meta or not file_meta.get('mimeType', '').startswith('image/'):
                continue
            ext = file_extension_from_name(file_meta.get('name', ''), file_meta.get('mimeType', ''))
            image_target = assets_root / 'exhibitions' / ex_id / f"{work_index:03d}-{safe_slug(Path(file_meta.get('name', 'work')).stem)}{ext}"
            download_file(drive, file_meta['id'], image_target)
            works.append({
                'image': str(image_target.relative_to(assets_root.parent)).replace(os.sep, '/'),
                'title': work.get('title', ''),
                'artist': work.get('artist', ''),
            })

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
        if (exhibition.get('displayBucket') or '').strip().lower() == 'upcoming':
            upcoming.append(payload)
        else:
            archive.append(payload)

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
    spreadsheet_id = args.content_spreadsheet_id
    output_json = Path(args.output_json)
    assets_dir = Path(args.assets_dir)
    if assets_dir.exists():
        shutil.rmtree(assets_dir)
    ensure_dir(assets_dir)
    ensure_dir(output_json.parent)

    content = upgrade_content(read_published_content(sheets, spreadsheet_id))
    drive.prefetch_meta(referenced_file_ids(content))
    snapshot = {
        'meta': {'generated_at': now_iso()},
        'recruit_calendar': normalize_recruit_calendar(content.get('recruitCalendars') or [], drive, assets_dir),
        'activities': normalize_activity_articles(content.get('activityArticles'), drive, assets_dir),
        'requests': normalize_requests(content.get('requestCases'), drive, assets_dir),
        'exhibitions': normalize_exhibitions(content.get('exhibitions'), drive, assets_dir),
        'change_log': normalize_change_log(get_sheet_rows(sheets, spreadsheet_id, CHANGE_LOG_RANGE)),
    }
    drive.finish()
    removed = drive.prune_cache()
    print(f'Images: {len(drive.cache_jobs)} used, {drive.downloaded} downloaded, {len(drive.cache_jobs) - drive.downloaded} from cache, {removed} removed from cache')
    output_json.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote snapshot to {output_json}')


if __name__ == '__main__':
    main()
