#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
import tempfile
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
SHEETS_RANGE_MAP = {
    'Recruit': 'Recruit!A1:Z2000',
    'PublishControl': 'PublishControl!A1:Z200',
    'ActivityArticles': 'ActivityArticles!A1:Z2000',
    'Exhibitions': 'Exhibitions!A1:Z2000',
    'RequestCases': 'RequestCases!A1:Z2000',
    'ChangeLog': 'ChangeLog!A1:Z2000',
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def load_service_account(service_account_json: str):
    return service_account.Credentials.from_service_account_file(service_account_json, scopes=SCOPES)


def build_clients(service_account_json: str):
    credentials = load_service_account(service_account_json)
    sheets = build('sheets', 'v4', credentials=credentials, cache_discovery=False)
    drive = build('drive', 'v3', credentials=credentials, cache_discovery=False)
    return sheets, drive


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


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on', 'y'}


def parse_json_cell(value: str, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def file_extension_from_name(name: str, mime_type: str) -> str:
    if '.' in name:
        return '.' + name.rsplit('.', 1)[1].lower()
    guessed = mimetypes.guess_extension(mime_type or '')
    return guessed or '.bin'


def download_file(drive, file_id: str, destination: Path) -> None:
    ensure_dir(destination.parent)
    request = drive.files().get_media(fileId=file_id)
    with destination.open('wb') as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def get_file_meta(drive, file_id: str) -> dict[str, Any] | None:
    if not file_id:
        return None
    try:
        return (
            drive.files()
            .get(
                fileId=file_id,
                fields='id, name, mimeType, webViewLink',
                supportsAllDrives=True,
            )
            .execute()
        )
    except Exception:
        return None


def list_folder_files(drive, folder_id: str) -> list[dict[str, Any]]:
    files = []
    page_token = None
    while True:
        response = drive.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields='nextPageToken, files(id, name, mimeType, webViewLink)',
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
    return files


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


def normalize_activity_articles(rows: list[dict[str, str]], drive, assets_root: Path) -> list[dict[str, Any]]:
    items = []
    for row in rows:
        if not parse_bool(row.get('published', 'TRUE')):
            continue
        if not row.get('title'):
            continue
        article_id = row.get('article_id') or safe_slug(row.get('title', 'article'))
        file_ids = parse_json_cell(row.get('media_file_ids', ''), [])
        images = download_ordered_images_by_ids(drive, file_ids, assets_root, f'activities/{article_id}', max_images=10)
        if not images:
            images = download_folder_images(drive, row.get('media_folder_id') or row.get('photo_folder_id', ''), assets_root, f'activities/{article_id}', max_images=10)
        items.append({
            'id': article_id,
            'title': row.get('title', ''),
            'body': row.get('body', ''),
            'category': row.get('category', 'record') or 'record',
            'created_at': row.get('created_at') or row.get('updated_at') or now_iso(),
            'images': images,
        })
    return sorted(items, key=lambda x: x.get('created_at', ''), reverse=True)


def normalize_requests(rows: list[dict[str, str]], drive, assets_root: Path) -> list[dict[str, Any]]:
    items = []
    for row in rows:
        if not parse_bool(row.get('published', 'TRUE')):
            continue
        if not row.get('title'):
            continue
        case_id = row.get('case_id') or safe_slug(row.get('title', 'case'))
        file_ids = parse_json_cell(row.get('media_file_ids', ''), [])
        images = download_ordered_images_by_ids(drive, file_ids, assets_root, f'requests/{case_id}', max_images=10)
        if not images:
            images = download_folder_images(drive, row.get('media_folder_id') or row.get('photo_folder_id', ''), assets_root, f'requests/{case_id}', max_images=10)
        items.append({
            'id': case_id,
            'title': row.get('title', ''),
            'body': row.get('body', ''),
            'sort_order': int(row.get('sort_order') or 9999),
            'images': images,
        })
    return sorted(items, key=lambda x: x['sort_order'])


def normalize_recruit_calendar(recruit_rows: list[dict[str, str]], drive, assets_root: Path) -> dict[str, Any]:
    row = next((item for item in recruit_rows if parse_bool(item.get('published', ''))), recruit_rows[0] if recruit_rows else {})
    year = str(row.get('year', '')).strip()
    label = f'{year}年度 新歓イベントカレンダー' if year else '新歓イベントカレンダー'
    file_ids = parse_json_cell(row.get('media_file_ids', ''), [])
    images = download_ordered_images_by_ids(drive, file_ids, assets_root, 'recruit', max_images=3)
    if not images:
        images = download_folder_images(drive, row.get('media_folder_id') or row.get('recruit_calendar_folder_id', ''), assets_root, 'recruit', max_images=3)
    return {
        'label': label,
        'year': year,
        'images': images,
    }


def normalize_exhibitions(ex_rows: list[dict[str, str]], drive, assets_root: Path) -> dict[str, Any]:
    upcoming = []
    archive = []

    published_rows = [row for row in ex_rows if parse_bool(row.get('published', 'TRUE')) and row.get('title')]
    published_rows.sort(key=lambda x: x.get('start_date', ''), reverse=True)

    for row in published_rows:
        ex_id = row.get('exhibition_id') or safe_slug(row.get('title', 'exhibition'))
        folder_id = row.get('media_folder_id') or row.get('drive_folder_id', '')
        dm_candidates = [get_file_meta(drive, file_id) for file_id in parse_json_cell(row.get('dm_file_ids', ''), [])[:2]]
        dm_candidates = [file for file in dm_candidates if file and file.get('mimeType', '').startswith('image/')]
        dm_images = []
        for dm_index, dm_file in enumerate(dm_candidates, start=1):
            dm_ext = file_extension_from_name(dm_file.get('name', ''), dm_file.get('mimeType', ''))
            dm_target = assets_root / 'exhibitions' / ex_id / f'DM{dm_index}{dm_ext}'
            download_file(drive, dm_file['id'], dm_target)
            dm_images.append(str(dm_target.relative_to(assets_root.parent)).replace(os.sep, '/'))
        dm_image = dm_images[0] if dm_images else ''

        works = []
        work_rows_for_ex = sorted(parse_json_cell(row.get('work_files', ''), []), key=lambda x: int(x.get('sort_order') or x.get('sortOrder') or 9999))[:200]
        for work_index, work_row in enumerate(work_rows_for_ex, start=1):
            file_id = str(work_row.get('file_id') or work_row.get('fileId') or '').strip()
            file_meta = get_file_meta(drive, file_id)
            if not file_meta or not file_meta.get('mimeType', '').startswith('image/'):
                continue
            ext = file_extension_from_name(file_meta.get('name', ''), file_meta.get('mimeType', ''))
            image_target = assets_root / 'exhibitions' / ex_id / f"{work_index:03d}-{safe_slug(Path(file_meta.get('name', 'work')).stem)}{ext}"
            download_file(drive, file_meta['id'], image_target)
            works.append({
                'image': str(image_target.relative_to(assets_root.parent)).replace(os.sep, '/'),
                'title': work_row.get('title') or work_row.get('workTitle', ''),
                'artist': work_row.get('artist') or work_row.get('artistName', ''),
            })

        payload = {
            'id': ex_id,
            'title': row.get('title', ''),
            'theme': row.get('theme', ''),
            'overview': row.get('overview', '') or row.get('summary', ''),
            'venue_name': row.get('venue_name', ''),
            'venue_address': row.get('venue_address', ''),
            'date_line': row.get('date_line', ''),
            'time_line': row.get('time_line', ''),
            'folder_id': folder_id,
            'folder_url': f'https://drive.google.com/drive/folders/{folder_id}' if folder_id else '',
            'map_embed_url': row.get('map_embed_url', ''),
            'dm_image': dm_image,
            'dm_images': dm_images,
            'works': works,
            'start_date': row.get('start_date', ''),
        }
        status = (row.get('display_bucket') or '').strip().lower()
        if status == 'upcoming':
            upcoming.append(payload)
        else:
            archive.append(payload)

    upcoming.sort(key=lambda x: x.get('start_date', ''))
    archive.sort(key=lambda x: x.get('start_date', ''), reverse=True)
    return {'upcoming': upcoming, 'archive': archive}


def main() -> None:
    parser = argparse.ArgumentParser(description='Read Google Sheets/Drive content and create a normalized site snapshot.')
    parser.add_argument('--service-account-json', required=True, help='Service account credential JSON path.')
    parser.add_argument('--content-spreadsheet-id', required=True, help='Spreadsheet ID for the content workbook.')
    parser.add_argument('--output-json', required=True, help='Destination path for normalized snapshot JSON.')
    parser.add_argument('--assets-dir', required=True, help='Directory where downloaded assets will be written.')
    args = parser.parse_args()

    sheets, drive = build_clients(args.service_account_json)
    spreadsheet_id = args.content_spreadsheet_id
    output_json = Path(args.output_json)
    assets_dir = Path(args.assets_dir)
    if assets_dir.exists():
        shutil.rmtree(assets_dir)
    ensure_dir(assets_dir)
    ensure_dir(output_json.parent)

    tables = {name: get_sheet_rows(sheets, spreadsheet_id, range_name) for name, range_name in SHEETS_RANGE_MAP.items()}
    snapshot = {
        'meta': {'generated_at': now_iso()},
        'recruit_calendar': normalize_recruit_calendar(tables['Recruit'] or tables['PublishControl'], drive, assets_dir),
        'activities': normalize_activity_articles(tables['ActivityArticles'], drive, assets_dir),
        'requests': normalize_requests(tables['RequestCases'], drive, assets_dir),
        'exhibitions': normalize_exhibitions(tables['Exhibitions'], drive, assets_dir),
        'change_log': normalize_change_log(tables['ChangeLog']),
    }
    output_json.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote snapshot to {output_json}')


if __name__ == '__main__':
    main()
