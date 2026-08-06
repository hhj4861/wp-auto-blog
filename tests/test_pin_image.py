"""세로 Pinterest 핀 이미지 생성기 테스트 (네트워크 없이 로컬 소스)."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pin_image import (  # noqa: E402
    ACCENTS, DEFAULT_ACCENT, W, H,
    make_pin_image, _cover, _wrap, _fit_title, _font,
)


def _src(tmp_path, w=1600, h=800, color=(80, 120, 200)) -> str:
    p = tmp_path / "src.jpg"
    Image.new("RGB", (w, h), color).save(p, "JPEG")
    return str(p)


def test_output_is_2x3_jpeg(tmp_path):
    out = tmp_path / "pin.jpg"
    make_pin_image(_src(tmp_path), "Korean Skincare Guide 2026", "K-Beauty", str(out))
    assert out.exists()
    im = Image.open(out)
    assert im.size == (W, H) == (1000, 1500)
    assert im.format == "JPEG"


def test_cover_returns_exact_target_for_any_ratio():
    for w, h in [(1600, 800), (800, 1600), (1000, 1000), (2000, 500)]:
        src = Image.new("RGB", (w, h))
        cov = _cover(src, W, H)
        assert cov.size == (W, H)


def test_accent_mapping_and_default():
    assert ACCENTS["K-Pop"] == (168, 85, 247)
    assert ACCENTS.get("Nonexistent", DEFAULT_ACCENT) == DEFAULT_ACCENT


def test_wrap_lines_fit_width():
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    font = _font(60)
    max_w = W - 128
    lines = _wrap(draw, "This is a fairly long Pinterest pin title that must wrap", font, max_w)
    assert len(lines) >= 2
    for ln in lines:
        assert draw.textlength(ln, font=font) <= max_w or " " not in ln


def test_long_title_autoshrinks_and_caps_lines():
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    long_title = "Korean " * 40  # 강제로 매우 긴 제목
    font, lines, line_h = _fit_title(draw, long_title.strip(), W - 128, 560)
    assert len(lines) <= 5
    assert isinstance(font, ImageFont.FreeTypeFont)


def test_font_resolver_always_returns_font():
    f = _font(48)
    assert isinstance(f, ImageFont.FreeTypeFont)
