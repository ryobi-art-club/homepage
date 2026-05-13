#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ASSET_SOURCE_ROOT = Path(".")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def escape(value: Any) -> str:
    return html.escape('' if value is None else str(value), quote=True)


def nl2br(value: str) -> str:
    return '<br>'.join(escape(value).splitlines())


def fmt_date(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except Exception:
        return escape(ts)
    return dt.strftime('%Y.%m.%d')


def normalized_site_url(url: str) -> str:
    value = str(url or '').strip()
    if not value:
        return ''
    return value.rstrip('/') + '/'


def build_seo_context(static: dict[str, Any], data: dict[str, Any]) -> dict[str, str]:
    base_url = normalized_site_url(static.get('og_url', ''))
    site_title = '神戸大学美術部凌美会 | ホームページ'
    description = '神戸大学美術部凌美会の公式ホームページです。展示会情報、活動記録・告知、入部案内、ご依頼の方向け情報を掲載しています。'
    og_image = static.get('og_image', 'logo.png')
    image_url = og_image if str(og_image).startswith('http') else (base_url + str(og_image).lstrip('/')) if base_url else str(og_image)
    organization = {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        'name': '神戸大学美術部凌美会',
        'alternateName': ['神戸大学 美術部 凌美会', '凌美会', '美術部凌美会', '神戸大学美術部'],
        'url': base_url or static.get('og_url', ''),
        'logo': image_url,
        'sameAs': [
            static.get('social_links', {}).get('instagram', ''),
            static.get('social_links', {}).get('x', '')
        ]
    }
    organization['sameAs'] = [url for url in organization['sameAs'] if url]
    website = {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': site_title,
        'url': base_url or static.get('og_url', '')
    }
    lastmod = None
    timestamps = [str(entry.get('timestamp', '')) for entry in data.get('change_log', []) if entry.get('timestamp')]
    for ts in sorted(timestamps, reverse=True):
        try:
            lastmod = datetime.fromisoformat(ts.replace('Z', '+00:00')).date().isoformat()
            break
        except Exception:
            continue
    if not lastmod:
        lastmod = datetime.now(timezone.utc).date().isoformat()
    return {
        'base_url': base_url,
        'title': site_title,
        'description': description,
        'image_url': image_url,
        'canonical': base_url or static.get('og_url', ''),
        'organization_json': json.dumps(organization, ensure_ascii=False),
        'website_json': json.dumps(website, ensure_ascii=False),
        'lastmod': lastmod,
    }

def render_sitemap_xml(base_url: str, lastmod: str) -> str:
    if not base_url:
        return ''
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url>\n'
        f'    <loc>{escape(base_url)}</loc>\n'
        f'    <lastmod>{escape(lastmod)}</lastmod>\n'
        '  </url>\n'
        '</urlset>\n'
    )


def activity_category_label(value: str) -> str:
    labels = {
        'record': '活動記録',
        'event': 'イベント告知',
        'other': 'その他',
    }
    return labels.get(str(value or 'record').strip().lower(), 'その他')


def render_carousel(images: list[str], label: str, max_images: int = 10, extra_class: str = '') -> str:
    if not images:
        return ''
    images = list(images)[:max_images]
    label_key = re.sub(r'\s+', '-', str(label or 'image')).strip('-')
    class_key = re.sub(r'\s+', '-', str(extra_class or '')).strip('-')
    gallery_id = 'carousel-' + label_key + ('-' + class_key if class_key else '')
    slides = []
    dots = []
    for index, image in enumerate(images):
        alt = f'{label} {index + 1}'
        slides.append(
            f'<button class="carousel-slide" type="button" data-lightbox-gallery="{escape(gallery_id)}" data-lightbox-index="{index}" data-lightbox-caption="{escape(alt)}" aria-label="{escape(alt)}を拡大">'
            f'<img src="{escape(image)}" alt="{escape(alt)}" draggable="false">'
            '</button>'
        )
        dots.append(f'<button class="carousel-dot{" is-active" if index == 0 else ""}" type="button" aria-label="{escape(alt)}へ移動"></button>')
    controls = ''
    dots_html = ''
    if len(images) > 1:
        controls = """
        <button class="carousel-button prev" type="button" aria-label="前へ">
          <i class="fa-solid fa-chevron-left"></i>
        </button>
        <button class="carousel-button next" type="button" aria-label="次へ">
          <i class="fa-solid fa-chevron-right"></i>
        </button>
        """
        dots_html = f'<div class="carousel-dots">{"".join(dots)}</div>'
    class_attr = f'carousel {extra_class}'.strip()
    return f"""
    <div class="{escape(class_attr)}" data-carousel>
      <div class="carousel-viewport">
        <div class="carousel-track">
          {''.join(slides)}
        </div>
      </div>
      {controls}
      {dots_html}
    </div>
    """


