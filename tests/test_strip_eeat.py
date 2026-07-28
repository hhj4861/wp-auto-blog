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


def test_removes_benchmark_methodology_box_and_anchors():
    box = ('<div id="benchmark-methodology" style="background: #1a1a2e; padding: 24px;">'
           '<h3>📊 Benchmark Methodology</h3>'
           '<p>We tested 50 code completion requests across projects.</p></div>')
    inline = ('<p>Response time 0.8s '
              '<a href="#benchmark-methodology" style="color:#3b82f6;">our benchmark ↓</a>'
              ' beats rivals.</p>')
    out = strip_fabricated_eeat(_wrap(box + inline))
    assert "Benchmark Methodology" not in out
    assert "We tested 50" not in out
    assert "benchmark-methodology" not in out  # 인라인 앵커도 제거
    assert "Response time 0.8s" in out and "beats rivals" in out  # 문장 본문은 보존


def test_removes_how_we_reviewed_box():
    box = ('<div style="border-left: 4px solid #3b82f6; padding: 12px;">'
           '<h4>📋 How We Reviewed These Shows</h4>'
           '<ul><li><strong>Team:</strong> K-fans with 5+ years following K-TV</li></ul></div>')
    out = strip_fabricated_eeat(_wrap(box))
    assert "How We Reviewed" not in out
    assert "5+ years following" not in out


def test_size_cap_prevents_section_over_removal():
    # 방법론 마커가 거대한 섹션 안에 있어도, 섹션 전체를 지우면 안 된다(상한).
    big = "<p>Real article paragraph. </p>" * 400  # ~12k
    section = f'<div style="margin:20px;"><h3>Benchmark Methodology</h3>{big}</div>'
    out = strip_fabricated_eeat(_wrap(section))
    assert "Real article paragraph." in out  # 본문 보존(과다제거 스킵)


def test_neutralizes_first_person_testing_prose():
    html = _wrap(
        "<p>In our testing, it absorbed instantly.</p>"
        "<p>Based on our benchmarks across prototypes, the Pi 5 wins.</p>"
        "<p>No greasy film in our tests. Consistent throughput (our benchmark testing) here.</p>"
    )
    out = strip_fabricated_eeat(html)
    assert "our testing" not in out.lower()
    assert "our benchmark" not in out.lower()
    assert "our tests" not in out.lower()
    # 문장 본문(주장)은 보존
    assert "it absorbed instantly" in out
    assert "the Pi 5 wins" in out
    assert "In testing, it absorbed" in out  # 소유격만 탈락, 문장 유지
