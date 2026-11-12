"""ページ全体の組み立てと、検索エンジン向けの情報（SEO・sitemap）。"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .html import JST, Markup, escape, html, jst_date, rich_text
from .sections import (render_activity_cards, render_exhibition_archive, render_exhibition_recent, render_exhibition_upcoming,
                       render_hero, render_info_points, render_material_chips, render_recruit_calendar, render_request_cards,
                       render_timeline, render_update_log)

SITE_TITLE = '神戸大学美術部凌美会 | ホームページ'
SITE_DESCRIPTION = '神戸大学美術部凌美会の公式ホームページです。展示会情報、活動記録・告知、入部案内、ご依頼の方向け情報を掲載しています。'


def normalized_site_url(url: str) -> str:
    value = str(url or '').strip()
    return value.rstrip('/') + '/' if value else ''


def build_seo_context(static: dict[str, Any], data: dict[str, Any]) -> dict[str, str]:
    base_url = normalized_site_url(static.get('og_url', ''))
    og_image = str(static.get('og_image', 'logo.png'))
    image_url = og_image if og_image.startswith('http') else (base_url + og_image.lstrip('/')) if base_url else og_image
    social = static.get('social_links', {})
    organization = {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        'name': '神戸大学美術部凌美会',
        'alternateName': ['神戸大学 美術部 凌美会', '凌美会', '美術部凌美会', '神戸大学美術部'],
        'url': base_url or static.get('og_url', ''),
        'logo': image_url,
        'sameAs': [url for url in (social.get('instagram', ''), social.get('x', '')) if url]
    }
    website = {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': SITE_TITLE,
        'url': base_url or static.get('og_url', '')
    }
    # 最後に更新した日（sitemap の lastmod）は、更新履歴のいちばん新しい日
    lastmod = None
    for ts in sorted((str(entry.get('timestamp', '')) for entry in data.get('change_log', []) if entry.get('timestamp')), reverse=True):
        try:
            lastmod = jst_date(ts).isoformat()
            break
        except Exception:
            continue
    return {
        'base_url': base_url,
        'title': SITE_TITLE,
        'description': SITE_DESCRIPTION,
        'image_url': image_url,
        'canonical': base_url or static.get('og_url', ''),
        'organization_json': json.dumps(organization, ensure_ascii=False),
        'website_json': json.dumps(website, ensure_ascii=False),
        'lastmod': lastmod or datetime.now(JST).date().isoformat(),
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


def render_tab_heading(eyebrow: str, title: str, summary: Any) -> Markup:
    return html('''
        <div class="section-header">
          <p class="eyebrow">{eyebrow}</p>
          <h3 class="section-title tab-title">{title}</h3>
          <p class="section-subtitle">{summary}</p>
        </div>''', eyebrow=eyebrow, title=title, summary=rich_text(summary))


def render_page(static: dict[str, Any], data: dict[str, Any]) -> str:
    recruit = static['recruit_static']
    requests_static = static['requests_static']
    social = static['social_links']
    seo = build_seo_context(static, data)
    exhibitions = data.get('exhibitions', {})
    upcoming = sorted(exhibitions.get('upcoming') or [], key=lambda item: str(item.get('start_date', '')))
    archive = sorted(exhibitions.get('archive') or [], key=lambda item: str(item.get('start_date', '')), reverse=True)
    # アーカイブの最新1件を「直近の展示会」として大きく出し、残りをアーカイブに並べる
    recent = archive[0] if archive else None
    calendar = data.get('recruit_calendar', {})
    return '<!DOCTYPE html>\n' + html('''
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{image_url}">
  <meta property="og:image:alt" content="神戸大学美術部凌美会 ロゴ">
  <meta property="og:site_name" content="{title}">
  <meta property="og:locale" content="ja_JP">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description}">
  <meta name="twitter:image" content="{image_url}">
  <script type="application/ld+json">{organization_json}</script>
  <script type="application/ld+json">{website_json}</script>
  <link rel="stylesheet" href="stylesheet.css">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap" rel="stylesheet">
  <script defer src="site.js"></script>
</head>
<body>
  <div class="ink-layer" data-ink-layer aria-hidden="true"></div>
  <nav class="global-nav">
    <div class="nav-container">
      <a href="#home" class="nav-brand">
        <img src="logo.png" alt="凌美会 ロゴ" class="nav-brand-logo">
        <span class="nav-brand-text">{club_name}</span>
      </a>
      <ul class="nav-menu">
        <li><a href="#about">ABOUT</a></li>
        <li><a href="#info-tabs">INFO</a></li>
      </ul>
      <ul class="nav-links">
        <li><a href="{instagram}" target="_blank" rel="noopener noreferrer" class="social-link instagram" aria-label="Instagram"><i class="fa-brands fa-instagram"></i></a></li>
        <li><a href="{x}" target="_blank" rel="noopener noreferrer" class="social-link x-twitter" aria-label="X (Twitter)"><i class="fa-brands fa-x-twitter"></i></a></li>
        <li><a href="{email}" class="social-link email" aria-label="Email"><i class="fa-regular fa-envelope"></i></a></li>
      </ul>
    </div>
  </nav>
  {hero}
  <main class="main-content">
    <section id="about" class="sub-section">
      <div class="section-header">
        <p class="section-label">ABOUT US</p>
        <h2 class="section-title">基本情報</h2>
        <p class="section-subtitle">{intro}</p>
      </div>
      <article class="simple-card glass-card">
        <p class="eyebrow">UPDATE LOG</p>
        {update_log}
      </article>
    </section>
    <section id="info-tabs" class="sub-section">
      <div class="section-header">
        <p class="section-label">INFORMATION</p>
        <h2 class="section-title">ご案内</h2>
        <p class="section-subtitle">{information}</p>
      </div>
      <div class="glass-card tab-shell" data-tab-shell>
        <div class="tab-buttons" role="tablist" aria-label="情報タブ">
          <button class="tab-button is-active" type="button" data-tab-target="exhibitions">展覧会</button>
          <button class="tab-button" type="button" data-tab-target="activities">活動記録・告知</button>
          <button class="tab-button" type="button" data-tab-target="recruit">入部希望の方</button>
          <button class="tab-button" type="button" data-tab-target="requests">ご依頼の方</button>
        </div>
        <section class="tab-panel is-active" data-tab-panel="exhibitions">
          {exhibitions_heading}
          <div class="exhibition-stack">
            {upcoming}
            {recent}
            <article class="simple-card glass-card">
              {archive}
            </article>
          </div>
        </section>
        <section class="tab-panel" data-tab-panel="activities">
          {activities_heading}
          {activities}
        </section>
        <section class="tab-panel" data-tab-panel="recruit">
          {recruit_heading}
          <div class="info-grid">{info_points}</div>
          <div class="simple-card glass-card">
            <p class="eyebrow">MATERIALS</p>
            <h4 class="card-heading">使えるもの</h4>
            {materials}
          </div>
          <div class="simple-card glass-card">
            <p class="eyebrow">ANNUAL SCHEDULE</p>
            <h4 class="card-heading">年間スケジュール</h4>
            {timeline}
          </div>
          <div class="simple-card glass-card">
            <p class="eyebrow">WELCOME CALENDAR</p>
            <h4 class="card-heading">{calendar_label}</h4>
            {calendar}
          </div>
        </section>
        <section class="tab-panel" data-tab-panel="requests">
          {requests_heading}
          <div class="simple-card glass-card request-contact-card">
            <p class="request-contact-heading">お問い合わせ先</p>
            <ul class="request-contact-list">
              <li><span>Email</span><a href="mailto:{contact_email}">{contact_email}</a></li>
              <li><span>Instagram</span><a href="{instagram}" target="_blank" rel="noopener noreferrer">{contact_instagram}</a></li>
              <li><span>X</span><a href="{x}" target="_blank" rel="noopener noreferrer">{contact_x}</a></li>
            </ul>
          </div>
          {requests}
        </section>
      </div>
    </section>
  </main>
  <footer>
    <p>{copyright}</p>
  </footer>
</body>
</html>
''',
        title=seo['title'], description=seo['description'], canonical=seo['canonical'], image_url=seo['image_url'],
        # 構造化データの JSON は site_static.json から作る（部員の入力は入らない）。書き換えると JSON として読めなくなる
        organization_json=Markup(seo['organization_json']), website_json=Markup(seo['website_json']),
        club_name=static['club_name_jp'], instagram=social['instagram'], x=social['x'], email=social['email'],
        hero=render_hero(static, recent),
        intro=rich_text(static['intro_text']), update_log=render_update_log(data.get('change_log', []), data),
        information=rich_text(static.get('information_text', '展示会、活動記録・告知、入部、ご依頼に関する情報をまとめています。')),
        exhibitions_heading=render_tab_heading('EXHIBITIONS', '展示会情報', static.get('exhibitions_static', {}).get('summary', '開催予定の展示会と最近の展示記録を掲載しています。')),
        upcoming=render_exhibition_upcoming(upcoming), recent=render_exhibition_recent(recent), archive=render_exhibition_archive(archive[1:]),
        activities_heading=render_tab_heading('ACTIVITIES', '活動記録・告知', static.get('activities_static', {}).get('summary', '展示以外の活動やイベントの記録です。')),
        activities=render_activity_cards(data.get('activities', [])),
        recruit_heading=render_tab_heading('JOIN US', '入部希望の方へ', recruit['summary']),
        info_points=render_info_points(recruit['info_points']), materials=render_material_chips(recruit['materials']),
        timeline=render_timeline(recruit['annual_schedule']),
        calendar_label=calendar.get('label', '新歓イベントカレンダー'), calendar=render_recruit_calendar(calendar),
        requests_heading=render_tab_heading('REQUESTS', 'ご依頼の方へ', requests_static['summary']),
        contact_email=requests_static['contact_email'], contact_instagram=requests_static.get('contact_instagram', '@ryobi.welcome'),
        contact_x=requests_static.get('contact_x', '@Art_Club_Ryobi'),
        requests=render_request_cards(data.get('requests', [])), copyright=static['copyright'])
