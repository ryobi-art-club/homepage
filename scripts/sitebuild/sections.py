"""ページの部品ごとの HTML（更新履歴・展示会・活動記録・ご依頼・入部案内・ヒーロー）。
管理画面のプレビュー（homepage-cms の UiPreview.html）が同じ部品をまねているので、見た目を変えたら両方を直す（README「管理画面のプレビュー」）。"""
from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any
from urllib.parse import quote

from .html import Markup, fmt_date, html, rich_text
from .images import image_aspect

# ---------- 画像 ----------

CAROUSEL_CONTROLS = Markup(
    '<button class="carousel-button prev" type="button" aria-label="前へ"><i class="fa-solid fa-chevron-left"></i></button>'
    '<button class="carousel-button next" type="button" aria-label="次へ"><i class="fa-solid fa-chevron-right"></i></button>'
)


def render_carousel(images: list[str], label: str, max_images: int = 10, extra_class: str = '', style: str = '') -> Markup | str:
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
        slides.append(html(
            '<button class="carousel-slide" type="button" data-lightbox-gallery="{gallery}" data-lightbox-index="{index}" '
            'data-lightbox-caption="{alt}" aria-label="{alt}を拡大"><img src="{image}" alt="{alt}" draggable="false"></button>',
            gallery=gallery_id, index=index, alt=alt, image=image))
        dots.append(html('<button class="carousel-dot{active}" type="button" aria-label="{alt}へ移動"></button>',
                         active=' is-active' if index == 0 else '', alt=alt))
    many = len(images) > 1
    return html('''
        <div class="{classes}"{style} data-carousel>
          <div class="carousel-viewport"><div class="carousel-track">{slides}</div></div>
          {controls}
          {dots}
        </div>''',
        classes=f'carousel {extra_class}'.strip(), style=style and html(' style="{style}"', style=style), slides=slides,
        controls=many and CAROUSEL_CONTROLS, dots=many and html('<div class="carousel-dots">{dots}</div>', dots=dots))


def render_image_grid(images: list[str], label: str, gallery_id: str) -> Markup | str:
    """記事・事例の写真。4枚まで並べ、残りは「+N」で拡大表示だけに出す。"""
    if not images:
        return ''
    images = list(images)[:10]
    visible_count = min(len(images), 4)
    grid_classes = ['image-grid', f'image-count-{visible_count}']
    if len(images) == 1:
        # 1枚のとき：横長（16:9以上）はカードの幅に合わせ、それ以外は16:9の黒い枠に全体を収める
        grid_classes.append('image-single-wide' if image_aspect(images[0]) >= (16 / 9) else 'image-single-framed')
    more_count = len(images) - visible_count
    cards = []
    for index, image in enumerate(images):
        classes = ['image-grid-item'] + (['is-primary'] if index == 0 else []) + (['is-lightbox-only'] if index >= visible_count else [])
        alt = f'{label} {index + 1}'
        cards.append(html(
            '<button class="{classes}" type="button" data-lightbox-gallery="{gallery}" data-lightbox-index="{index}" '
            'data-lightbox-caption="{alt}" aria-label="{alt}を拡大"><img src="{image}" alt="{alt}" loading="lazy">{more}</button>',
            classes=' '.join(classes), gallery=gallery_id, index=index, alt=alt, image=image,
            more=index == visible_count - 1 and more_count > 0 and html('<span class="image-grid-more">+{count}</span>', count=more_count)))
    return html('<div class="{classes}" data-lightbox-set="{gallery}" data-total-images="{total}">{cards}</div>',
                classes=' '.join(grid_classes), gallery=gallery_id, total=len(images), cards=cards)


