"""Deterministic, article-grounded TrendPulse title cards; no stock fallback."""
from hashlib import sha256
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

from src.image_fetcher import FetchedImage, ImageSource

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/generated-thumbnails'
FONT = ROOT / 'assets/fonts/NanumGothic-Bold.ttf'
W, H = 1200, 900


def clean(text):
    return re.sub(r'\s+', ' ', BeautifulSoup(text, 'html.parser').get_text(' ', strip=True)).strip()


def article_labels(title, body):
    title = clean(title)
    if not title or len(title) > 160 or '\ufffd' in title:
        raise ValueError('Invalid title for editorial thumbnail')
    soup = BeautifulSoup(body, 'html.parser')
    headings = []
    for node in soup.select('h2'):
        text = clean(node.get_text(' ', strip=True))
        if not text or any(word in text for word in ('목차', '출처', 'FAQ', '자주 묻', '관련 글')):
            continue
        # Remove decorative emoji, without rewriting factual text.
        text = re.sub(r'^[^가-힣A-Za-z0-9]+', '', text)
        if text and text not in headings and text != title:
            headings.append(text)
    return title, headings[:2]


def wrap(draw, text, font, width):
    lines, line = [], ''
    for word in text.split():
        trial = (line + ' ' + word).strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = ''
            for char in word:
                if line and draw.textlength(line + char, font=font) > width:
                    lines.append(line)
                    line = ''
                line += char
    if line:
        lines.append(line.rstrip())
    return lines


def create_editorial_thumbnail(title, body, category=''):
    title, headings = article_labels(title, body)
    if not FONT.is_file():
        raise RuntimeError('Bundled Korean font missing; refusing substitute font')
    image = Image.new('RGB', (W, H), '#102b2b')
    draw = ImageDraw.Draw(image)
    # All text lies within the central square for WordPress square crops.
    draw.rounded_rectangle((152, 80, 1048, 820), radius=30, fill='#f5f6ed')
    draw.rounded_rectangle((182, 112, 188, 155), radius=3, fill='#087f73')
    font = lambda size: ImageFont.truetype(str(FONT), size)
    draw.text((208, 117), 'TrendPulse', font=font(30), fill='#087f73')
    for size in range(70, 33, -2):
        title_font = font(size)
        lines = wrap(draw, title, title_font, 800)
        if len(lines) * (size + 15) <= 365:
            break
    else:
        raise ValueError('Title cannot fit without clipping')
    y = 206
    for line in lines:
        draw.text((198, y), line, font=title_font, fill='#102b2b')
        y += size + 15
    draw.line((198, 598, 1002, 598), fill='#cbd9ce', width=2)
    for index, heading in enumerate(headings):
        label_font = font(28)
        while heading and draw.textlength(heading, font=label_font) > 740:
            heading = heading[:-2].rstrip() + '…'
        y = 635 + index * 70
        draw.ellipse((198, y + 9, 210, y + 21), fill='#087f73')
        draw.text((230, y), heading, font=label_font, fill='#35514b')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    digest = sha256((title + '\n' + body).encode()).hexdigest()[:20]
    path = OUTPUT / f'article-{digest}.jpg'
    image.save(path, quality=92)
    # Audit evidence: exact article labels, not AI-invented visual claims.
    path.with_suffix('.json').write_text(json.dumps({
        'version': 'editorial-card-v1', 'title': title, 'headings': headings,
        'category': category, 'body_sha256': sha256(body.encode()).hexdigest(),
        'width': W, 'height': H,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    return FetchedImage(str(path), title + ' — 본문 핵심 항목', 'TrendPulse',
                        ImageSource.EDITORIAL, W, H)
