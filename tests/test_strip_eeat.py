"""strip_fabricated_eeat — 팀명 무관 구조적 저자박스 제거 회귀 테스트.

버그: 과거엔 'Bytepulse Engineering Team' 리터럴만 잡아 'K-Pulse Beauty/Style/
Editorial Team' 등 K-컬처 변종 115개가 살아남음(AdSense 저가치 사유). 구조로 잡도록 수정.
"""

from src.monetization import strip_fabricated_eeat

WRAPPER_OPEN = '<div class="post-content category-k-beauty" data-category="K-Beauty">'


def _author_box(team: str, exp: str, initials: str = "KP") -> str:
    return (
        '<div style="display: flex; flex-wrap: wrap; align-items: center; gap: 16px; '
        'margin: 16px 0; padding: 16px; background: #1a1a2e; border-radius: 8px;">'
        '<div style="display: flex; align-items: center; gap: 10px;">'
        '<div style="width: 44px; height: 44px; background: linear-gradient(135deg, #ff6b9d, '
        f'#c44569); border-radius: 50%; display: flex;">{initials}</div><div>'
        f'<div style="color: #e8e8e8; font-weight: 600;">{team}</div>'
        f'<div style="color: #94a3b8; font-size: 0.85em;">{exp}</div></div></div>'
        '<div style="color: #64748b; font-size: 0.85em; margin-left: auto;">'
        '<span>📅 Updated: January 22, 2026</span> · <span>⏱️ 9 min read</span></div></div>'
    )


def _wrap(inner: str) -> str:
    return (f"{WRAPPER_OPEN}\n<p>Intro body that must survive.</p>\n{inner}\n"
            "<h2>Real Section</h2><p>More body.</p></div>")


def test_removes_kpulse_beauty_team_variant():
    html = _wrap(_author_box("K-Pulse Beauty Team",
                             "5+ years testing K-Beauty from Seoul to the US"))
    out = strip_fabricated_eeat(html)
    assert "K-Pulse Beauty Team" not in out
    assert "years testing" not in out
    assert "border-radius: 50%" not in out


def test_removes_all_team_name_variants():
    for team, exp in [
        ("K-Pulse Editorial Team", "5+ years covering Korean fashion trends"),
        ("K-Pulse Style Team", "Sourcing Seoul street style since 2019"),
        ("Bytepulse Engineering Team", "5+ years testing developer tools"),
        ("Bytepulse K-Food Team", "Home-testing Korean recipes since 2021"),
    ]:
        out = strip_fabricated_eeat(_wrap(_author_box(team, exp)))
        assert team not in out, f"{team} 미제거"


def test_preserves_body_and_wrapper():
    out = strip_fabricated_eeat(_wrap(_author_box("K-Pulse Beauty Team", "5+ years testing")))
    assert "Intro body that must survive." in out
    assert "Real Section" in out
    assert 'class="post-content' in out  # 래퍼 보존


def test_removes_multiple_boxes_in_one_post():
    two = (_author_box("K-Pulse Beauty Team", "5+ years testing skincare")
           + "<p>mid</p>"
           + _author_box("K-Pulse Style Team", "5+ years covering fashion", "KS"))
    out = strip_fabricated_eeat(_wrap(two))
    assert "Team" not in out
    assert "mid" in out


def test_noop_when_no_author_box():
    clean = _wrap("<p>Just honest content with the word team in a sentence.</p>")
    assert strip_fabricated_eeat(clean) == clean