def exhibition_dm_images(item: dict[str, Any]) -> list[str]:
    images = item.get('dm_images') or []
    if isinstance(images, str):
        images = [images]
    images = [str(image) for image in images if image]
    if not images and item.get('dm_image'):
        images = [str(item.get('dm_image'))]
    return images[:2]


def render_dm_carousel(item: dict[str, Any], label: str) -> str:
    images = exhibition_dm_images(item)
    if not images:
        return ''
    return f'<div class="dm-poster-wrap">{render_carousel(images, label, max_images=2, extra_class="dm-carousel")}</div>'


def render_image_grid(images: list[str], label: str, gallery_id: str) -> str:
    if not images:
        return ''
    images = list(images)[:10]
    visible_count = min(len(images), 4)
    grid_classes = ['image-grid', f'image-count-{visible_count}']
    if len(images) == 1:
        ratio = image_aspect(images[0])
        # PC版1枚表示: 横長(16:9以上)はカード幅に合わせた自然比率、
        # それ以外は16:9黒枠内で上下を揃えて全体表示する。
        grid_classes.append('image-single-wide' if ratio >= (16 / 9) else 'image-single-framed')
    cards = []
    hidden_cards = []
    more_count = max(0, len(images) - visible_count)
    for index, image in enumerate(images):
        alt = f'{label} {index + 1}'
        classes = ['image-grid-item']
        if index == 0:
            classes.append('is-primary')
        if index >= visible_count:
            classes.append('is-lightbox-only')
        more_badge = ''
        if index == visible_count - 1 and more_count:
            more_badge = f'<span class="image-grid-more">+{more_count}</span>'
        card = (
            f'<button class="{" ".join(classes)}" type="button" data-lightbox-gallery="{escape(gallery_id)}" '
            f'data-lightbox-index="{index}" data-lightbox-caption="{escape(alt)}" aria-label="{escape(alt)}を拡大">'
            f'<img src="{escape(image)}" alt="{escape(alt)}" loading="lazy">{more_badge}</button>'
        )
        if index >= visible_count:
            hidden_cards.append(card)
        else:
            cards.append(card)
    return (
        f'<div class="{" ".join(grid_classes)}" data-lightbox-set="{escape(gallery_id)}" '
        f'data-total-images="{len(images)}">{"".join(cards)}{"".join(hidden_cards)}</div>'
    )


def _looks_legacy_summary_segment(segment: str) -> bool:
    return bool(
        segment == '新歓イベントカレンダーを更新'
        or re.match(r'^(活動記事|活動記録・告知|ご依頼事例|取り組み事例|取り組み)「.+?」(?:を追加|を更新|の情報を公開)?$', segment)
        or re.match(r'^展示会「.+?」(?:を追加|を更新|の情報を公開)?$', segment)
    )


