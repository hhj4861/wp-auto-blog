"""GSC URL Inspection 조회 URL 정규화 회귀 테스트.

2026-08-24 사고: Yoast 사이트맵은 퍼센트인코딩을 소문자(%ec)로, GSC는 RFC 3986
정규형인 대문자(%EC)로 보관한다. 소문자 그대로 Inspection API에 넘기면 색인된
URL조차 '알려지지 않은 URL'로 돌아와, trendpulse 사이트맵 330개 중 279개가
미발견으로 오판됐다. 정규화를 코드에서 강제한다.
"""

from src.gsc_client import normalize_url


def test_lowercase_percent_hex_is_uppercased():
    src = "https://trendpulse.blog/%ec%b1%85-%ec%a0%84%ec%b2%b4-review-2026/"
    assert normalize_url(src) == (
        "https://trendpulse.blog/%EC%B1%85-%EC%A0%84%EC%B2%B4-review-2026/")


def test_ascii_url_untouched():
    src = "https://bytepulse.io/tailwind-css-alternatives-review-2026/"
    assert normalize_url(src) == src


def test_already_uppercase_is_idempotent():
    src = "https://trendpulse.blog/%EC%B1%85-review-2026/"
    assert normalize_url(src) == src == normalize_url(normalize_url(src))


def test_query_string_and_non_escape_percent_preserved():
    # %xx 시퀀스만 건드린다 — 리터럴 %는 그대로, 쿼리스트링도 동일 규칙
    src = "https://x.io/a%2fb/?q=100%&t=%ec%a0%84"
    assert normalize_url(src) == "https://x.io/a%2Fb/?q=100%&t=%EC%A0%84"


def test_inspect_url_normalizes_before_request(monkeypatch):
    """정규화가 helper에만 있고 실제 호출 경로에서 빠지는 회귀를 막는다."""
    import src.gsc_client as g

    sent = {}

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"inspectionResult": {"indexStatusResult": {}}}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent["inspectionUrl"] = json["inspectionUrl"]
        return _Resp()

    monkeypatch.setattr(g.requests, "post", fake_post)
    monkeypatch.setattr(g, "_headers", lambda: {})
    g.inspect_url("https://trendpulse.blog/%ec%b1%85-review-2026/",
                  "https://trendpulse.blog/")
    assert sent["inspectionUrl"] == "https://trendpulse.blog/%EC%B1%85-review-2026/"
