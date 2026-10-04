#!/usr/bin/env python3
"""Read-only ownership check by default; submit existing URLs only explicitly."""
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from src.indexnow import check_key, submit_urls


def main(argv=None):
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='trendpulse.blog')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--submit', action='append', metavar='PUBLIC_URL')
    group.add_argument('--sitemap', metavar='SITEMAP_URL')
    args = parser.parse_args(argv)
    key_status = check_key(args.host)
    print(json.dumps({'key_check': key_status}))
    if key_status != 'key_matches':
        return 1
    urls = args.submit or []
    if args.sitemap:
        parsed = urlsplit(args.sitemap)
        if (parsed.scheme != 'https' or parsed.hostname != args.host
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            parser.error('Sitemap must belong to the selected HTTPS host')
        try:
            response = requests.get(args.sitemap, timeout=30, allow_redirects=False)
        except requests.RequestException:
            print(json.dumps({'status': 'sitemap_network_error'}))
            return 1
        if response.status_code != 200:
            print(json.dumps({'status': 'sitemap_unavailable'}))
            return 1
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            print(json.dumps({'status': 'invalid_sitemap'}))
            return 1
        if root.tag.split('}')[-1] != 'urlset':
            parser.error('Use a URL sitemap, not a sitemap index')
        urls = [node.text for node in root.findall('.//{*}loc') if node.text]
    if urls:
        result = submit_urls(urls, args.host)
        print(json.dumps(result))
        return 0 if result['accepted'] else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