def _split_summary_segments(summary: str) -> list[str]:
    normalized = str(summary or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not normalized:
        return []
    if '\n' in normalized:
        return [segment.strip() for segment in re.split(r'\n+', normalized) if segment.strip()]
    legacy_parts = [segment.strip() for segment in re.split(r'\s/\s', normalized) if segment.strip()]
    if len(legacy_parts) > 1 and all(_looks_legacy_summary_segment(segment) for segment in legacy_parts):
        return legacy_parts
    return [normalized]


def _segment_public_key(segment: str) -> tuple[str | None, str | None]:
    if segment == '新歓イベントカレンダーを更新':
        return ('recruit', None)
    patterns = [
        (r'^(活動記事|活動記録・告知)「(.+?)」(?:を追加|を更新|の情報を公開)?$', 'activity'),
        (r'^(ご依頼事例|取り組み事例|取り組み)「(.+?)」(?:を追加|を更新|の情報を公開)?$', 'request'),
        (r'^展示会「(.+?)」(?:を追加|を更新|の情報を公開)?$', 'exhibition'),
    ]
    for pattern, kind in patterns:
        match = re.match(pattern, segment)
        if match:
            title = match.groups()[-1]
            return (kind, title)
    return (None, None)


def _canonical_public_summary(kind: str, title: str | None = None) -> str:
    if kind == 'recruit':
        return '新歓イベントカレンダーを更新'
    if kind == 'activity' and title:
        return f'活動記録・告知「{title}」'
    if kind == 'request' and title:
        return f'取り組み「{title}」'
    if kind == 'exhibition' and title:
        return f'展示会「{title}」の情報を公開'
    return title or ''


def render_update_log(change_log: list[dict[str, Any]], data: dict[str, Any]) -> str:
    if not change_log:
        return '<div class="empty-message">まだ更新履歴はありません。</div>'

    current_titles = {
        'activity': {str(item.get('title', '')) for item in data.get('activities', [])},
        'request': {str(item.get('title', '')) for item in data.get('requests', [])},
        'exhibition': set(),
    }
    exhibitions = data.get('exhibitions', {}) or {}
    upcoming_items = exhibitions.get('upcoming', []) or []
    if isinstance(upcoming_items, dict):
        upcoming_items = [upcoming_items]
    for item in upcoming_items:
        if item and item.get('title'):
            current_titles['exhibition'].add(str(item.get('title')))
    for item in exhibitions.get('archive', []) or []:
        if item and item.get('title'):
            current_titles['exhibition'].add(str(item.get('title')))

    grouped: OrderedDict[str, OrderedDict[str, None]] = OrderedDict()
    ordered_entries = sorted(change_log, key=lambda entry: str(entry.get('timestamp', '')), reverse=True)
    for entry in ordered_entries:
        date_key = fmt_date(str(entry.get('timestamp', '')))
        grouped.setdefault(date_key, OrderedDict())
        for segment in _split_summary_segments(str(entry.get('summary', ''))):
            kind, title = _segment_public_key(segment)
            if kind == 'recruit':
                grouped[date_key][_canonical_public_summary('recruit')] = None
                continue
            if kind in current_titles:
                if title and title in current_titles[kind]:
                    grouped[date_key][_canonical_public_summary(kind, title)] = None
                continue
            grouped[date_key][segment] = None

    items = []
    for date_key, summaries in grouped.items():
        bullets = ''.join(f'<li>{escape(summary)}</li>' for summary in summaries.keys())
        if not bullets:
            continue
        items.append(
            f"""
            <li class="update-log-item">
              <span class="update-log-date">{escape(date_key)}</span>
              <ul class="update-log-bullets">{bullets}</ul>
            </li>
            """
        )
    if not items:
        return '<div class="empty-message">まだ更新履歴はありません。</div>'
    return f'<ul class="update-log-list">{"".join(items)}</ul>'


def render_timeline(schedule: list[dict[str, str]]) -> str:
    color_class = {
        'yellow': 'border-yellow',
        'blue': 'border-blue',
        'green': 'border-green',
        'white': 'border-white',
    }
    items = []
    for row in schedule:
        items.append(
            f"""
            <div class="timeline-item">
              <div class="timeline-dot {color_class.get(row.get('accent', 'yellow'), 'border-yellow')}"></div>
              <div class="timeline-date">{escape(row.get('period', ''))}</div>
              <div class="timeline-content">{escape(row.get('label', ''))}</div>
            </div>
            """
        )
    return f'<div class="timeline">{"".join(items)}</div>'


def render_info_points(points: list[dict[str, str]]) -> str:
    return ''.join(
        f"""
        <article class="info-point">
          <div class="info-point-label">{escape(point.get('label', ''))}</div>
          <div class="info-point-text">{escape(point.get('text', ''))}</div>
        </article>
        """
        for point in points
    )



def render_activity_cards(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty-message">公開中の記事はありません。</div>'
    ordered = sorted(items, key=lambda x: x.get('created_at', ''), reverse=True)
    cards = []
    for item in ordered:
        cards.append(
            f"""
            <article class="article-card">
              <div class="article-meta">
                <span>{escape(activity_category_label(item.get('category', 'record')))}</span>
                <time datetime="{escape(item.get('created_at', ''))}">{fmt_date(item.get('created_at', ''))}</time>
              </div>
              <h4 class="article-title">{escape(item.get('title', ''))}</h4>
              <p class="article-body">{nl2br(item.get('body', ''))}</p>
              {render_image_grid(item.get('images', []), item.get('title', '活動記録・告知'), 'activity-' + str(item.get('id', '')))}
            </article>
            """
        )
    return f'<div class="article-grid">{"".join(cards)}</div>'


def render_request_cards(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty-message">公開中の事例はありません。</div>'
    ordered = sorted(items, key=lambda x: int(x.get('sort_order', 9999)))
    cards = []
    for item in ordered:
        cards.append(
            f"""
            <article class="request-card">
              <div class="request-meta"><span>過去の取り組み事例</span></div>
              <h4 class="request-title">{escape(item.get('title', ''))}</h4>
              <p class="request-body">{nl2br(item.get('body', ''))}</p>
              {render_image_grid(item.get('images', []), item.get('title', '取り組み事例'), 'request-' + str(item.get('id', '')))}
            </article>
            """
        )
    return f'<div class="request-grid">{"".join(cards)}</div>'

def render_exhibition_meta(item: dict[str, Any], include_address: bool = True) -> str:
    venue_parts = [f'<span>{escape(item.get("venue_name", ""))}</span>' if item.get('venue_name') else '']
    if include_address and item.get('venue_address'):
        venue_parts.append(f'<span class="venue-address">{escape(item.get("venue_address", ""))}</span>')
    venue_html = ''.join(part for part in venue_parts if part)
    date_time_parts = []
    if item.get('date_line'):
        date_time_parts.append(f'<span>{escape(item.get("date_line", ""))}</span>')
    if item.get('time_line'):
        date_time_parts.append(f'<span class="venue-address">{escape(item.get("time_line", ""))}</span>')
    date_time_html = ''.join(date_time_parts)
    rows = []
    if date_time_html:
        rows.append(
            '<div class="exhibition-meta-row">'
            '<div class="exhibition-meta-label">会期</div>'
            f'<div class="exhibition-meta-value venue-stack">{date_time_html}</div>'
            '</div>'
        )
    if venue_html:
        rows.append(
            '<div class="exhibition-meta-row">'
            '<div class="exhibition-meta-label">会場</div>'
            f'<div class="exhibition-meta-value venue-stack">{venue_html}</div>'
            '</div>'
        )
    if not rows:
        return ''
    return f"""
    <div class="exhibition-meta compact-meta">
      {''.join(rows)}
    </div>
    """



def render_exhibition_upcoming(items: list[dict[str, Any]]) -> str:
    if not items:
        return ''
    cards = []
    for index, upcoming in enumerate(items):
        map_embed = ''
        if upcoming.get('map_embed_url'):
            map_embed = f"""
            <div class="map-embed">
              <iframe src="{escape(upcoming['map_embed_url'])}" loading="lazy" referrerpolicy="no-referrer-when-downgrade" title="{escape(upcoming.get('title', ''))} 会場マップ"></iframe>
            </div>
            """
        overview = upcoming.get('overview') or upcoming.get('theme', '')
        poster = render_dm_carousel(upcoming, upcoming.get('title', '展示会DM'))
        cards.append(f"""
        <article class="simple-card glass-card exhibition-card upcoming-card">
          <div class="exhibition-heading">
            <div class="exhibition-kicker">{'NEXT EXHIBITION' if index == 0 else 'UPCOMING'}</div>
            <h4 class="exhibition-title">{escape(upcoming.get('title', ''))}</h4>
          </div>
          <div class="exhibition-hero{' no-poster' if not poster else ''}">
            <div class="exhibition-body">
              <p class="exhibition-overview">{nl2br(overview)}</p>
              {render_exhibition_meta(upcoming, include_address=True)}
              {map_embed}
            </div>
            {poster}
          </div>
        </article>
        """)
    return f'<div class="upcoming-list">{"".join(cards)}</div>'


def _resolve_asset_path(src: str) -> Path | None:
    value = str(src or '').split('?', 1)[0].lstrip('/')
    if not value:
        return None
    candidates = [Path(value)]
    if value.startswith('assets/'):
        candidates.append(ASSET_SOURCE_ROOT / value)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _read_svg_aspect(path: Path) -> float | None:
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')[:1200]
    except Exception:
        return None
    viewbox = re.search(r'viewBox=["\']\s*[-0-9.]+\s+[-0-9.]+\s+([0-9.]+)\s+([0-9.]+)\s*["\']', text)
    if viewbox:
        w, h = float(viewbox.group(1)), float(viewbox.group(2))
        return w / h if h else None
    width = re.search(r'width=["\']([0-9.]+)', text)
    height = re.search(r'height=["\']([0-9.]+)', text)
    if width and height:
        w, h = float(width.group(1)), float(height.group(1))
        return w / h if h else None
    return None


def _read_png_aspect(path: Path) -> float | None:
    try:
        with path.open('rb') as f:
            header = f.read(24)
        if header.startswith(b'\x89PNG\r\n\x1a\n') and len(header) >= 24:
            w = int.from_bytes(header[16:20], 'big')
            h = int.from_bytes(header[20:24], 'big')
            return w / h if h else None
    except Exception:
        return None
    return None


def _read_jpeg_aspect(path: Path) -> float | None:
    try:
        with path.open('rb') as f:
            if f.read(2) != b'\xff\xd8':
                return None
            while True:
                marker_start = f.read(1)
                if not marker_start:
                    return None
                if marker_start != b'\xff':
                    continue
                marker = f.read(1)
                while marker == b'\xff':
                    marker = f.read(1)
                if marker in [b'\xc0', b'\xc1', b'\xc2', b'\xc3', b'\xc5', b'\xc6', b'\xc7', b'\xc9', b'\xca', b'\xcb', b'\xcd', b'\xce', b'\xcf']:
                    f.read(2)
                    f.read(1)
                    h = int.from_bytes(f.read(2), 'big')
                    w = int.from_bytes(f.read(2), 'big')
                    return w / h if h else None
                length_bytes = f.read(2)
                if len(length_bytes) < 2:
                    return None
                length = int.from_bytes(length_bytes, 'big')
                f.seek(length - 2, 1)
    except Exception:
        return None


def image_aspect(src: str) -> float:
    path = _resolve_asset_path(src)
    if not path:
        return 1.0
    suffix = path.suffix.lower()
    if suffix == '.svg':
        ratio = _read_svg_aspect(path)
    elif suffix == '.png':
        ratio = _read_png_aspect(path)
    elif suffix in {'.jpg', '.jpeg'}:
        ratio = _read_jpeg_aspect(path)
    else:
        ratio = None
    if not ratio or ratio <= 0:
        return 1.0
    return max(0.35, min(3.2, ratio))


def render_work_card(index: int, work: dict[str, Any], ratio: float, extra_class: str = '') -> str:
    caption = (work.get('title', '作品画像') or '') + ((' / ' + work.get('artist', '')) if work.get('artist') else '')
    classes = 'work-card' + (f' {extra_class}' if extra_class else '')
    return f'''
      <article class="{classes}" data-work-card data-aspect="{ratio:.4f}" style="--work-order: {index};">
        <button class="work-image-button" type="button" data-lightbox-gallery="{escape(work.get('_gallery_id', 'recent-works'))}" data-lightbox-index="{index}" data-lightbox-caption="{escape(caption)}" aria-label="{escape(work.get('title', '作品画像'))}を拡大">
          <img src="{escape(work.get('image', ''))}" alt="{escape(work.get('title', '作品画像'))}" loading="lazy">
        </button>
        <div class="work-index">{index + 1:02d}</div>
        <div class="work-title">{escape(work.get('title', ''))}</div>
        <div class="work-artist">{escape(work.get('artist', ''))}</div>
      </article>
    '''


def render_work_gallery(works: list[dict[str, Any]], gallery_id: str) -> str:
    if not works:
        return ''

    enriched: list[dict[str, Any]] = []
    for index, work in enumerate(works):
        copied = dict(work)
        ratio = image_aspect(copied.get('image', ''))
        copied['_index'] = index
        copied['_ratio'] = ratio
        copied['_gallery_id'] = gallery_id
        copied['_height_score'] = 1.0 / max(ratio, 0.35)
        enriched.append(copied)

    # 横幅が縦幅の2倍以上ある作品は、展示カード幅を活かすため上段で2列分を使う。
    panoramas = [work for work in enriched if work['_ratio'] >= 2.0]
    remaining = [work for work in enriched if work['_ratio'] < 2.0]

    # 残りは順序入れ替え可。高さ差が最小になる2列分割をビルド時に探索する。
    # 作品数は通常少数なので、完全探索で左右差を最小化する。多すぎる場合のみLPTへフォールバック。
    scores = [work['_height_score'] + 0.12 for work in remaining]
    columns: list[list[dict[str, Any]]] = [[], []]
    if remaining and len(remaining) <= 18:
        total = sum(scores)
        best_mask = 0
        best_diff = float('inf')
        for mask in range(1 << len(remaining)):
            left = sum(scores[i] for i in range(len(remaining)) if mask & (1 << i))
            diff = abs(total - 2 * left)
            if diff < best_diff:
                best_diff = diff
                best_mask = mask
        columns = [
            [work for i, work in enumerate(remaining) if best_mask & (1 << i)],
            [work for i, work in enumerate(remaining) if not (best_mask & (1 << i))]
        ]
        columns[0].sort(key=lambda work: work['_height_score'], reverse=True)
        columns[1].sort(key=lambda work: work['_height_score'], reverse=True)
    else:
        remaining.sort(key=lambda work: work['_height_score'], reverse=True)
        heights = [0.0, 0.0]
        for work in remaining:
            target = 0 if heights[0] <= heights[1] else 1
            columns[target].append(work)
            heights[target] += work['_height_score'] + 0.12

    full_html = ''.join(
        render_work_card(work['_index'], work, work['_ratio'], 'is-full')
        for work in panoramas
    )
    column_html = []
    for column in columns:
        cards = ''.join(
            render_work_card(work['_index'], work, work['_ratio'])
            for work in column
        )
        column_html.append(f'<div class="work-column">{cards}</div>')

    return (
        '<div class="work-gallery work-gallery-balanced" data-work-gallery>'
        f'<div class="work-full">{full_html}</div>'
        f'<div class="work-columns">{"".join(column_html)}</div>'
        '</div>'
    )


def render_exhibition_recent(recent: dict[str, Any] | None) -> str:
    if not recent:
        return '<div class="empty-message">最近の展示会情報はまだありません。</div>'
    works = recent.get('works', [])
    gallery_id = 'recent-works-' + re.sub(r'[^a-zA-Z0-9_-]+', '-', str(recent.get('id', 'recent'))).strip('-')
    work_gallery = render_work_gallery(works, gallery_id)
    overview = recent.get('overview') or recent.get('theme', '')
    poster = render_dm_carousel(recent, recent.get('title', '展示会DM'))
    return f"""
    <article class="simple-card glass-card exhibition-card recent-card">
      <div class="exhibition-heading">
        <div class="exhibition-kicker">RECENT EXHIBITION</div>
        <h4 class="exhibition-title">{escape(recent.get('title', ''))}</h4>
      </div>
      <div class="exhibition-hero{' no-poster' if not poster else ''}">
        <div class="exhibition-body">
          <p class="exhibition-overview">{nl2br(overview)}</p>
          {render_exhibition_meta(recent, include_address=True)}
        </div>
        {poster}
      </div>
      {work_gallery}
    </article>
    """


def render_recruit_calendar(calendar: dict[str, Any]) -> str:
    images = calendar.get('images', []) if calendar else []
    if not images:
        return '<div class="empty-message">現在公開中の新歓イベントカレンダー画像はありません。</div>'
    return render_carousel(images, '新歓イベントカレンダー', extra_class='recruit-carousel')

def render_exhibition_archive(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<div class="empty-message">公開中のアーカイブはありません。</div>'
    cards = []
    for item in items:
        poster = render_dm_carousel(item, item.get('title', '展示会DM'))
        overview = item.get('overview') or item.get('theme', '')
        cards.append(
            f"""
            <article class="simple-card glass-card exhibition-card archive-card">
              <div class="exhibition-hero archive-hero{' no-poster' if not poster else ''}">
                <div class="exhibition-body">
                  <div class="exhibition-kicker">ARCHIVE</div>
                  <h4 class="exhibition-title archive-title">{escape(item.get('title', ''))}</h4>
                  <p class="exhibition-overview archive-overview">{nl2br(overview)}</p>
                  {render_exhibition_meta(item, include_address=True)}
                  {'<div class="archive-actions"><a class="archive-link" href="' + escape(item.get('folder_url', '')) + '" target="_blank" rel="noopener noreferrer">Google Driveで見る <i class="fa-solid fa-up-right-from-square"></i></a></div>' if item.get('folder_url') else ''}
                </div>
                {poster}
              </div>
            </article>
            """
        )
    return f'<div class="archive-list">{"".join(cards)}</div>'

def render_page(static: dict[str, Any], data: dict[str, Any]) -> str:
    recruit = static['recruit_static']
    requests_static = static['requests_static']
    seo = build_seo_context(static, data)
    exhibitions = data.get('exhibitions', {})
    upcoming_items = exhibitions.get('upcoming', []) or []
    if isinstance(upcoming_items, dict):
        upcoming_items = [upcoming_items]
    upcoming_items = sorted(upcoming_items, key=lambda item: str(item.get('start_date', '')))
    archive_items = sorted(exhibitions.get('archive', []) or [], key=lambda item: str(item.get('start_date', '')), reverse=True)
    recent = archive_items[0] if archive_items else None
    archive_rest = archive_items[1:] if len(archive_items) > 1 else []
    return f'''<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(seo['title'])}</title>
  <meta name="description" content="{escape(seo['description'])}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <link rel="canonical" href="{escape(seo['canonical'])}">
  <meta property="og:title" content="{escape(seo['title'])}">
  <meta property="og:description" content="{escape(seo['description'])}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{escape(seo['canonical'])}">
  <meta property="og:image" content="{escape(seo['image_url'])}">
  <meta property="og:image:alt" content="神戸大学美術部凌美会 ロゴ">
  <meta property="og:site_name" content="{escape(seo['title'])}">
  <meta property="og:locale" content="ja_JP">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(seo['title'])}">
  <meta name="twitter:description" content="{escape(seo['description'])}">
  <meta name="twitter:image" content="{escape(seo['image_url'])}">
  <script type="application/ld+json">{seo['organization_json']}</script>
  <script type="application/ld+json">{seo['website_json']}</script>
  <link rel="stylesheet" href="stylesheet.css">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap" rel="stylesheet">
  <script defer src="site.js"></script>
</head>
<body>
  <nav class="global-nav">
    <div class="nav-container">
      <a href="#home" class="nav-brand">
        <img src="logo.png" alt="凌美会 ロゴ" class="nav-brand-logo">
        <span class="nav-brand-text">{escape(static['club_name_jp'])}</span>
      </a>
      <ul class="nav-menu">
        <li><a href="#about">ABOUT</a></li>
        <li><a href="#info-tabs">INFO</a></li>
      </ul>
      <ul class="nav-links">
        <li><a href="{escape(static['social_links']['instagram'])}" target="_blank" rel="noopener noreferrer" class="social-link instagram" aria-label="Instagram"><i class="fa-brands fa-instagram"></i></a></li>
        <li><a href="{escape(static['social_links']['x'])}" target="_blank" rel="noopener noreferrer" class="social-link x-twitter" aria-label="X (Twitter)"><i class="fa-brands fa-x-twitter"></i></a></li>
        <li><a href="{escape(static['social_links']['email'])}" class="social-link email" aria-label="Email"><i class="fa-regular fa-envelope"></i></a></li>
      </ul>
    </div>
  </nav>

  <header id="home" class="hero-section">
    <div class="hero-content">
      <img src="logo.png" alt="凌美会 ロゴ" class="hero-logo">
      <p class="hero-kicker">{escape(static['hero_kicker'])}</p>
      <h1 class="hero-title">{escape(static['hero_title'])}</h1>
      <p class="hero-subtitle">{escape(static['hero_subtitle'])}</p>
    </div>
    <div class="decoration circle-green"></div>
    <div class="decoration square-blue"></div>
    <div class="grid-overlay"></div>
  </header>

  <main class="main-content">
    <section id="about" class="sub-section">
      <div class="section-header">
        <p class="section-label">ABOUT US</p>
        <h2 class="section-title">基本情報</h2>
        <p class="section-subtitle">{escape(static['intro_text'])}</p>
      </div>
      <article class="simple-card glass-card">
        <p class="eyebrow">UPDATE LOG</p>
        {render_update_log(data.get('change_log', []), data)}
      </article>
    </section>

    <section id="info-tabs" class="sub-section">
      <div class="section-header">
        <p class="section-label">INFORMATION</p>
        <h2 class="section-title">ご案内</h2>
        <p class="section-subtitle">展示会、活動記録・告知、入部、ご依頼に関する情報をまとめています。</p>
      </div>

      <div class="glass-card tab-shell" data-tab-shell>
        <div class="tab-buttons" role="tablist" aria-label="情報タブ">
          <button class="tab-button is-active" type="button" data-tab-target="exhibitions">展覧会</button>
          <button class="tab-button" type="button" data-tab-target="activities">活動記録・告知</button>
          <button class="tab-button" type="button" data-tab-target="recruit">入部希望の方</button>
          <button class="tab-button" type="button" data-tab-target="requests">ご依頼の方</button>
        </div>

        <section class="tab-panel is-active" data-tab-panel="exhibitions">
          <div class="section-header">
            <p class="eyebrow">EXHIBITIONS</p>
            <h3 class="section-title" style="font-size: clamp(1.6rem, 3vw, 2.3rem);">展示会情報</h3>
            <p class="section-subtitle">開催予定の展示会と最近の展示記録を掲載しています。</p>
          </div>
          <div class="exhibition-stack">
            {render_exhibition_upcoming(upcoming_items)}
            {render_exhibition_recent(recent)}
            <article class="simple-card glass-card">
              <p class="eyebrow">ARCHIVE</p>
              <h4 style="font-size:1.28rem; margin-bottom: 12px;">展示会アーカイブ</h4>
              {render_exhibition_archive(archive_rest)}
            </article>
          </div>
        </section>

        <section class="tab-panel" data-tab-panel="activities">
          <div class="section-header">
            <p class="eyebrow">ACTIVITIES</p>
            <h3 class="section-title" style="font-size: clamp(1.6rem, 3vw, 2.3rem);">活動記録・告知</h3>
            <p class="section-subtitle">展示以外の活動やイベントの記録です。</p>
          </div>
          {render_activity_cards(data.get('activities', []))}
        </section>

        <section class="tab-panel" data-tab-panel="recruit">
          <div class="section-header">
            <p class="eyebrow">JOIN US</p>
            <h3 class="section-title" style="font-size: clamp(1.6rem, 3vw, 2.3rem);">入部希望の方へ</h3>
            <p class="section-subtitle">{escape(recruit['summary'])}</p>
          </div>
          <div class="info-grid">{render_info_points(recruit['info_points'])}</div>
          <div class="simple-card glass-card">
            <p class="eyebrow">MATERIALS</p>
            <h4 style="font-size:1.28rem;">使えるもの</h4>
            <div class="material-chip-grid">{''.join(f'<span>{escape(x)}</span>' for x in recruit['materials'])}</div>
          </div>
          <div style="height: 18px;"></div>
          <div class="simple-card glass-card">
            <p class="eyebrow">ANNUAL SCHEDULE</p>
            <h4 style="font-size:1.28rem;">年間スケジュール</h4>
            {render_timeline(recruit['annual_schedule'])}
          </div>
          <div style="height: 18px;"></div>
          <div class="simple-card glass-card">
            <p class="eyebrow">WELCOME CALENDAR</p>
            <h4 style="font-size:1.28rem;">{escape(data.get('recruit_calendar', {}).get('label', '新歓イベントカレンダー'))}</h4>
            {render_recruit_calendar(data.get('recruit_calendar', {}))}
          </div>
        </section>

        <section class="tab-panel" data-tab-panel="requests">
          <div class="section-header">
            <p class="eyebrow">REQUESTS</p>
            <h3 class="section-title" style="font-size: clamp(1.6rem, 3vw, 2.3rem);">ご依頼の方へ</h3>
            <p class="section-subtitle">{escape(requests_static['summary'])}</p>
          </div>
          <div class="simple-card glass-card request-contact-card" style="margin-bottom: 18px;">
            <p class="request-contact-heading">お問い合わせ先</p>
            <ul class="request-contact-list">
              <li><span>Email</span><a href="mailto:{escape(requests_static['contact_email'])}">{escape(requests_static['contact_email'])}</a></li>
              <li><span>Instagram</span><a href="{escape(static['social_links']['instagram'])}" target="_blank" rel="noopener noreferrer">{escape(requests_static.get('contact_instagram', '@ryobi.welcome'))}</a></li>
              <li><span>X</span><a href="{escape(static['social_links']['x'])}" target="_blank" rel="noopener noreferrer">{escape(requests_static.get('contact_x', '@Art_Club_Ryobi'))}</a></li>
            </ul>
          </div>
          {render_request_cards(data.get('requests', []))}
        </section>
      </div>
    </section>
  </main>

  <footer>
    <p>{escape(static['copyright'])}</p>
  </footer>
</body>
</html>
'''


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    for file_path in src.rglob('*'):
        if file_path.is_dir():
            continue
        relative = file_path.relative_to(src)
        target = dst / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, target)


def main() -> None:
    parser = argparse.ArgumentParser(description='Build the Ryobi static site from a normalized content snapshot.')
    parser.add_argument('--static-config', required=True, help='Path to site_static.json')
    parser.add_argument('--content-snapshot', required=True, help='Path to normalized content snapshot JSON')
    parser.add_argument('--assets-root', required=True, help='Root directory for local assets referenced by the snapshot')
    parser.add_argument('--output-dir', required=True, help='Destination directory for built site')
    args = parser.parse_args()

    static = load_json(Path(args.static_config))
    data = load_json(Path(args.content_snapshot))
    output_dir = Path(args.output_dir)
    assets_root = Path(args.assets_root)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    ensure_dir(output_dir)

    global ASSET_SOURCE_ROOT
    ASSET_SOURCE_ROOT = Path(args.assets_root).parent
    page_html = render_page(static, data)
    seo = build_seo_context(static, data)
    (output_dir / 'index.html').write_text(page_html, encoding='utf-8')
    sitemap_xml = render_sitemap_xml(seo['base_url'], seo['lastmod'])
    if sitemap_xml:
        (output_dir / 'sitemap.xml').write_text(sitemap_xml, encoding='utf-8')
    verification_dir = Path(args.static_config).parent / "verification"
    for file in verification_dir.iterdir():
        if file.is_file():
            shutil.copy2(file, output_dir / file.name)
    shutil.copy2(Path(args.static_config).parent / 'stylesheet.css', output_dir / 'stylesheet.css')
    shutil.copy2(Path(args.static_config).parent / 'site.js', output_dir / 'site.js')
    shutil.copy2(Path(args.static_config).parent / 'logo.png', output_dir / 'logo.png')
    copy_tree(assets_root, output_dir / 'assets')
    print(f'Built site at {output_dir}')


if __name__ == '__main__':
    main()
