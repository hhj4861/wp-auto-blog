"""Deterministic, article-grounded TrendPulse title cards; no stock fallback."""
from hashlib import sha256
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

from src.image_fetcher import FetchedImage, ImageSource
from src.thumbnail_art import PALETTES, illustration, subject_for

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'data/generated-thumbnails'
FONT = ROOT / 'assets/fonts/NanumGothic-Bold.ttf'
W, H = 1200, 900
VERSION = 'editorial-illustrated-v2'


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
    digest = sha256((VERSION + '\n' + category + '\n' + title + '\n' + body).encode()).hexdigest()[:20]
    subject = subject_for(title, category)
    background, ink, accent, light = PALETTES[subject]
    image = Image.new('RGB', (W, H), background)
    draw = ImageDraw.Draw(image)
    font = lambda size: ImageFont.truetype(str(FONT), size)
    # Headline is an exact title fragment, never a generated promise or claim.
    parts = re.split(r'[:：]', title, maxsplit=1)
    headline = parts[0].strip() or title
    # Spacing only: preserve the article's words while keeping Korean phrases together.
    headline = re.sub(r'(?<=[가-힣])(치료방법|확인방법|신청방법|사용방법)', r' \1', headline)
    subtitle = parts[1].strip() if len(parts) == 2 else (headings[0] if headings else '')
    layout = 'split' if len(headline) <= 28 and int(digest[:2], 16) % 2 else 'stacked'
    draw.text((185, 72), 'TrendPulse', font=font(25), fill=ink)
    if category:
        label = category[:14]
        label_width = draw.textlength(label, font=font(22))
        draw.text((1015 - label_width, 76), label, font=font(22), fill=accent)
    art = illustration(subject, int(digest[2:4], 16) % 3)
    if layout == 'split':
        art = art.resize((440, 396), Image.Resampling.LANCZOS)
        image.paste(art, (625, 215), art)
        x, y, width, height = 185, 259, 440, 340
        max_size = 68
    else:
        art = art.resize((540, 486), Image.Resampling.LANCZOS)
        x, y, width, height = 185, 583, 830, 180
        if len(headline) > 65:
            art = art.resize((400, 360), Image.Resampling.LANCZOS)
            y, height = 475, 285
        image.paste(art, ((W - art.width) // 2, 110), art)
        max_size = 64
    for size in range(max_size, 25, -2):
        title_font = font(size)
        lines = wrap(draw, headline, title_font, width)
        if len(lines) * (size + 14) <= height:
            break
    else:
        raise ValueError('Title cannot fit without clipping')
    bounds = []
    for line in lines:
        bounds.append(draw.textbbox((x, y), line, font=title_font))
        draw.text((x, y), line, font=title_font, fill=ink)
        y += size + 14
    if subtitle:
        label_font = font(25)
        subtitle = subtitle.rstrip()
        if draw.textlength(subtitle, font=label_font) > 830:
            while subtitle and draw.textlength(subtitle + '…', font=label_font) > 830:
                subtitle = subtitle[:-1].rstrip()
            subtitle += '…'
        draw.text((185, 798), subtitle, font=label_font, fill=ink)
    draw.rounded_rectangle((185, 858, 237, 863), radius=2, fill=accent)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / f'article-{digest}.jpg'
    image.save(path, quality=92)
    # Audit evidence: exact article labels, not AI-invented visual claims.
    path.with_suffix('.json').write_text(json.dumps({
        'version': VERSION, 'title': title, 'headings': headings,
        'headline': headline, 'subtitle': subtitle, 'subject': subject,
        'layout': layout, 'palette': list(PALETTES[subject]), 'headline_bounds': bounds,
        'category': category, 'body_sha256': sha256(body.encode()).hexdigest(),
        'width': W, 'height': H,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    return FetchedImage(str(path), title + ' — 주제 일러스트', 'TrendPulse',
                        ImageSource.EDITORIAL, W, H)
