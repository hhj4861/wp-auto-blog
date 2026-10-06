"""Acquire open official vacancies before spending model research on employers.

Listing rows are locators only. A candidate needs a separately fetched detail,
its own measured demand, and all the existing search/intent/article gates.
"""
from datetime import date
import re
from time import monotonic
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
import requests

from src import recruitment_sources
from src.editorial import fetch_source

LIST_URL = 'https://job.alio.go.kr/recruit.do'
MAX_PAGES = 3
MAX_DETAILS = 18
MAX_EMPLOYERS = 12
BUDGET_SECONDS = 150


def parse_date(value):
    match = re.search(r'\b(20\d{2}|\d{2})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})\b', value)
    if not match:
        return None
    year, month, day = map(int, match.groups())
    try:
        return date(year + 2000 if year < 100 else year, month, day)
    except ValueError:
        return None


def listing_rows(html, today):
    soup = BeautifulSoup(html, 'html.parser')
    rows, seen = [], set()
    for tr in soup.select('tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 9:
            continue
        anchor = cells[2].find('a', href=True)
        if anchor is None:
            continue
        url = urljoin(LIST_URL, anchor['href'])
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'job.alio.go.kr'
                or parsed.path != '/recruitview.do' or not re.fullmatch(r'idx=\d+', parsed.query)):
            continue
        end = parse_date(cells[7].get_text(' ', strip=True))
        # Same-day closing times are ambiguous. Do not seed already-closing jobs.
        if end is None or end <= today or cells[8].get_text(strip=True) != '진행중' or url in seen:
            continue
        name = cells[3].get_text(' ', strip=True)
        name = re.sub(r'\(주\)|㈜|주식회사|^재단법인\s*|^학교법인\s*', '', name).strip()
        keyword = re.sub(r'\s+', '', name) + '채용'
        if not recruitment_sources.employer(keyword):
            continue
        seen.add(url)
        rows.append({'keyword': keyword, 'employer': name, 'url': url,
                     'title': cells[2].get_text(' ', strip=True),
                     'employment_type': cells[5].get_text(' ', strip=True),
                     'deadline': end.isoformat()})
    return rows


def fetch_listing(page):
    # Fixed public endpoint; never follow a redirect to an arbitrary host.
    deadline = monotonic() + 20
    with requests.get(LIST_URL, params={'pageNo': page, 'ing': '2'},
                      timeout=12, allow_redirects=False, stream=True) as response:
        if response.status_code != 200 or 'html' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('listing_unavailable')
        content = bytearray()
        for chunk in response.iter_content(16384):
            if monotonic() >= deadline:
                raise ValueError('listing_time_budget')
            content.extend(chunk)
            if len(content) > 2_000_000:
                raise ValueError('listing_too_large')
        return bytes(content)


def detail_matches(row, source, today):
    if (not isinstance(source, dict) or source.get('url') != row['url']
            or recruitment_sources.source_issue(row['keyword'], source, today=today)):
        return False
    # Independently fetched detail must identify the same current application
    # window. A list status or a date buried in an old body cannot prove it.
    metadata = source['excerpt'].split('등록일', 1)[0]
    token = r'(?:20\d{2}|\d{2})[.\-/]\s*\d{1,2}[.\-/]\s*\d{1,2}'
    periods = re.findall(r'채용기간\s*(' + token + r')\s*~\s*(' + token + r')', metadata)
    if len(periods) != 1:
        return False
    start, end = map(parse_date, periods[0])
    return bool(start and end and start <= today < end and end.isoformat() == row['deadline'])


def discover(today, *, deadline=None):
    deadline = min(deadline if deadline is not None else float('inf'), monotonic() + BUDGET_SECONDS)
    audit = {'provider': 'job_alio_open_list', 'status': 'empty', 'pages': 0,
             'listed': 0, 'detail_attempts': 0, 'verified': 0, 'errors': []}
    rows, seen = [], set()
    for page in range(1, MAX_PAGES + 1):
        if monotonic() >= deadline:
            audit['errors'].append('time_budget')
            break
        try:
            batch = listing_rows(fetch_listing(page), today)
        except (requests.RequestException, ValueError):
            audit['errors'].append('listing_unavailable')
            break
        audit['pages'] += 1
        fresh = [row for row in batch if row['url'] not in seen]
        rows.extend(fresh)
        seen.update(row['url'] for row in fresh)
        if not fresh:
            break
    audit['listed'] = len(rows)
    # Give distinct employers a first read before several subsidiaries/roles of
    # one employer consume the request budget. Keep remaining notices for scope.
    counts = {}
    for row in rows:
        row['_rank'] = counts.get(row['keyword'], 0)
        counts[row['keyword']] = row['_rank'] + 1
    rows.sort(key=lambda row: (row['_rank'], row['employment_type'] != '정규직'))
    verified = []
    for row in rows[:MAX_DETAILS]:
        if monotonic() >= deadline:
            audit['errors'].append('time_budget')
            break
        audit['detail_attempts'] += 1
        source = fetch_source(row['url'])
        if not detail_matches(row, source, today):
            continue
        verified.append({k: v for k, v in row.items() if k != '_rank'} | {'source': source})
    audit['verified'] = len(verified)
    audit['status'] = 'ready' if verified else 'unavailable' if audit['errors'] else 'empty'
    return verified, audit


def prepare(stats, measure, today, *, deadline=None):
    notices, audit = discover(today, deadline=deadline)
    groups = {}
    for notice in notices:
        groups.setdefault(notice['keyword'], []).append(notice)
    measured = dict(stats)
    deadline = min(deadline if deadline is not None else float('inf'), monotonic() + 90)
    measurement_errors = []
    for keyword in list(groups)[:MAX_EMPLOYERS]:
        if deadline is not None and monotonic() >= deadline:
            measurement_errors.append('time_budget')
            break
        if not any(recruitment_sources.compact(row['keyword']) == recruitment_sources.compact(keyword) for row in measured.values()):
            try:
                measured.update(measure([keyword]))
            except (OSError, ValueError, RuntimeError):
                measurement_errors.append(keyword)
    matched = {recruitment_sources.compact(key): rows for key, rows in groups.items()}
    prepared, skipped = {}, []
    for key, row in measured.items():
        keyword = row['keyword']
        if not recruitment_sources.employer(keyword):
            prepared[key] = row  # Career guides keep their existing route.
            continue
        # Exact query only: a parent's broad demand is never assigned to a
        # local hospital, role, or an unmeasured qualification query.
        notices = matched.get(recruitment_sources.compact(keyword), [])
        if not notices:
            skipped.append(keyword)
            continue
        prepared[key] = {**row, 'recruitment_notices': notices[:3]}
    audit.update(measured_supported=sum(bool(row.get('recruitment_notices')) for row in prepared.values()),
                 unsupported_hiring_keywords=skipped, measurement_errors=measurement_errors)
    return prepared, audit
