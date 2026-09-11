"""Read fixed public sources; accessibility alone is not approval to publish."""
import argparse
import json
import logging
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.editorial import fetch_source


CASES = (
    ('nts_original', 'https://www.nts.go.kr/nts/na/ntt/selectNttInfo.do?mi=5850&nttSn=1349564'),
    ('nts_mirror', 'https://webtv.nts.go.kr/nts/na/ntt/selectNttInfo.do?mi=2201&nttSn=1349564'),
    ('korea_policy', 'https://www.korea.kr/news/policyNewsView.do?newsId=148960444'),
    ('nts_invoice_primary_selected', 'https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=7788&mi=2453'),
    ('nts_invoice_primary_menu', 'https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=7788&mi=2462'),
    ('nts_invoice_secondary_selected', 'https://t.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=7789&mi=2463'),
    ('nts_invoice_secondary_canonical', 'https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=7789&mi=2463'),
)
SOURCE_FIELDS = ('url', 'original_url', 'title', 'checked_on', 'sha256', 'excerpt')
logger = logging.getLogger(__name__)


def probe_case(name, url):
    started = time.monotonic()
    source = None
    try:
        fetched = fetch_source(url)
        if (isinstance(fetched, dict)
                and all(isinstance(fetched.get(key), str) and fetched[key].strip() for key in SOURCE_FIELDS)):
            # Retain only public evidence fields, never arbitrary provider metadata.
            source = {key: fetched[key] for key in SOURCE_FIELDS}
            source['excerpt'] = source['excerpt'][:8000]
        elif fetched is not None:
            logger.warning('Official source probe failed: invalid_source_shape')
    except Exception:
        # Even unexpected fetch failures must not stop the remaining fixed cases
        # or expose arbitrary exception text, request URLs or headers.
        logger.warning('Official source probe failed: unexpected_fetch_error')
    summary = {
        'case': name, 'success': source is not None,
        'title_chars': len(source['title']) if source else 0,
        'excerpt_chars': len(source['excerpt']) if source else 0,
        'elapsed_seconds': round(max(0, time.monotonic() - started), 3),
    }
    print(json.dumps(summary, sort_keys=True))
    return {**summary, 'source': source}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Public source JSON output path')
    args = parser.parse_args(argv)
    reports = [probe_case(name, url) for name, url in CASES]
    artifact = {'schema_version': 1, 'purpose': 'source_accessibility_only', 'cases': reports}
    try:
        args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except OSError:
        logger.warning('Official source probe failed: artifact_write_error')
        return 2
    return 0 if any(report['success'] for report in reports) else 1


if __name__ == '__main__':
    raise SystemExit(main())
