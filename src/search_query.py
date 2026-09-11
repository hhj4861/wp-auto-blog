"""Allow search-query spacing changes without changing the measured keyword."""

import re
import unicodedata


MAX_QUERY_LENGTH = 256
_FORBIDDEN_CATEGORIES = frozenset({'Cc', 'Cf', 'Cs', 'Zl', 'Zp'})
_BOOLEAN_OPERATORS = frozenset({'AND', 'OR', 'NOT', 'XOR', 'NEAR', 'AROUND',
                                'ADJ', 'BEFORE', 'AFTER', 'ONEAR'})


def _checked_text(value, reason):
    if (not isinstance(value, str) or not 1 <= len(value) <= MAX_QUERY_LENGTH
            or not value.strip()
            or any(unicodedata.category(char) in _FORBIDDEN_CATEGORIES for char in value)):
        raise ValueError(reason)
    return value


def validated_search_query(keyword, proposed=None) -> str:
    """Return the original query or an exact, ASCII-space-only alternative.

    Length and forbidden-character checks apply before trimming. Proposed queries
    may add or remove U+0020 only; case, Unicode, punctuation and digits remain
    exact, including the sequence of contiguous ASCII letters/digits. Spacing
    changes involving punctuation/symbols or standalone uppercase
    operators are conservatively rejected: they can activate query syntax or
    change its scope. This also holds ordinary terms such as C++ unchanged.
    No normalization, HTML decoding, or model text enters error messages.
    """
    keyword = _checked_text(keyword, 'invalid_keyword')
    if proposed is None:
        return keyword.strip(' ')
    proposed = _checked_text(proposed, 'invalid_search_query')
    if proposed.strip(' ') == keyword.strip(' '):
        return keyword.strip(' ')
    if proposed.replace(' ', '') != keyword.replace(' ', ''):
        raise ValueError('search_query_mismatch')
    query = ' '.join(part for part in proposed.split(' ') if part)
    if query != keyword.strip(' '):
        # Query syntax varies by provider. Do not try to rewrite or escape it:
        # only ordinary word spacing may change, and an unchanged query remains
        # compatible. Inspect both sides to catch activation and deactivation.
        if (any(unicodedata.category(char)[0] in {'P', 'S'} for char in keyword)
                or _BOOLEAN_OPERATORS.intersection(keyword.split())
                or _BOOLEAN_OPERATORS.intersection(query.split())):
            raise ValueError('search_query_syntax_change')
    if re.findall(r'[A-Za-z0-9]+', keyword) != re.findall(r'[A-Za-z0-9]+', query):
        raise ValueError('search_query_token_change')
    return query
