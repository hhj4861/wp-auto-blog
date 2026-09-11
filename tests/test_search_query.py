"""Pure spacing validation; no providers, files, or model calls are involved."""

import pytest

from src.search_query import validated_search_query


@pytest.mark.parametrize('keyword,proposed,expected', [
    ('대상포진초기증상', '대상포진 초기 증상', '대상포진 초기 증상'),
    ('대상포진 초기 증상', '대상포진초기증상', '대상포진초기증상'),
    ('대상포진초기증상', '  대상포진   초기  증상  ', '대상포진 초기 증상'),
    ('  ITQ 자격증 조회  ', 'ITQ자격증 조회', 'ITQ자격증 조회'),
    ('ITQ자격증조회', 'ITQ 자격증 조회', 'ITQ 자격증 조회'),
    ('컴활2급필기', '컴활 2급 필기', '컴활 2급 필기'),
    ('2026산업기사시험일정', '2026 산업기사 시험 일정', '2026 산업기사 시험 일정'),
    ('카페\u00a0조회', '카 페\u00a0조 회', '카 페\u00a0조 회'),
    ('\u00a0카페조회\u3000', '\u00a0카페 조회\u3000', '\u00a0카페 조회\u3000'),
])
def test_only_ascii_spacing_can_change(keyword, proposed, expected):
    query = validated_search_query(keyword, proposed)
    assert query == expected
    assert query.replace(' ', '') == keyword.replace(' ', '')


def test_no_proposal_preserves_existing_internal_spacing():
    assert validated_search_query('  대상포진  초기 증상  ') == '대상포진  초기 증상'
    assert validated_search_query('대상포진초기증상') == '대상포진초기증상'


@pytest.mark.parametrize('keyword', ['\u00a0키워드\u3000', '\u2002키워드\u202f', 'e\u0301조회', 'ＩＴＱ조회'])
def test_default_does_not_strip_or_normalize_non_ascii_characters(keyword):
    assert validated_search_query(keyword) == keyword
    assert validated_search_query('  ' + keyword + '  ') == keyword
    assert validated_search_query(keyword, keyword) == keyword


@pytest.mark.parametrize('keyword,proposed', [
    ('WORD자격증조회', 'W OR D자격증조회'),
    ('대장내시경비용OR무료', '대장내시경비용 OR 무료'),
    ('대장내시경비용 OR 무료', '대장내시경비용OR무료'),
    ('ANDROID조회', 'AND ROID조회'),
    ('NOT조회', 'NOT 조회'),
    ('검사NEAR예약', '검사 NEAR 예약'),
    ('검사AROUND예약', '검사 AROUND 예약'),
    ('site : go.kr', 'site:go.kr'),
    ('site:go.kr', 'site : go.kr'),
    ('intitle : 검사', 'intitle:검사'),
    ('검사비용-무료', '검사비용 -무료'),
    ('검사비용 - 무료', '검사비용 -무료'),
    ('"대상포진초기증상"', '"대상포진 초기 증상"'),
    ('2025 . . 2026', '2025..2026'),
    ('검사|예약', '검사 | 예약'),
    ('PC+모바일(2026)', 'PC + 모바일 (2026)'),
    ('C++자격증', 'C++ 자격증'),
])
def test_identical_characters_cannot_activate_or_change_search_syntax(keyword, proposed):
    assert keyword.replace(' ', '') == proposed.replace(' ', '')
    with pytest.raises(ValueError, match='^search_query_syntax_change$'):
        validated_search_query(keyword, proposed)


@pytest.mark.parametrize('keyword', ['site:go.kr', '검사 OR 예약', '검사 -무료',
                                     '"검사 비용"', '"검사  비용"', 'C++자격증', '2025..2026'])
def test_original_queries_with_syntax_or_ordinary_symbols_remain_compatible(keyword):
    assert validated_search_query(keyword) == keyword
    assert validated_search_query(keyword, keyword) == keyword
    assert validated_search_query(keyword, '  ' + keyword + '  ') == keyword


@pytest.mark.parametrize('keyword,proposed', [
    ('2026산업기사시험일정', '20 26 산업기사 시험 일정'),
    ('SQLD시험', 'SQL D 시험'),
    ('ITQ자격증조회', 'I T Q 자격증 조회'),
    ('ITQ2급', 'ITQ 2급'),
    ('SQL D시험', 'SQLD 시험'),
    ('20 26산업기사시험일정', '2026 산업기사 시험 일정'),
])
def test_ascii_letter_and_digit_tokens_cannot_be_split_or_merged(keyword, proposed):
    assert keyword.replace(' ', '') == proposed.replace(' ', '')
    with pytest.raises(ValueError, match='^search_query_token_change$'):
        validated_search_query(keyword, proposed)