def render_work_gallery(works: list[dict[str, Any]], gallery_id: str) -> Markup | str:
    """出展作品を登録順のまま行ごとに並べる。行の高さをそろえ、幅は縦横比に合わせる
    （行の折り返しはブラウザがする。stylesheet.css の .work-gallery）。"""
    if not works:
        return ''
    cards = []
    for index, work in enumerate(works):
        ratio = image_aspect(work.get('image', ''))
        title = work.get('title', '')
        caption = (title or '') + ((' / ' + work['artist']) if work.get('artist') else '')
        cards.append(html('''
            <article class="work-card" data-work-card data-aspect="{aspect}" style="--ratio: {layout_ratio};">
              <button class="work-image-button" type="button" data-lightbox-gallery="{gallery}" data-lightbox-index="{index}" data-lightbox-caption="{caption}" aria-label="{name}を拡大">
                <img src="{image}" alt="{name}" loading="lazy">
              </button>
              <div class="work-index">{number}</div>
              <div class="work-title">{title}</div>
              <div class="work-artist">{artist}</div>
            </article>''',
            # 行の中の幅の比。極端な縦長・横長だけ枠の比を丸め、画像は枠の中に収める
            aspect=f'{ratio:.4f}', layout_ratio=f'{min(max(ratio, 0.4), 3.0):.4f}', gallery=gallery_id, index=index,
            caption=caption, name=work.get('title', '作品画像'), image=work.get('image', ''), number=f'{index + 1:02d}',
            title=title, artist=work.get('artist', '')))
    return html('<p class="work-gallery-label">出展作品<span>{count}点</span></p><div class="work-gallery" data-work-gallery>{cards}</div>',
                count=len(works), cards=cards)


# ---------- 更新履歴 ----------

# 更新履歴の文言。管理画面（ContentHistory.js の CHANGE_LOG_ITEM_LISTS）と同じにする（homepage-cms の README「8-4」）
CHANGE_LOG_RECRUIT_TEXT = '新歓イベントカレンダーを更新'
CHANGE_LOG_TEXT = {
    'activity': '活動記録・告知「{}」',
    'request': '取り組み「{}」',
    'exhibition': '展示会「{}」の情報を公開',
}


def change_log_text(entry: dict[str, Any], titles: dict[str, dict[str, str]]) -> str:
    """サイトに出す文言。非公開・削除した項目の行は空（出さない）。titles は種類ごとの「ID → 今のタイトル」。"""
    kind = entry.get('kind')
    if kind == 'recruit':
        return CHANGE_LOG_RECRUIT_TEXT
    if kind == 'note':
        return str(entry.get('note', ''))
    title = titles.get(kind, {}).get(str(entry.get('item_id', '')))
    return CHANGE_LOG_TEXT[kind].format(title) if title else ''


def render_update_log(change_log: list[dict[str, Any]], data: dict[str, Any]) -> Markup:
    """日ごとにまとめ、同じ日の同じ文言は1つにする。"""
    exhibitions = data.get('exhibitions', {}) or {}
    exhibition_items = [item for item in (exhibitions.get('upcoming') or []) + (exhibitions.get('archive') or []) if item and item.get('title')]
    titles = {
        'activity': {str(item.get('id', '')): str(item['title']) for item in data.get('activities', []) if item.get('title')},
        'request': {str(item.get('id', '')): str(item['title']) for item in data.get('requests', []) if item.get('title')},
        'exhibition': {str(item.get('id', '')): str(item['title']) for item in exhibition_items},
    }
    grouped: OrderedDict[str, OrderedDict[str, None]] = OrderedDict()
    for entry in sorted(change_log, key=lambda entry: str(entry.get('timestamp', '')), reverse=True):
        text = change_log_text(entry, titles)
        if text:
            grouped.setdefault(fmt_date(str(entry.get('timestamp', ''))), OrderedDict())[text] = None
    if not grouped:
        return Markup('<div class="empty-message">まだ更新履歴はありません。</div>')
    items = [html('''
        <li class="update-log-item">
          <span class="update-log-date">{date}</span>
          <ul class="update-log-bullets">{bullets}</ul>
        </li>''', date=date, bullets=[html('<li>{text}</li>', text=text) for text in texts]) for date, texts in grouped.items()]
    return html('<ul class="update-log-list">{items}</ul>', items=items)


# ---------- 展示会 ----------

def exhibition_dm_images(item: dict[str, Any]) -> list[str]:
    images = item.get('dm_images') or []
    if isinstance(images, str):
        images = [images]
    images = [str(image) for image in images if image]
    if not images and item.get('dm_image'):
        images = [str(item.get('dm_image'))]
    return images[:2]


def render_dm_carousel(item: dict[str, Any], label: str) -> Markup | str:
    images = exhibition_dm_images(item)
    if not images:
        return ''
    return html('<div class="dm-poster-wrap">{carousel}</div>', carousel=render_carousel(images, label, max_images=2, extra_class='dm-carousel'))


def google_maps_search_url(query: str) -> str:
    # Google が公式に案内している、地図を開くための URL（API キー不要）
    return 'https://www.google.com/maps/search/?api=1&query=' + quote(query, safe='')


