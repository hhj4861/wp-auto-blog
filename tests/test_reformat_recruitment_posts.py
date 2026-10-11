from copy import deepcopy
from unittest.mock import Mock
import pytest
from bs4 import BeautifulSoup
from scripts.reformat_recruitment_posts import TARGETS, convert_legacy_recruitment, preservation_snapshot
from scripts.repair_reader_css import repair


def legacy(key):
    headings, groups = TARGETS[key]
    chapters = []
    for i, (heading, group) in enumerate(zip(headings, groups)):
        body = f'<h2 id="section-{i}">{heading}</h2><p>설명 {i} 첫째.</p><p>설명 {i} 둘째.</p>'
        if group == 'facts': body += '<table><tr><th>마감</th><td>공고 확인</td></tr></table>'
        if group == 'prepare': body += '<ol data-visual="steps"><li>제출 확인</li></ol>'
        if group == 'check': body += '<ul data-visual="checklist"><li>지원자격 확인</li></ul>'
        if group == 'faq': body += '<div data-faq-card="1"><h3>질문?</h3><p>답변.</p></div>'
        chapters.append('<section>'+body+'</section>' if key[0] == 1897 else body)
    return ('<div class="wpab-article"><section id="quick-answer"><p>핵심 요약</p></section>'
            '<details id="article-toc"><a href="#section-0">옛 목차</a></details>' + ''.join(chapters) +
            '<div><ins class="adsbygoogle" style="min-height:280px" data-ad-slot="123"></ins></div>'
            '<section id="verified-sources"><a href="https://example.com/source">공식 출처</a></section>'
            '<div><a href="https://example.com/apply">지원 바로가기</a><p>공식 사이트로 이동합니다</p></div>'
            '<p id="policy-notice">안내 보존</p><img src="image.png" alt="예시"></div>'
            '<script type="application/ld+json">{"name":"FAQ"}</script>')


@pytest.mark.parametrize('key', list(TARGETS))
def test_conversion_preserves_editorial_content_and_keeps_sources_ads_visible(key):
    raw = legacy(key)
    fixed = convert_legacy_recruitment(raw, *key)
    soup = BeautifulSoup(fixed, 'html.parser')
    assert preservation_snapshot(raw) == preservation_snapshot(fixed)
    assert len(soup.select('[data-reader-panel]')) == 5
    assert [a.text for a in soup.select('[data-reader-menu] a')] == ['모집 조건','직무·조건','준비 가이드','최종 점검','FAQ','전체 보기']
    for node in soup.select('#verified-sources, ins.adsbygoogle, [data-monetization]'):
        assert not node.find_parent(attrs={'data-reader-panel':'1'})
    assert soup.select_one('details[data-faq-card] summary')
    assert convert_legacy_recruitment(fixed, *key) == fixed
    assert len(soup.select('[id^="section-"]')) == 6


@pytest.mark.parametrize('key', list(TARGETS))
def test_changed_identity_structure_or_sources_fail_closed(key):
    raw = legacy(key)
    with pytest.raises(ValueError): convert_legacy_recruitment(raw, 999, key[1])
    with pytest.raises(ValueError): convert_legacy_recruitment(raw.replace('verified-sources','unknown'), *key)
    with pytest.raises(ValueError): convert_legacy_recruitment(raw.replace(TARGETS[key][0][0], '다른 제목'), *key)
    with pytest.raises(ValueError): convert_legacy_recruitment(raw.replace('data-visual="steps"',''), *key)


def test_authenticated_conversion_backup_and_content_only_update(tmp_path):
    key = next(iter(TARGETS)); raw = legacy(key); fixed = convert_legacy_recruitment(raw, *key)
    post = dict(id=key[0],slug=key[1],status='publish',content={'raw':raw},modified_gmt='now',title={'raw':'제목'},link='https://trendpulse.blog/'+key[1]+'/')
    saved = deepcopy(post); saved['content']['raw'] = fixed
    response = lambda p: Mock(json=lambda:deepcopy(p))
    session = Mock(); session.get.side_effect = [response(post),response(post),response(saved)]
    result = repair(session,*key,apply=True,legacy_recruitment=True,backup_dir=tmp_path)
    assert result['verified']
    assert session.post.call_args.kwargs['json'] == {'content':fixed}
    assert (tmp_path / f'{key[0]}-original.html').read_text() == raw
    assert (tmp_path / f'{key[0]}-proposed.html').read_text() == fixed
    session = Mock(); session.get.return_value = response(post)
    assert repair(session,*key,legacy_recruitment=True,backup_dir=tmp_path)['dry_run']
    session.post.assert_not_called()
