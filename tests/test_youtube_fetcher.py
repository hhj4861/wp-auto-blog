"""YouTubeFetcher 키리스 스크레이프 폴백 테스트."""

import pytest
from unittest.mock import Mock, patch

from src.youtube_fetcher import YouTubeFetcher

FAKE_RESULTS_HTML = (
    '... "videoRenderer":{"videoId":"dQw4w9WgXcQ","thumbnail":{},'
    '"title":{"runs":[{"text":"STAYC World Tour 2026 Concert"}]},'
    '"ownerText":{"runs":[{"text":"STAYC Official"}]} ...'
)


class TestKeylessScrapeSearch:
    @pytest.mark.unit
    def test_search_without_api_key_falls_back_to_scrape(self):
        """API 키가 없으면 검색 결과 페이지 스크레이프로 영상을 찾는다."""
        fetcher = YouTubeFetcher(api_key=None)
        fetcher.api_key = None  # env 무시

        html_resp = Mock(status_code=200, text=FAKE_RESULTS_HTML)
        html_resp.raise_for_status = Mock()
        head_resp = Mock(status_code=200, headers={"content-length": "50000"})

        with patch.object(fetcher.session, "get", return_value=html_resp), \
             patch.object(fetcher.session, "head", return_value=head_resp):
            video = fetcher.search("STAYC world tour")

        assert video is not None
        assert video.video_id == "dQw4w9WgXcQ"
        assert "STAYC" in video.title
        assert video.channel == "STAYC Official"
        assert "dQw4w9WgXcQ" in video.thumbnail_url

    @pytest.mark.unit
    def test_scrape_returns_none_when_no_video_found(self):
        fetcher = YouTubeFetcher(api_key=None)
        fetcher.api_key = None
        empty = Mock(status_code=200, text="<html>no results</html>")
        empty.raise_for_status = Mock()
        with patch.object(fetcher.session, "get", return_value=empty):
            assert fetcher.search("zzz") is None
