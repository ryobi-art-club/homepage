"""HTML を作る道具。管理画面の画面のスクリプト（UiCore.html の html`…`）と同じ考え方にしている。"""
from __future__ import annotations

import html as _html
import re
from datetime import datetime, timedelta, timezone
from typing import Any


class Markup(str):
    """そのまま HTML として入れてよい文字列（html() で作ったもの、コードの中で決めたもの）。部員が入力した値には使わない。"""


def escape(value: Any) -> str:
    return _html.escape('' if value is None else str(value), quote=True)


def _html_value(value: Any) -> str:
    if value is None or value is False:
        return ''
    if isinstance(value, Markup):
        return str(value)
    if isinstance(value, (list, tuple)):
        return ''.join(_html_value(item) for item in value)
    return escape(value)


_LINE_BREAK = re.compile(r'\n\s*')


def html(template: str, **values: Any) -> Markup:
    """template の {名前} に values を入れる。値は文字として表示されるように書き換える（< や " がそのまま表示される）。
    Markup と、その一覧（リスト）はそのまま入る。None と False は何も入らない。
    読みやすいようにタグの間で改行してよい（template の改行と行頭の空白は取り除く。値の中の改行はそのまま）。"""
    return Markup(_LINE_BREAK.sub('', template).format(**{key: _html_value(value) for key, value in values.items()}))


LINK_RE = re.compile(r'\[([^\]\n]+)\]\((https?://[^\s)]+)\)')


def inline_rich_text(value: Any) -> Markup:
    """[文字](URL) をリンクにする。"""
    text = '' if value is None else str(value)
    parts: list[Any] = []
    last = 0
    for match in LINK_RE.finditer(text):
        parts.append(text[last:match.start()])
        parts.append(html('<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>', url=match.group(2), label=match.group(1)))
        last = match.end()
    parts.append(text[last:])
    return html('{parts}', parts=parts)


def rich_text(value: Any) -> Markup:
    """改行を <br> にし、[文字](URL) をリンクにする。"""
    lines = ('' if value is None else str(value)).splitlines()
    return Markup('<br>'.join(inline_rich_text(line) for line in lines))


# 管理画面は日時を世界標準時（末尾が Z）で保存する。日付は日本時間で出す（管理画面のプレビューと同じ）。
# 日本には夏時間がないので、9時間ずらすだけでよい
JST = timezone(timedelta(hours=9))


def jst_date(ts: str):
    return datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone(JST).date()


def fmt_date(ts: str) -> str:
    try:
        return jst_date(ts).strftime('%Y.%m.%d')
    except Exception:
        return ts
