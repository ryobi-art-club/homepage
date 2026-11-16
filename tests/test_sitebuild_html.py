"""scripts/sitebuild/html.py のテスト。部員が入力した値が、HTML として動かずに文字として出ることを確かめる。

実行：python -m unittest discover tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from sitebuild.html import Markup, escape, fmt_date, html, inline_rich_text, rich_text  # noqa: E402


class EscapeTest(unittest.TestCase):
    def test_escapes_html_characters(self):
        self.assertEqual(escape('<b>"A" & \'B\'</b>'), '&lt;b&gt;&quot;A&quot; &amp; &#x27;B&#x27;&lt;/b&gt;')

    def test_none_is_empty(self):
        self.assertEqual(escape(None), '')


class HtmlTest(unittest.TestCase):
    def test_values_are_escaped(self):
        result = html('<p title="{title}">{body}</p>', title='" onmouseover="alert(1)', body='<script>alert(1)</script>')
        self.assertEqual(result, '<p title="&quot; onmouseover=&quot;alert(1)">&lt;script&gt;alert(1)&lt;/script&gt;</p>')
        self.assertIsInstance(result, Markup)

    def test_markup_is_inserted_as_is(self):
        self.assertEqual(html('<div>{inner}</div>', inner=Markup('<i>アイコン</i>')), '<div><i>アイコン</i></div>')

    def test_list_items_are_each_escaped_or_kept(self):
        self.assertEqual(html('{items}', items=[Markup('<br>'), '<br>']), '<br>&lt;br&gt;')

    def test_none_and_false_are_empty(self):
        self.assertEqual(html('[{a}][{b}][{c}]', a=None, b=False, c=0), '[][][0]')

    def test_template_line_breaks_are_removed_but_value_line_breaks_are_kept(self):
        result = html('''<ul>
          <li>{text}</li>
        </ul>''', text='一行目\n二行目')
        self.assertEqual(result, '<ul><li>一行目\n二行目</li></ul>')

    def test_braces_in_values_are_not_treated_as_placeholders(self):
        self.assertEqual(html('<p>{text}</p>', text='{text}'), '<p>{text}</p>')


class RichTextTest(unittest.TestCase):
    def test_link_becomes_anchor(self):
        self.assertEqual(
            inline_rich_text('詳しくは[こちら](https://example.com/a?b=1&c=2)へ'),
            '詳しくは<a href="https://example.com/a?b=1&amp;c=2" target="_blank" rel="noopener noreferrer">こちら</a>へ')

    def test_label_and_surrounding_text_are_escaped(self):
        self.assertEqual(
            inline_rich_text('<b>[<i>x</i>](https://example.com)'),
            '&lt;b&gt;<a href="https://example.com" target="_blank" rel="noopener noreferrer">&lt;i&gt;x&lt;/i&gt;</a>')

    def test_quote_in_url_cannot_leave_the_attribute(self):
        result = inline_rich_text('[x](https://example.com/"onclick="alert(1))')
        self.assertIn('href="https://example.com/&quot;onclick=&quot;alert(1"', result)
        self.assertNotIn('"onclick="', result)

    def test_only_http_and_https_links(self):
        self.assertEqual(inline_rich_text('[x](javascript:alert(1))'), '[x](javascript:alert(1))')

    def test_line_breaks_become_br(self):
        self.assertEqual(rich_text('一行目\n<二行目>'), '一行目<br>&lt;二行目&gt;')

    def test_none_is_empty(self):
        self.assertEqual(rich_text(None), '')


class FmtDateTest(unittest.TestCase):
    def test_utc_is_shown_as_japan_date(self):
        # 世界標準時の15時は、日本時間では翌日の0時
        self.assertEqual(fmt_date('2026-10-31T15:00:00.000Z'), '2026.11.01')

    def test_unreadable_value_is_shown_as_is(self):
        self.assertEqual(fmt_date('日付なし'), '日付なし')


if __name__ == '__main__':
    unittest.main()