def test_explicit_original_query_preserves_repeated_spaces_like_default():
    keyword = '  ITQ  자격증조회  '
    default = validated_search_query(keyword)
    assert default == 'ITQ  자격증조회'
    assert validated_search_query(keyword, keyword) == default
    assert validated_search_query(keyword, default) == default
    assert validated_search_query(keyword, ' ' + default + ' ') == default
    # Only a genuine spacing alternative is collapsed and then remains stable.
    changed = validated_search_query(keyword, 'ITQ   자격증  조회')
    assert changed == 'ITQ 자격증 조회'
    assert validated_search_query(keyword, changed) == changed


@pytest.mark.parametrize('keyword,proposed', [
    ('대상포진초기증상', '대승포징 초기 증상'),
    ('대상포진초기증상', '대상포진 증상'),
    ('대상포진초기증상', '대상포진 초기 증상 치료'),
    ('2026산업기사시험일정', '2027 산업기사 시험 일정'),
    ('ITQ자격증조회', 'itq 자격증 조회'),
    ('ITQ자격증조회', 'ＩＴＱ 자격증 조회'),
    ('대장내시경비용', '대장내시경\u00a0비용'),
    ('대장내시경비용', '대장내시경\u3000비용'),
    ('대장내시경\u00a0비용', '대장내시경 비용'),
    ('PC+모바일', 'PC 모바일'),
    ('PC+모바일', '모바일+PC'),
    ('대상포진초기증상', '"대상포진 초기 증상"'),
    ('대상포진초기증상', '대상포진 초기 증상 site:go.kr'),
    ('대상포진초기증상', '대상포진 초기 증상 OR 치료'),
    ('대장내시경&nbsp;비용', '대장내시경 비용'),
    ('가', '\u1100\u1161'),
    ('é', 'e\u0301'),
])
def test_query_cannot_change_characters_or_apply_unicode_or_html_normalization(keyword, proposed):
    with pytest.raises(ValueError, match='^search_query_mismatch$'):
        validated_search_query(keyword, proposed)


@pytest.mark.parametrize('value', [None, True, 123, [], {}, b'keyword', '', '   ', '\u00a0'])
def test_invalid_keyword_has_only_a_fixed_error(value):
    with pytest.raises(ValueError, match='^invalid_keyword$'):
        validated_search_query(value)


@pytest.mark.parametrize('value', [True, 123, [], {}, b'keyword', '', '   ', '\u00a0'])
def test_invalid_proposal_has_only_a_fixed_error(value):
    with pytest.raises(ValueError, match='^invalid_search_query$'):
        validated_search_query('키워드', value)


@pytest.mark.parametrize('forbidden', [
    '\0', '\t', '\n', '\r', '\x1f', '\x7f', '\x85',
    '\u200b', '\u200d', '\u202e', '\u2066', '\ufeff',
    '\ud800', '\udfff', '\u2028', '\u2029',
])
@pytest.mark.parametrize('field', ['keyword', 'proposed'])
def test_controls_format_surrogates_and_line_separators_are_rejected_before_trimming(forbidden, field):
    if field == 'keyword':
        arguments, reason = (forbidden + '키워드' + forbidden,), 'invalid_keyword'
    else:
        arguments, reason = ('키워드', forbidden + '키워드' + forbidden), 'invalid_search_query'
    with pytest.raises(ValueError, match='^' + reason + '$'):
        validated_search_query(*arguments)


def test_lengths_are_bounded_before_trimming_or_collapsing():
    assert validated_search_query('가' * 256) == '가' * 256
    assert validated_search_query('가' * 255, '가' * 255 + ' ') == '가' * 255
    with pytest.raises(ValueError, match='^invalid_keyword$'):
        validated_search_query('가' * 256 + ' ')
    with pytest.raises(ValueError, match='^invalid_search_query$'):
        validated_search_query('키워드', ' ' * 254 + '키워드')


@pytest.mark.parametrize('raw,reason', [
    ('https://example.test/?token=never-print-this', 'search_query_mismatch'),
    ('SECRET=never-print-this\n', 'invalid_search_query'),
    ('인용한 원문이나 모델 설명을 검색어 대신 반환했습니다.', 'search_query_mismatch'),
])
def test_error_messages_never_include_model_text_or_source_quotes(raw, reason):
    with pytest.raises(ValueError) as failure:
        validated_search_query('대상포진초기증상', raw)
    assert str(failure.value) == reason
    assert raw not in str(failure.value)
