#!/usr/bin/env python3
"""Preview thumbnails without WordPress; native ImageGen is explicit and strictly checked."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import editorial_thumbnail

SAMPLES = (
    ('lung', '폐암 초기증상: 무증상 가능성과 진료 신호',
     '<h2>폐와 기침의 변화</h2><p>초기에는 증상이 없을 수 있으며 증상만으로 진단할 수 없습니다.</p>', '건강'),
    ('footcare', '발톱무좀치료방법: 먹는 약·바르는 약과 치료 전 확인사항',
     '<h2>치료 전 확인사항</h2>', '건강'),
    ('vacuum', '무선청소기 흡입력 비교: 수치와 시험 조건 읽는 법',
     '<h2>흡입력 단위와 시험 조건</h2>', '리뷰'),
    ('spreadsheet', '엑셀 조건부 서식: 필요한 데이터만 한눈에',
     '<h2>조건에 맞는 셀 강조하기</h2>', '생산성'),
    ('laptop', '노트북 램 16GB·32GB: 내 작업에 맞게 고르기',
     '<h2>작업별 메모리 확인</h2>', '리뷰'),
    ('career', '면접 자기소개: 경험을 명확하게 전하는 법',
     '<h2>경험 선택과 구성</h2>', '취업'),
    ('air', '공기청정기 평수: 사용 면적 확인하기',
     '<h2>공간에 맞는 사용 면적</h2>', '리뷰'),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--provider', choices=('editorial', 'codex'), default='editorial')
    parser.add_argument('--sample', choices=[row[0] for row in SAMPLES], action='append')
    args = parser.parse_args()
    os.environ["BLOG_THUMBNAIL_PROVIDER"] = args.provider
    args.output.mkdir(parents=True, exist_ok=True)
    editorial_thumbnail.OUTPUT = args.output / '.rendered'
    for name, title, body, category in SAMPLES:
        if args.sample and name not in args.sample:
            continue
        result = editorial_thumbnail.create_editorial_thumbnail(title, body, category)
        path = Path(result.url)
        for suffix in ('.jpg', '.json'):
            shutil.copyfile(path.with_suffix(suffix), args.output / (name + suffix))
        audit = json.loads(path.with_suffix('.json').read_text())
        if args.provider == 'codex' and audit.get('provider') != 'codex_imagegen':
            raise RuntimeError('Native image generation failed; fallback preview is not a pass')
    shutil.rmtree(editorial_thumbnail.OUTPUT)


if __name__ == '__main__':
    main()