def render_venue_address(item: dict[str, Any]) -> Markup:
    # 住所は Google マップへのリンクにする。会場名も検索語に含めて、建物まで絞り込みやすくする
    address = item.get('venue_address', '')
    query = ' '.join(part for part in [item.get('venue_name', ''), address] if part)
    return html(
        '<a class="venue-address venue-map-link" href="{url}" target="_blank" rel="noopener noreferrer" aria-label="{address}（Google マップで開く）">'
        '<i class="fa-solid fa-location-dot" aria-hidden="true"></i><span>{address}</span></a>',
        url=google_maps_search_url(query), address=address)


def render_exhibition_meta(item: dict[str, Any]) -> Markup | str:
    date_time = [html('<span>{text}</span>', text=item['date_line']) if item.get('date_line') else '',
                 html('<span class="venue-address">{text}</span>', text=item['time_line']) if item.get('time_line') else '']
    venue = [html('<span>{text}</span>', text=item['venue_name']) if item.get('venue_name') else '',
             render_venue_address(item) if item.get('venue_address') else '']
    rows = [html('<div class="exhibition-meta-row"><div class="exhibition-meta-label">{label}</div><div class="exhibition-meta-value venue-stack">{value}</div></div>',
                 label=label, value=value)
            for label, value in (('会期', date_time), ('会場', venue)) if any(value)]
    if not rows:
        return ''
    return html('<div class="exhibition-meta compact-meta">{rows}</div>', rows=rows)


def render_exhibition_heading(item: dict[str, Any], kicker: str, placement: str, title_class: str = '') -> Markup:
    """展示会カードの見出し。PC では本文の列の中（placement='desktop'）に置いて DM と横に並べ、
    スマホではカードの先頭（placement='mobile'）に出して「見出し→DM→本文」の順にする。
    どちらも出力し、表示の切り替えは CSS でする。"""
    subtitle = str(item.get('subtitle', '') or '').strip()
    return html('''
        <div class="exhibition-heading exhibition-{placement}-heading">
          <div class="exhibition-kicker">{kicker}</div>
          {subtitle}
          <h4 class="{title_classes}">{title}</h4>
        </div>''',
        placement=placement, kicker=kicker, subtitle=subtitle and html('<div class="exhibition-subtitle">{text}</div>', text=subtitle),
        title_classes=' '.join(['exhibition-title'] + ([title_class] if title_class else [])), title=item.get('title', ''))


def render_exhibition_card(item: dict[str, Any], kicker: str, card_class: str, extra: Any = '') -> Markup:
    """展示会のカード（開催予定・直近・アーカイブで共通）。extra は本文の後ろ（直近の展示会の出展作品）。"""
    poster = render_dm_carousel(item, item.get('title', '展示会DM'))
    archive = card_class == 'archive-card'
    title_class = 'archive-title' if archive else ''
    return html('''
        <article class="simple-card glass-card exhibition-card {card_class}">
          {mobile_heading}
          <div class="{hero_classes}">
            <div class="exhibition-body">
              {desktop_heading}
              <p class="{overview_classes}">{overview}</p>
              {drive_link}
              {meta}
            </div>
            {poster}
          </div>
          {extra}
        </article>''',
        card_class=card_class,
        mobile_heading=render_exhibition_heading(item, kicker, 'mobile', title_class),
        hero_classes=' '.join(['exhibition-hero'] + (['archive-hero'] if archive else []) + ([] if poster else ['no-poster'])),
        desktop_heading=render_exhibition_heading(item, kicker, 'desktop', title_class),
        overview_classes='exhibition-overview archive-overview' if archive else 'exhibition-overview', overview=rich_text(item.get('theme', '')),
        drive_link=archive and item.get('folder_url') and html(
            '<div class="archive-actions"><a class="archive-link" href="{url}" target="_blank" rel="noopener noreferrer">'
            'Google Driveで作品を観る<i class="fa-solid fa-up-right-from-square" aria-hidden="true"></i></a></div>', url=item['folder_url']),
        meta=render_exhibition_meta(item), poster=poster, extra=extra)


def render_exhibition_upcoming(items: list[dict[str, Any]]) -> Markup | str:
    if not items:
        return ''
    return html('<div class="upcoming-list">{cards}</div>', cards=[
        render_exhibition_card(item, 'NEXT EXHIBITION' if index == 0 else 'UPCOMING', 'upcoming-card') for index, item in enumerate(items)])


