#!/usr/bin/env python3
"""Render article-grounded preview files without WordPress or network access."""
import argparse
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import editorial_thumbnail

SAMPLES = (
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
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    editorial_thumbnail.OUTPUT = args.output / '.rendered'
    for name, title, body, category in SAMPLES:
        result = editorial_thumbnail.create_editorial_thumbnail(title, body, category)
        path = Path(result.url)
        for suffix in ('.jpg', '.json'):
            shutil.copyfile(path.with_suffix(suffix), args.output / (name + suffix))
    shutil.rmtree(editorial_thumbnail.OUTPUT)


if __name__ == '__main__':
    main()
