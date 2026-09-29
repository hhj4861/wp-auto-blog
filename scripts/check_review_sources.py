#!/usr/bin/env python3
"""Read fixed public sources; never select a topic, alter history, or publish."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.editorial import fetch_source
from src.review_discovery import compact, relevant_source


def main():
    cases = [
        ('kca_html_connectivity_only', 'https://www.kca.go.kr/kca/sub.do?menukey=5084&mode=view&no=1001956093',
         None, True, None, ['2016-11-13', '문턱']),
        ('kca_attachment_only', 'https://www.kca.go.kr/home/sub.do?menukey=4002&mode=view&no=1003905732',
         None, False, None, []),
        ('tablet_is_not_laptop', 'https://www.samsung.com/sec/support/model/SM-P550NZBEKOO/',
         '노트북메모리', True, False, []),
        ('laptop_specification', 'https://www.samsung.com/sec/support/model/NT960XHA-KC51G/',
         '노트북메모리', True, True, ['16gb']),
        ('catalog_is_not_evidence', 'https://www.samsung.com/sec/memory-storage/all-memory-storage/',
         '노트북메모리', False, False, []),
        ('roborock_threshold', 'https://kr.roborock.com/pages/roborock-qrevo-curv',
         '로봇청소기문턱', True, True, ['문턱', '3cm', '4cm', '내부테스트']),
        ('dreame_threshold', 'https://store.kr.dreametech.com/products/x50-ultra',
         '로봇청소기문턱', True, True, ['문턱', '42cm', '매트']),
    ]
    results = []
    for name, url, keyword, readable, relevant, terms in cases:
        source = fetch_source(url)
        body = compact((source or {}).get('excerpt', ''))
        matches = relevant_source(keyword, source) if keyword else None
        conditions = all(compact(term) in body for term in terms)
        passed = bool(source) == readable and matches == relevant and conditions
        results.append({'case': name, 'url': url, 'passed': passed,
                        'readable': bool(source), 'relevant_to_keyword': matches,
                        'required_conditions_present': conditions,
                        'excerpt_chars': len((source or {}).get('excerpt', '')),
                        'sha256': (source or {}).get('sha256')})
    print(json.dumps({'checks': results, 'passed': all(row['passed'] for row in results),
                      'scope': 'Public source extraction only; no semantic selection or publication approval.'},
                     ensure_ascii=False, indent=2))
    return 0 if all(row['passed'] for row in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
