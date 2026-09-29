import json
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw, ImageFont
import pytest

from src import editorial_thumbnail as module
from src.wordpress_client import WordPressClient, WPConfig


def test_card_uses_article_labels_and_bundled_korean_font(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'OUTPUT', tmp_path)
    title = '2026 현대자동차 9월 신입채용 지원자격·어학성적 체크리스트'
    body = '<h2>목차</h2><h2>지원자격 확인</h2><h2>어학성적 기준</h2><h2>FAQ</h2>'
    result = module.create_editorial_thumbnail(title, body)
    path = Path(result.url)
    assert Image.open(path).size == (1200, 900)
    audit = json.loads(path.with_suffix('.json').read_text())
    assert audit['title'] == title
    assert audit['headings'] == ['지원자격 확인', '어학성적 기준']
    assert result.source.value == 'editorial'
    assert module.create_editorial_thumbnail(title, body).url == result.url


def test_no_font_or_invalid_title_fails_instead_of_stock_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'FONT', tmp_path / 'missing.ttf')
    with pytest.raises(RuntimeError, match='font missing'):
        module.create_editorial_thumbnail('면접', '<h2>준비</h2>')
    with pytest.raises(ValueError):
        module.article_labels('깨진\ufffd제목', '')


def test_long_korean_words_fit_without_clipping():
    draw = ImageDraw.Draw(Image.new('RGB', (1200, 900)))
    font = ImageFont.truetype(str(module.FONT), 64)
    text = '현대자동차 신입채용 지원자격·어학성적 체크리스트 ' + '장문제목' * 10
    lines = module.wrap(draw, text, font, 800)
    assert ''.join(lines).replace(' ', '') == text.replace(' ', '')
    assert all(draw.textlength(line, font=font) <= 800 for line in lines)


def test_local_upload_uses_generated_bytes_only(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'OUTPUT', tmp_path)
    card = module.create_editorial_thumbnail('면접 자기소개', '<h2>경험 선택</h2>')
    client = WordPressClient(WPConfig('https://trendpulse.blog', 'user', 'pass'))
    response = Mock()
    response.json.return_value = {'id': 12, 'source_url': 'https://trendpulse.blog/card.jpg'}
    with patch.object(client, '_request_with_retry', return_value=response) as upload, \
         patch('requests.get') as download, patch('requests.post'):
        assert client._upload_media(card.url, card.alt)[0] == 12
        download.assert_not_called()
        assert upload.call_args.kwargs['data'] == Path(card.url).read_bytes()
        upload.reset_mock()
        assert client._upload_media('/etc/passwd', '') == (None, None)
        upload.assert_not_called()


@pytest.mark.parametrize('title,subject', [
    ('무선청소기 흡입력 비교: 시험 조건 읽기', 'vacuum'),
    ('공기청정기 평수', 'air'), ('엑셀 조건부 서식', 'spreadsheet'),
    ('노트북 램 16GB·32GB', 'laptop'), ('아이폰 배터리', 'phone'),
    ('와이파이 공유기', 'router'), ('발톱무좀치료방법', 'footcare'),
    ('건강검진 준비', 'health'), ('세금 환급', 'wallet'), ('접수 일정', 'calendar'),
    ('면접 자기소개', 'career'), ('노션 메모', 'notebook'), ('전입신고', 'home'),
    ('일상에서 확인할 내용', 'document'), ('장문제목' * 40, 'document'),
])
def test_subject_art_and_headline_stay_readable_inside_square_crop(tmp_path, monkeypatch, title, subject):
    monkeypatch.setattr(module, 'OUTPUT', tmp_path)
    path = Path(module.create_editorial_thumbnail(title, '<h2>본문의 확인 항목</h2>').url)
    audit = json.loads(path.with_suffix('.json').read_text())
    assert audit['version'] == module.VERSION and audit['subject'] == subject
    assert audit['headline'].replace(' ', '') == title.split(':')[0].replace(' ', '')
    assert all(150 <= x0 < x1 <= 1050 and 100 <= y0 < y1 < 785
               for x0, y0, x1, y1 in audit['headline_bounds'])
    # An actual non-text illustration occupies the upper central area.
    image = Image.open(path)
    assert len(image.crop((650, 200, 1000, 550)).getcolors(350 * 350)) > 100


def test_version_and_category_invalidate_old_thumbnail_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'OUTPUT', tmp_path)
    original = module.create_editorial_thumbnail('본문 확인', '', '건강')
    different_category = module.create_editorial_thumbnail('본문 확인', '', '리뷰')
    monkeypatch.setattr(module, 'VERSION', 'next-design')
    updated = module.create_editorial_thumbnail('본문 확인', '', '건강')
    assert len({original.url, different_category.url, updated.url}) == 3