def render_exhibition_recent(recent: dict[str, Any] | None) -> Markup:
    if not recent:
        return Markup('<div class="empty-message">最近の展示会情報はまだありません。</div>')
    gallery_id = 'recent-works-' + re.sub(r'[^a-zA-Z0-9_-]+', '-', str(recent.get('id', 'recent'))).strip('-')
    return render_exhibition_card(recent, 'RECENT EXHIBITION', 'recent-card', render_work_gallery(recent.get('works', []), gallery_id))


def render_exhibition_archive(items: list[dict[str, Any]]) -> Markup:
    if not items:
        return Markup('<div class="empty-message">公開中のアーカイブはありません。</div>')
    return html('<div class="archive-list">{cards}</div>', cards=[render_exhibition_card(item, 'ARCHIVE', 'archive-card') for item in items])


# ---------- 活動記録・ご依頼 ----------

ACTIVITY_CATEGORY_LABELS = {'record': '活動記録', 'event': 'イベント告知', 'other': 'その他'}


def render_activity_cards(items: list[dict[str, Any]]) -> Markup:
    if not items:
        return Markup('<div class="empty-message">公開中の記事はありません。</div>')
    cards = []
    for item in sorted(items, key=lambda x: x.get('created_at', ''), reverse=True):
        images = render_image_grid(item.get('images', []), item.get('title', '活動記録・告知'), 'activity-' + str(item.get('id', '')))
        cards.append(html('''
            <article class="article-card{has_images}">
              <div class="article-text">
                <div class="article-meta">
                  <span>{category}</span>
                  <time datetime="{created_at}">{date}</time>
                </div>
                <h4 class="article-title">{title}</h4>
                <p class="article-body">{body}</p>
              </div>
              {images}
            </article>''',
            has_images=images and ' has-images', category=ACTIVITY_CATEGORY_LABELS.get(str(item.get('category') or 'record').strip().lower(), 'その他'),
            created_at=item.get('created_at', ''), date=fmt_date(item.get('created_at', '')), title=item.get('title', ''),
            body=rich_text(item.get('body', '')), images=images))
    return html('<div class="article-grid">{cards}</div>', cards=cards)


def render_request_cards(items: list[dict[str, Any]]) -> Markup:
    if not items:
        return Markup('<div class="empty-message">公開中の事例はありません。</div>')
    cards = []
    for item in items:
        images = render_image_grid(item.get('images', []), item.get('title', '取り組み事例'), 'request-' + str(item.get('id', '')))
        cards.append(html('''
            <article class="request-card{has_images}">
              <div class="article-text">
                <div class="request-meta"><span>過去の取り組み事例</span></div>
                <h4 class="request-title">{title}</h4>
                <p class="request-body">{body}</p>
              </div>
              {images}
            </article>''',
            has_images=images and ' has-images', title=item.get('title', ''), body=rich_text(item.get('body', '')), images=images))
    return html('<div class="request-grid">{cards}</div>', cards=cards)


# ---------- 入部案内 ----------

TIMELINE_DOT_CLASSES = {'yellow': 'dot-yellow', 'blue': 'dot-blue', 'green': 'dot-green', 'white': 'dot-white'}


def render_timeline(schedule: list[dict[str, str]]) -> Markup:
    return html('<div class="timeline">{items}</div>', items=[html('''
        <div class="timeline-item">
          <div class="timeline-dot {dot}"></div>
          <div class="timeline-date">{period}</div>
          <div class="timeline-content">{label}</div>
        </div>''', dot=TIMELINE_DOT_CLASSES.get(row.get('accent', 'yellow'), 'dot-yellow'), period=row.get('period', ''), label=row.get('label', ''))
        for row in schedule])


def render_info_points(points: list[dict[str, Any]]) -> Markup:
    # 写真つきの項目は PC で左列全体を占める。右列に並ぶ項目の数だけの行にまたがらせる
    rows = max(1, sum(1 for point in points if not point.get('image')))
    cards = []
    for point in points:
        label = point.get('label', '')
        link = point.get('link') or {}
        photo = point.get('image') and html(
            '<button class="info-point-photo-button" type="button" data-lightbox-gallery="info-{label}" data-lightbox-index="0" '
            'data-lightbox-caption="{label}" aria-label="{label}の写真を拡大"><img class="info-point-photo" src="{image}" alt="{label}" loading="lazy"></button>',
            label=label, image=point['image'])
        cards.append(html('''
            <article class="info-point{has_photo}"{rows}>
              <div class="info-point-label">{label}</div>
              <div class="info-point-text">{text}</div>
              {photo}
              {link}
            </article>''',
            has_photo=photo and ' has-photo', rows=photo and html(' style="--rows: {rows};"', rows=rows), label=label,
            text=rich_text(point.get('text', '')), photo=photo,
            link=link.get('url') and html(
                '<a class="info-point-link" href="{url}" target="_blank" rel="noopener noreferrer"><i class="fa-solid fa-location-dot" aria-hidden="true"></i>{label}</a>',
                url=link['url'], label=link.get('label', '地図を開く'))))
    return html('{cards}', cards=cards)


