"""画像の縦横比を、ファイルの頭の部分から読む（PNG・JPEG・SVG）。画像を読み込む道具を入れずに済ませるため。"""
from __future__ import annotations

import re
from pathlib import Path

# 内容の画像（assets/…）がある場所の1つ上。build_site.py が --assets-root から決める
ASSET_SOURCE_ROOT = Path('.')

_JPEG_SIZE_MARKERS = {b'\xc0', b'\xc1', b'\xc2', b'\xc3', b'\xc5', b'\xc6', b'\xc7', b'\xc9', b'\xca', b'\xcb', b'\xcd', b'\xce', b'\xcf'}


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
                if marker in _JPEG_SIZE_MARKERS:
                    f.read(3)
                    h = int.from_bytes(f.read(2), 'big')
                    w = int.from_bytes(f.read(2), 'big')
                    return w / h if h else None
                length_bytes = f.read(2)
                if len(length_bytes) < 2:
                    return None
                f.seek(int.from_bytes(length_bytes, 'big') - 2, 1)
    except Exception:
        return None


def image_aspect(src: str, default: float | None = 1.0) -> float | None:
    """幅 ÷ 高さ。読めないときは default。極端な値は 0.35〜3.2 に丸める。"""
    path = _resolve_asset_path(src)
    if not path:
        return default
    readers = {'.svg': _read_svg_aspect, '.png': _read_png_aspect, '.jpg': _read_jpeg_aspect, '.jpeg': _read_jpeg_aspect}
    reader = readers.get(path.suffix.lower())
    ratio = reader(path) if reader else None
    if not ratio or ratio <= 0:
        return default
    return max(0.35, min(3.2, ratio))
