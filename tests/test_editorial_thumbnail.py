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