MATERIAL_HINT = '気になる画材を押すと、説明が表示されます。'


def render_material_chips(materials: list[Any]) -> Markup:
    chips = []
    for material in materials:
        name = str(material.get('name', '')) if isinstance(material, dict) else str(material)
        note = str(material.get('note', '') or '') if isinstance(material, dict) else ''
        chips.append(html('<button class="material-chip has-note" type="button" data-name="{name}" data-note="{note}" aria-expanded="false">{name}</button>', name=name, note=note)
                     if note else html('<span>{name}</span>', name=name))
    has_notes = any(isinstance(material, dict) and material.get('note') for material in materials)
    return html('<div class="material-chip-grid">{chips}</div>{note}', chips=chips, note=has_notes and html(
        '<p class="material-note is-hint" id="materialNote" data-hint="{hint}" aria-live="polite">{hint}</p>', hint=MATERIAL_HINT))


def render_recruit_calendar(calendar: dict[str, Any]) -> Markup:
    images = calendar.get('images', []) if calendar else []
    if not images:
        return Markup('<div class="empty-message">現在公開中の新歓イベントカレンダー画像はありません。</div>')
    # 枠の縦横比を2つ用意し、画面に合わせて CSS で切り替える（どの画像も切れずに収まる）。
    #   横長の画面（大きさが画面の高さで決まる）：いちばん横長の画像に合わせる（--carousel-ratio-wide）
    #   縦長の画面（大きさが画面の幅で決まる）：いちばん縦長の画像に合わせる（--carousel-ratio-tall）
    # こうすると、どちらの画面でも、ある画像を大きくするために別の画像が小さくなることがない。
    # パワーポイント（16:9）と Instagram 用（正方形・4:5）の画像を想定し、16:9〜4:5 に収める
    known = [min(16 / 9, max(0.8, ratio)) for ratio in (image_aspect(image, None) for image in images[:10]) if ratio]
    wide = max(known) if known else 16 / 9
    tall = min(known) if known else 16 / 9
    return render_carousel(images, '新歓イベントカレンダー', extra_class='recruit-carousel',
                           style=f'--carousel-ratio-wide: {wide:.4f}; --carousel-ratio-tall: {tall:.4f}')


# ---------- ヒーロー（ページの先頭） ----------

def render_hero(static: dict[str, Any], recent: dict[str, Any] | None) -> Markup:
    # 直近の展示会の全作品の画像を、背景のスライドショーにする（特定の作品だけが選ばれないよう全作品）。
    # 1枚目だけをすぐ読み、2枚目からは表示する直前に site.js が data-src から読む。画像がなければロゴと飾りにする
    images = [str(work.get('image') or '') for work in (recent or {}).get('works', []) if work.get('image')]
    if images:
        slides = [html('<div class="hero-slide{active}"><img {source}="{src}" alt="" decoding="async"></div>',
                       active=' is-active' if index == 0 else '', source='src' if index == 0 else 'data-src', src=src)
                  for index, src in enumerate(images)]
        background = html('<div class="hero-slideshow" aria-hidden="true" data-hero-slideshow>{slides}<div class="hero-shade"></div></div>'
                          '<div class="grid-overlay"></div>', slides=slides)
        logo = ''
    else:
        background = Markup('<div class="decoration circle-green"></div><div class="decoration square-blue"></div><div class="grid-overlay"></div>')
        logo = Markup('<img src="logo.png" alt="凌美会 ロゴ" class="hero-logo">')
    return html('''
        <header id="home" class="hero-section{has_slideshow}">
          {background}
          <div class="hero-content">
            {logo}
            <p class="hero-kicker">{kicker}</p>
            <h1 class="hero-title">{title}</h1>
            <p class="hero-subtitle">{subtitle}</p>
          </div>
        </header>''',
        has_slideshow=bool(images) and ' has-slideshow', background=background, logo=logo,
        kicker=static['hero_kicker'], title=static['hero_title'], subtitle=rich_text(static['hero_subtitle']))
