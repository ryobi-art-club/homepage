#!/usr/bin/env python3
"""サイトを作る入口。fetch_google_content.py が作った内容（content_snapshot.json）からページを作り、
src/ の固定のファイルと画像と一緒に書き出す。ページの HTML は sitebuild/ にある。"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from sitebuild import images
from sitebuild.page import build_seo_context, render_page, render_sitemap_xml

# src/ からそのまま写すファイル（Google Search Console の所有確認用の verification/ の中身も写す）
STATIC_FILES = ['stylesheet.css', 'site.js', 'logo.png', 'clubroom.jpg']


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    for file_path in src.rglob('*'):
        if file_path.is_file():
            target = dst / file_path.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, target)


def main() -> None:
    parser = argparse.ArgumentParser(description='Build the Ryobi static site from a normalized content snapshot.')
    parser.add_argument('--static-config', required=True, help='Path to site_static.json')
    parser.add_argument('--content-snapshot', required=True, help='Path to normalized content snapshot JSON')
    parser.add_argument('--assets-root', required=True, help='Root directory for local assets referenced by the snapshot')
    parser.add_argument('--output-dir', required=True, help='Destination directory for built site')
    args = parser.parse_args()

    static_dir = Path(args.static_config).parent
    static = json.loads(Path(args.static_config).read_text(encoding='utf-8'))
    data = json.loads(Path(args.content_snapshot).read_text(encoding='utf-8'))
    output_dir = Path(args.output_dir)
    assets_root = Path(args.assets_root)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # 内容の画像は「assets/…」の形で書かれているので、その1つ上から縦横比を読む
    images.ASSET_SOURCE_ROOT = assets_root.parent
    (output_dir / 'index.html').write_text(render_page(static, data), encoding='utf-8')
    seo = build_seo_context(static, data)
    sitemap_xml = render_sitemap_xml(seo['base_url'], seo['lastmod'])
    if sitemap_xml:
        (output_dir / 'sitemap.xml').write_text(sitemap_xml, encoding='utf-8')
    copy_tree(static_dir / 'verification', output_dir)
    for name in STATIC_FILES:
        shutil.copy2(static_dir / name, output_dir / name)
    copy_tree(assets_root, output_dir / 'assets')
    print(f'Built site at {output_dir}')


if __name__ == '__main__':
    main()
