"""Bounded NAVER API HUB daily interest; ratios never become search counts."""
from datetime import date, datetime, timedelta, timezone
import math
import os
from time import monotonic
from zoneinfo import ZoneInfo

import requests

PROVIDER = 'naver_api_hub_daily_relative'
URL = 'https://naverapihub.apigw.ntruss.com/search-trend/v1/search'
KST = ZoneInfo('Asia/Seoul')
MAX_KEYWORDS = 120
MAX_CALLS = 24
MAX_SECONDS = 60
UNAVAILABLE = frozenset({'not_configured', 'budget_exhausted', 'authentication_failed',
    'rate_limited', 'http_error', 'network_error', 'invalid_response', 'insufficient_history',
    'stale_data', 'zero_baseline'})


def configured():
    return all(os.getenv(key, '').strip() for key in
               ('NAVER_API_HUB_CLIENT_ID', 'NAVER_API_HUB_CLIENT_SECRET'))


def unavailable(keyword, now, status):
    return {'provider': PROVIDER, 'keyword': keyword, 'checked_at': now.isoformat(),
            'status': status, 'unit': 'relative_index', 'qualified_rising': False, 'points': 0}


def analyze(keyword, points, now):
    """Use complete KST dates only; retain inputs so cached priority can be verified."""
    fallback = lambda status: unavailable(keyword, now, status)
    end = now.astimezone(KST).date() - timedelta(days=1)
    if not isinstance(points, list) or not points or len(points) > 15:
        return fallback('invalid_response')
    values = {}
    try:
        for point in points:
            day = date.fromisoformat(point['period'])
            value = point['ratio']
            if (day in values or day > end or day < end - timedelta(days=14)
                    or type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100):
                return fallback('invalid_response')
            values[day] = value
    except (KeyError, TypeError, ValueError):
        return fallback('invalid_response')
    latest = max(values)
    if (end - latest).days > 1:
        return fallback('stale_data')
    days = [latest - timedelta(days=i) for i in range(9, -1, -1)]
    if any(day not in values for day in days):
        return fallback('insufficient_history')
    samples = [values[day] for day in days]
    baseline = sum(samples[-8:-1]) / 7
    prior = sum(samples[:7]) / 7
    weekday = samples[-8]
    if min(baseline, prior, weekday) <= 0:
        return fallback('zero_baseline')
    growth = samples[-1] / baseline - 1
    recent = (sum(samples[-3:]) / 3) / prior - 1
    weekly = samples[-1] / weekday - 1
    rising_days = sum(value >= prior * 1.2 for value in samples[-3:])
    qualified = growth >= .3 and recent >= .2 and weekly >= .2 and rising_days >= 2
    # A low relative baseline is not a measured low search count. Bound its effect.
    score = (min(20, max(0, growth * 10)) + min(10, max(0, recent * 10))
             + min(10, max(0, weekly * 10)) + rising_days * 5 / 3) if qualified else 0
    return {**fallback('measured'), 'latest_period': latest.isoformat(),
        'lag_days': (now.astimezone(KST).date() - latest).days,
        'latest_vs_previous_7d': round(growth, 6), 'recent_3d_vs_previous_7d': round(recent, 6),
        'latest_vs_previous_weekday': round(weekly, 6), 'rising_days': rising_days,
        'qualified_rising': qualified, 'points': round(score, 2),
        'data': [{'period': day.isoformat(), 'ratio': values[day]} for day in sorted(values)]}


