"""Offline regressions for the observed government-looking hostname false positive."""
import pytest

from src.keyword_gate import DOMINANT_DOMAIN_RE, gov_ratio


@pytest.mark.parametrize('host', [
    'nts.go.kr', 'www.nts.go.kr', 'webtv.nts.go.kr', 'www.hometax.go.kr',
    'www.wetax.go.kr', 'www.law.go.kr', 'oshri.kosha.or.kr', 'www.jnsports.or.kr',
    'www.bimkorea.or.kr', 'korea.kr', 'www.korea.kr',
    'gov.kr', 'www.gov.kr', 'plus.gov.kr', 'usa.gov', 'www.irs.gov',
    'gov.uk', 'www.gov.uk', 'gov.au', 'www.ato.gov.au',
    'naver.com', 'news.naver.com', 'namu.wiki', 'ko.wikipedia.org',
    'toss.im', 'kbstar.com', 'obank.kbstar.com', 'shinhan.com', 'bank.shinhan.com',
    'wooribank.com', 'spot.wooribank.com', 'hanabank.com', 'www.hanabank.com',
    'nonghyup.com', 'banking.nonghyup.com', 'chosun.com', 'www.joongang.co.kr',
    'www.donga.com', 'www.hankyung.com', 'www.mk.co.kr', 'www.yna.co.kr',
    'news.sbs.co.kr', 'news.kbs.co.kr', 'imnews.mbc.co.kr', 'brunch.co.kr',
    'WWW.NTS.GO.KR', 'news.naver.com.',
])
def test_existing_institutions_and_subdomains_remain_dominant(host):
    assert DOMINANT_DOMAIN_RE.search(host) is not None
    assert gov_ratio([host]) == 1.0


@pytest.mark.parametrize('host', [
    'alpha.gov.carspecial.kr', 'gov.carspecial.kr', 'carspecial.kr',
    'gov.example.com', 'agency.gov.example.com', 'agency.gov.uk.example.com',
    'gov.kr.evil.example', 'www.gov.kr.evil.example', 'notgov.kr',
    'agency.go.kr.example.com', 'agency.or.kr.example.com',
    'evil-korea.kr', 'notkorea.kr', 'korea.kr.example.com',
    'hometax.example.com', 'hometax-help.com', 'wetax.example.com', 'wetax-help.com',
    'naver.com.example.com', 'notnaver.com', 'evil-naver.com',
    'namu.wiki.example.com', 'wikipedia.org.example.com', 'toss.im.example.com',
    'kbstar.example.com', 'kbstar.com.example.com', 'notkbstar.com',
    'shinhan.example.com', 'shinhan-finance.com', 'wooribank-help.com',
    'hanabank.example.com', 'nonghyup.example.com',
    'notchosun.com', 'joongang.co.kr.example.com', 'donga.com.example.com',
    'hankyung.com.example.com', 'notmk.co.kr', 'yna.co.kr.example.com',
    'sbs.co.kr.example.com', 'kbs.co.kr.example.com', 'mbc.co.kr.example.com',
    'brunch.co.kr.example.com', 'news.govblog.com',
])
def test_brand_and_government_text_cannot_claim_an_unrelated_domain(host):
    assert DOMINANT_DOMAIN_RE.search(host) is None
    assert gov_ratio([host]) == 0.0


@pytest.mark.parametrize('host', [
    'https://www.naver.com', 'www.naver.com/path', 'www.naver.com?x=1',
    'www.naver.com#part', 'user@www.naver.com', 'www.naver.com:443',
    ' www.naver.com', 'www.naver.com ', 'www.naver.com\n',
    'www.naver.com\x00', 'www..naver.com', '.naver.com', 'naver.com..',
    '-bad.naver.com', 'bad-.naver.com', 'www.Ｎaver.com', '',
])
def test_only_dns_hosts_match_not_urls_credentials_or_malformed_aliases(host):
    assert DOMINANT_DOMAIN_RE.search(host) is None
    assert gov_ratio([host]) == 0.0


@pytest.mark.parametrize('suffix', ['gov', 'go.kr', 'or.kr', 'GOV', 'go.kr.', 'or.kr.', 'gov.'])
def test_generic_public_suffix_alone_is_not_an_institution(suffix):
    assert DOMINANT_DOMAIN_RE.search(suffix) is None
    assert gov_ratio([suffix]) == 0.0


@pytest.mark.parametrize('root', ['naver.com', 'nts.go.kr'])
@pytest.mark.parametrize('terminal_dot', ['', '.'])
@pytest.mark.parametrize('length,expected', [(253, True), (254, False)])
def test_total_dns_host_length_excludes_one_optional_terminal_dot(root, terminal_dot, length, expected):
    host = '.'.join(['a' * 63, 'b' * 63, 'c' * 63, 'd' * (length - 202), root])
    assert len(host) == length
    assert (DOMINANT_DOMAIN_RE.search(host + terminal_dot) is not None) is expected
    assert gov_ratio([host + terminal_dot]) == float(expected)


def test_observed_safety_manager_sample_counts_only_real_institutional_hosts():
    # Positive hosts preserved in employment run 34617454546; no network lookup.
    positive_hosts = ['alpha.gov.carspecial.kr', 'oshri.kosha.or.kr', 'glasswallet.com',
                      'cert.gisanara.com', 'www.jnsports.or.kr']
    assert gov_ratio(positive_hosts) == 2 / 5


def test_ratio_retains_its_denominator_and_empty_unknown_contract():
    assert gov_ratio([]) is None
    assert gov_ratio(['www.nts.go.kr', 'alpha.gov.carspecial.kr', 'ordinary.example']) == 1 / 3
    assert gov_ratio(['www.nts.go.kr', 'www.nts.go.kr', 'ordinary.example']) == 2 / 3


def test_patch_does_not_add_unlisted_education_or_commercial_domain_classes():
    assert gov_ratio(['www.global.ac.kr', 'www.harvard.edu', 'example.com']) == 0.0
