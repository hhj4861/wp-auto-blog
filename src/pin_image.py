"""세로 2:3 Pinterest 핀 이미지 생성기 (bytepulse Phase 2b).

발행 히어로(가로) → Pinterest 최적 세로 핀(1000×1500)으로 변환.
전면 히어로 + 하단 다크 그라디언트 + 카테고리 배지 + 제목 오버레이 + 브랜드.
폰트는 이식성 우선: 데스크톱 Arial Black → Pillow 임베드 DejaVu 폴백(CI 안전).

CLI 미리보기:
    python -m src.pin_image <source(파일|URL)> "<제목>" <카테고리> <출력.jpg>
"""

from __future__ import annotations

import io
import os
import sys
import textwrap
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

W, H = 1000, 1500  # Pinterest 권장 2:3

# 카테고리별 액센트 (블로그 정체성과 일치)
ACCENTS = {
    "K-Beauty": (236, 72, 153),   # pink
    "K-Pop": (168, 85, 247),      # purple
    "K-Fashion": (244, 63, 94),   # rose
    "K-Food": (249, 115, 22),     # orange
    "K-Culture": (139, 92, 246),  # violet
}
DEFAULT_ACCENT = (14, 165, 233)   # cyan (tech)
DARK = (15, 23, 42)               # slate-900 (그라디언트/브랜드 배경)

# 데스크톱 우선 폰트(무게감) → 없으면 Pillow 임베드 DejaVu(이식성)
_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # 리눅스 설치 시
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:  # noqa: BLE001
                continue
    # Pillow 10+ : 스케일러블 DejaVu 임베드 (mac·CI 공통 폴백)
    return ImageFont.load_default(size=size)


def _load_source(source: str) -> Image.Image:
    """파일 경로 또는 URL에서 이미지 로드."""
    if source.startswith(("http://", "https://")):
        r = requests.get(source, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content))
    else:
        img = Image.open(source)
    return img.convert("RGB")


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """대상 비율을 꽉 채우도록 리사이즈 후 중앙 크롭(cover)."""
    src_ratio = img.width / img.height
    dst_ratio = w / h
    if src_ratio > dst_ratio:  # 소스가 더 넓음 → 높이 맞추고 좌우 크롭
        new_h = h
        new_w = round(h * src_ratio)
    else:                      # 소스가 더 좁음 → 너비 맞추고 상하 크롭
        new_w = w
        new_h = round(w / src_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def _bottom_gradient(h_from_frac: float = 0.42, max_alpha: int = 238) -> Image.Image:
    """하단부 다크 그라디언트(RGBA) — 텍스트 가독성 확보. (세로 알파 마스크 방식, 빠름)"""
    start = int(H * h_from_frac)
    span = max(H - start, 1)
    col = bytearray(H)
    for y in range(start, H):
        col[y] = int(max_alpha * ((y - start) / span) ** 1.35)
    mask = Image.frombytes("L", (1, H), bytes(col)).resize((W, H))
    overlay = Image.new("RGBA", (W, H), (*DARK, 255))
    overlay.putalpha(mask)
    return overlay


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
          max_w: int) -> list[str]:
    """폰트 실측 폭 기준 단어 래핑."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def _fit_title(draw: ImageDraw.ImageDraw, title: str, max_w: int,
               max_h: int) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    """제목이 허용 영역에 들어가도록 폰트 크기 자동 축소."""
    for size in range(84, 43, -4):
        font = _font(size)
        lines = _wrap(draw, title, font, max_w)
        line_h = int(size * 1.18)
        total = line_h * len(lines)
        if len(lines) <= 5 and total <= max_h:
            return font, lines, line_h
    font = _font(44)
    lines = _wrap(draw, title, font, max_w)[:5]
    return font, lines, int(44 * 1.18)


def make_pin_image(source: str, title: str, category: str, out_path: str,
                   brand: str = "bytepulse.io") -> str:
    """세로 2:3 핀 이미지를 만들어 out_path(JPEG)에 저장하고 경로를 반환."""
    accent = ACCENTS.get(category, DEFAULT_ACCENT)

    base = _cover(_load_source(source), W, H)
    base = base.convert("RGBA")
    base.alpha_composite(_bottom_gradient())
    draw = ImageDraw.Draw(base)

    margin = 64
    max_w = W - margin * 2

    # --- 제목(하단) ---
    title_area_h = 560
    font, lines, line_h = _fit_title(draw, title.strip(), max_w, title_area_h)
    brand_h = 90
    block_h = line_h * len(lines)
    y = H - margin - brand_h - block_h
    for ln in lines:
        draw.text((margin, y), ln, font=font, fill=(255, 255, 255),
                  stroke_width=3, stroke_fill=(0, 0, 0))
        y += line_h

    # --- 카테고리 배지(상단 좌측) ---
    bfont = _font(36)
    label = category.upper()
    tw = draw.textlength(label, font=bfont)
    pad_x, pad_y = 26, 16
    bx0, by0 = margin, margin
    bx1 = bx0 + tw + pad_x * 2
    by1 = by0 + 36 + pad_y * 2
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=14, fill=accent)
    draw.text((bx0 + pad_x, by0 + pad_y - 2), label, font=bfont, fill=(255, 255, 255))

    # --- 브랜드(하단) + 액센트 바 ---
    draw.rectangle([margin, H - margin - 52, margin + 60, H - margin - 46], fill=accent)
    dfont = _font(34)
    draw.text((margin + 76, H - margin - 62), brand, font=dfont,
              fill=(226, 232, 240))

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(out_path, "JPEG", quality=88, optimize=True)
    return out_path


def _cli() -> int:
    if len(sys.argv) < 5:
        print(__doc__)
        return 1
    src, title, category, out = sys.argv[1:5]
    path = make_pin_image(src, title, category, out)
    im = Image.open(path)
    print(f"생성: {path} ({im.size[0]}x{im.size[1]}, {os.path.getsize(path)//1024}KB)")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