def valid(signal, keyword, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        checked = datetime.fromisoformat(signal['checked_at'])
        if (signal['provider'] != PROVIDER or signal['keyword'] != keyword
                or checked.tzinfo is None or not timedelta(0) <= now - checked <= timedelta(hours=24)
                or checked.astimezone(KST).date() != now.astimezone(KST).date()):
            return False
        if signal['status'] == 'measured':
            return signal == analyze(keyword, signal['data'], checked)
        return (signal['status'] in UNAVAILABLE
                and signal == unavailable(keyword, checked, signal['status']))
    except (KeyError, TypeError, ValueError):
        return False


def rising(signal):
    return isinstance(signal, dict) and signal.get('status') == 'measured' and signal.get('qualified_rising') is True


def rank(signal):
    return (int(rising(signal)), signal.get('points', 0) if rising(signal) else 0)


class Collector:
    """One selection's request/cache budget, shared by all replenishment rounds."""
    def __init__(self, now=None):
        self.now = now or datetime.now(timezone.utc)
        self.enabled = configured()
        self.cache = {}
        self.calls = 0
        self.elapsed = 0.0
        self.stop = None

    def collect(self, keywords):
        keywords = list(dict.fromkeys(keywords))
        if not self.enabled:
            return {key: unavailable(key, self.now, 'not_configured') for key in keywords}
        started = monotonic()
        pending = [key for key in keywords if key not in self.cache]
        for offset in range(0, len(pending), 5):
            batch = pending[offset:offset + 5]
            remaining = MAX_SECONDS - self.elapsed - (monotonic() - started)
            status = self.stop
            if self.calls >= MAX_CALLS or remaining <= 0:
                status = status or 'budget_exhausted'
            if status:
                for key in batch:
                    self.cache[key] = unavailable(key, self.now, status)
                continue
            end = self.now.astimezone(KST).date() - timedelta(days=1)
            body = {'startDate': (end - timedelta(days=14)).isoformat(), 'endDate': end.isoformat(),
                    'timeUnit': 'date', 'keywordGroups': [
                        {'groupName': f'k{i}', 'keywords': [key]} for i, key in enumerate(batch)]}
            self.calls += 1
            try:
                response = requests.post(URL, json=body, headers={
                    'X-NCP-APIGW-API-KEY-ID': os.environ['NAVER_API_HUB_CLIENT_ID'],
                    'X-NCP-APIGW-API-KEY': os.environ['NAVER_API_HUB_CLIENT_SECRET'],
                    'Content-Type': 'application/json'}, timeout=min(4, max(.1, remaining / 2)),
                    allow_redirects=False)
                code = response.status_code
                if code != 200:
                    status = ('authentication_failed' if code in (401, 403) else
                              'rate_limited' if code == 429 else 'http_error')
                    if code in (401, 403, 429):
                        self.stop = status
                else:
                    payload = response.json()
                    rows = payload.get('results')
                    if (payload.get('timeUnit') != 'date' or payload.get('startDate') != body['startDate']
                            or payload.get('endDate') != body['endDate'] or not isinstance(rows, list)
                            or len(rows) != len(batch)):
                        raise ValueError('invalid_response')
                    mapped = {row['title']: row for row in rows}
                    if len(mapped) != len(batch):
                        raise ValueError('invalid_response')
                    for i, key in enumerate(batch):
                        row = mapped[f'k{i}']
                        if row.get('keywords') != [key]:
                            raise ValueError('invalid_response')
                    for i, key in enumerate(batch):
                        self.cache[key] = analyze(key, mapped[f'k{i}']['data'], self.now)
                    continue
            except requests.RequestException:
                status = 'network_error'
            except (ValueError, TypeError, KeyError, AttributeError):
                status = 'invalid_response'
            for key in batch:
                self.cache[key] = unavailable(key, self.now, status)
        self.elapsed += monotonic() - started
        return {key: self.cache[key] for key in keywords}

    def summary(self):
        counts = {}
        for signal in self.cache.values():
            counts[signal['status']] = counts.get(signal['status'], 0) + 1
        return {'provider': PROVIDER, 'status': 'checked' if self.enabled else 'not_configured',
                'calls': self.calls, 'checked_keywords': len(self.cache), 'outcomes': counts,
                'qualified_rising': sum(rising(x) for x in self.cache.values()),
                'unit': 'relative_index', 'today_excluded': True}
