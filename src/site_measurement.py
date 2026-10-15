"""Read-only measurements of the live published inventory; no editorial mutations."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from html import escape, unescape
import csv
import hashlib
import io
import json
import math
import re
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

SITE = 'https://trendpulse.blog'
PACIFIC = ZoneInfo('America/Los_Angeles')


def normalize_url(value):
    url = urlsplit(value)
    if (url.scheme != 'https' or url.netloc != 'trendpulse.blog' or url.query or url.fragment
            or not url.path.strip('/')):
        raise ValueError('Expected a canonical TrendPulse article URL')
    return re.sub(r'%[a-fA-F0-9]{2}', lambda m: m[0].upper(), value.rstrip('/')) + '/'


def utc_now():
    return datetime.now(timezone.utc)


def parse_time(value):
    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('Timestamp must include a timezone')
    return value


def fingerprint(posts):
    keys = [(p['post_id'], p['url'], p['modified_at']) for p in posts]
    return hashlib.sha256(json.dumps(sorted(keys)).encode()).hexdigest()


def fetch_inventory(session, *, ledger=(), max_pages=100, now=None):
    """GET only; strict pagination never reports a partial inventory as complete."""
    by_url = {}
    for row in ledger:
        try:
            by_url[normalize_url(row['url'])] = row
        except (ValueError, KeyError, TypeError):
            continue
    categories = {}
    try:
        response = session.get(SITE + '/wp-json/wp/v2/categories',
            params={'per_page':100,'_fields':'id,name'}, timeout=45, allow_redirects=False)
        if response.status_code == 200:
            categories = {x['id']:x['name'] for x in response.json()}
    except (Exception, SystemExit):
        pass  # Category availability never pretends the published inventory itself is empty.
    posts, seen_ids, seen_urls = [], set(), set()
    total, pages = None, None
    for page in range(1, max_pages + 1):
        response = session.get(SITE + '/wp-json/wp/v2/posts', params={
            'status': 'publish', 'per_page': 100, 'page': page, 'orderby': 'id', 'order': 'asc',
            '_fields': 'id,link,slug,status,title,date_gmt,modified_gmt,categories,content'},
            timeout=45, allow_redirects=False)
        if response.status_code != 200:
            raise RuntimeError('Published inventory request failed')
        batch = response.json()
        count, page_count = int(response.headers['X-WP-Total']), int(response.headers['X-WP-TotalPages'])
        if page == 1:
            total, pages = count, page_count
        if (count != total or page_count != pages or not isinstance(batch, list)
                or pages > max_pages or pages != (total + 99) // 100):
            raise ValueError('Unstable or invalid published inventory pagination')
        for post in batch:
            pid, url = post['id'], normalize_url(post['link'])
            if type(pid) is not int or pid <= 0 or post.get('status') != 'publish' or pid in seen_ids or url in seen_urls:
                raise ValueError('Invalid or duplicate published identity')
            seen_ids.add(pid); seen_urls.add(url)
            published, modified = post['date_gmt'] + '+00:00', post['modified_gmt'] + '+00:00'
            parse_time(published); parse_time(modified)
            html = post.get('content', {}).get('rendered', '')
            category = re.search(r'data-reader-category=["\']([^"\']+)', html)
            item = by_url.get(url, {})
            posts.append({'post_id': pid, 'url': url, 'slug': post['slug'],
                'title': unescape(re.sub(r'<[^>]*>', '', post['title']['rendered'])),
                'published_at': published, 'modified_at': modified,
                'category': unescape(category[1]) if category else item.get('category') or next((categories[i] for i in post.get('categories',[]) if i in categories),'미분류'),
                'category_ids': post.get('categories', []),
                'format': 'category-menu-v1' if 'wpab-menu-reader' in html else 'legacy',
                'keyword': item.get('keyword'),
                'selection_search_volume': item.get('monthly_search'),
                'selection_volume_engine': item.get('search_engine', 'unknown')})
        if page >= pages:
            break
    if len(posts) != total:
        raise ValueError('Published inventory was incomplete')
    return {'schema_version': 1, 'site': SITE, 'generated_at': (now or utc_now()).isoformat(),
            'complete': True, 'inventory_id': fingerprint(posts), 'posts': posts}


def validate_inventory(inventory):
    if inventory.get('site') != SITE or inventory.get('complete') is not True:
        raise ValueError('Complete authenticated inventory required')
    posts = inventory['posts']
    if len({p['post_id'] for p in posts}) != len(posts) or len({normalize_url(p['url']) for p in posts}) != len(posts):
        raise ValueError('Duplicate inventory')
    for post in posts:
        if normalize_url(post['url']) != post['url']:
            raise ValueError('Unnormalized inventory URL')
        parse_time(post['published_at']); parse_time(post['modified_at'])
    if inventory['inventory_id'] != fingerprint(posts):
        raise ValueError('Inventory fingerprint mismatch')


def windows(now):
    end = now.astimezone(PACIFIC).date() - timedelta(days=3)
    return {name: {'start': (stop-timedelta(days=days-1)).isoformat(), 'end': stop.isoformat()}
            for name, days, stop in [('7d', 7, end), ('28d', 28, end),
                                     ('previous28d', 28, end-timedelta(days=28))]}


def metrics(row):
    keys = ('clicks', 'impressions', 'ctr', 'position')
    if any(type(row.get(k)) not in (int, float) or not math.isfinite(row[k]) or row[k] < 0 for k in keys):
        raise ValueError('Invalid performance metrics')
    if row['ctr'] > 1:
        raise ValueError('Invalid CTR')
    return {k: row[k] for k in keys}


def collect_shard(inventory, query, inspect, *, shard=0, shards=4, cache=None, refresh=False,
                  now=None, on_progress=lambda value: None, workers=4, budget_seconds=480,
                  monotonic=time.monotonic):
    validate_inventory(inventory)
    if not 0 <= shard < shards or not 1 <= shards <= 16:
        raise ValueError('Invalid shard')
    now = now or utc_now(); cache = {} if cache is None else cache; periods = windows(now)
    posts = sorted(inventory['posts'], key=lambda p:p['post_id'])[shard::shards]
    report = {'schema_version': 1, 'inventory_id': inventory['inventory_id'], 'site': SITE,
              'generated_at': now.isoformat(), 'shard': shard, 'shards': shards,
              'complete': False, 'periods': periods, 'posts': []}
    on_progress(report)
    datasets = {}
    for name, period in periods.items():
        try:
            result = query(period['start'], period['end'], ['page'])
            if result.get('complete') is not True:
                raise ValueError('Truncated page totals')
            mapped = {}
            for row in result['rows']:
                try:
                    url = normalize_url(row['page'])
                except ValueError:
                    continue  # Other domains/archives are not our published articles.
                if url in mapped:
                    raise ValueError('Ambiguous page aggregation')
                mapped[url] = metrics(row)
            datasets[name] = {'status': 'reported', 'by_url': mapped}
        except (Exception, SystemExit):
            datasets[name] = {'status': 'unavailable', 'by_url': {}}
    try:
        period = periods['28d']
        details = query(period['start'], period['end'], ['page','query','device','country'])
        query_rows = details['rows']
        query_status = 'reported' if details['complete'] else 'truncated'
    except (Exception, SystemExit):
        query_rows, query_status = [], 'unavailable'
    grouped = {}
    for row in query_rows:
        try:
            url = normalize_url(row['page']); m = metrics(row)
            if any(not isinstance(row.get(k), str) for k in ('query','device','country')):
                raise ValueError('Missing segment')
            grouped.setdefault(url, []).append({**m, **{k:row[k] for k in ('query','device','country')}})
        except (ValueError, KeyError, TypeError):
            query_status = 'unavailable'; grouped = {}; break
    for post in posts:
        published = parse_time(post['published_at']).astimezone(PACIFIC).date()
        row = {**post, 'performance': {}, 'search_segments': {'status': query_status,
                'privacy_omissions_possible': True, 'rows': sorted(grouped.get(post['url'], []),
                    key=lambda r:-r['impressions'])[:50], 'display_limit': 50, 'display_truncated':len(grouped.get(post['url'],[])) > 50},
               'index': {'status':'unavailable', 'reason':'not_started'}}
        for name, period in periods.items():
            data = datasets[name]; found = data['by_url'].get(post['url'])
            after_end = published.isoformat() > period['end']
            row['performance'][name] = {**period, 'status': 'collecting' if after_end else
                data['status'] if data['status'] != 'reported' else 'reported' if found else 'no_reported_rows',
                'metrics': None if after_end else found,
                'full_window': published.isoformat() <= period['start']}
        report['posts'].append(row)
    on_progress(report)
    deadline = monotonic() + budget_seconds

    def inspect_one(row):
        old = cache.get(row['url'], {})
        try:
            age = (now-parse_time(old['checked_at'])).total_seconds()
            ttl = 7*86400 if old.get('verdict') == 'PASS' else 86400
            if (not refresh and old.get('status') == 'reported' and old.get('modified_at') == row['modified_at']
                    and 0 <= age < ttl):
                return row['url'], {**old, 'cached': True}
        except (KeyError, TypeError, ValueError):
            pass
        if monotonic() + 195 > deadline:
            return row['url'], {'status':'unavailable','reason':'time_budget'}
        try:
            result = inspect(row['url'])
            if result.get('error') or result.get('verdict') not in ('PASS','PARTIAL','FAIL','NEUTRAL'):
                raise ValueError('Inspection unavailable')
            return row['url'], {'status':'reported', 'checked_at':now.isoformat(),
                'modified_at':row['modified_at'], 'cached':False, **{k:result.get(k) for k in
                ('verdict','coverageState','lastCrawlTime','googleCanonical','userCanonical','robotsTxtState','indexingState')}}
        except (Exception, SystemExit):
            return row['url'], {'status':'unavailable','reason':'request_failed'}

    # Errors and incomplete shards still retain every article and completed inspection.
    lookup = {r['url']: r for r in report['posts']}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(inspect_one, row) for row in report['posts']]
        for future in as_completed(futures):
            url, result = future.result(); lookup[url]['index'] = result
            if result['status'] == 'reported':
                cache[url] = result
            on_progress(report)
    report['complete'] = True
    on_progress(report)
    return report


def validate_signals(signals):
    """Optional independently measured demand/behavior/revenue; never inferred from GSC."""
    if signals.get('site') != SITE or signals.get('schema_version') != 1:
        raise ValueError('Invalid external measurement file')
    result = {}
    for item in signals.get('posts', []):
        url = normalize_url(item['url'])
        if url in result:
            raise ValueError('Duplicate external signal')
        clean = {}
        for kind in ('demand','engagement','monetization'):
            value = item.get(kind)
            if value is None:
                continue
            if (not isinstance(value, dict) or value.get('status') != 'reported' or
                    not all(isinstance(value.get(k),str) and value[k] for k in
                            ('source','period_start','period_end','checked_at'))):
                raise ValueError('Measurement provenance required')
            parse_time(value['checked_at'])
            from datetime import date
            if date.fromisoformat(value['period_start']) > date.fromisoformat(value['period_end']):
                raise ValueError('Invalid signal period')
            allowed = {'demand':('monthly_searches',), 'engagement':('sessions','section_views','official_clicks','affiliate_clicks'),
                       'monetization':('revenue','cost')}[kind]
            if not any(k in value for k in allowed):
                raise ValueError('Measured values required')
            for key in allowed:
                if key in value and (type(value[key]) not in (int,float) or not math.isfinite(value[key]) or value[key] < 0):
                    raise ValueError('Invalid external measured value')
            if kind == 'demand' and (value.get('engine') not in ('google','naver') or not value.get('region')):
                raise ValueError('Search engine and region required')
            if kind == 'monetization' and not re.fullmatch('[A-Z]{3}',value.get('currency','')):
                raise ValueError('Revenue currency required')
            keys = set(allowed) | {'status','source','period_start','period_end','checked_at','engine','region','currency'}
            clean[kind] = {key:val for key,val in value.items() if key in keys}
        result[url] = clean
    return result


def merge_report(inventory, shards, *, signals=None):
    validate_inventory(inventory); external = validate_signals(signals) if signals else {}
    measured = {}; valid_shards = set(); expected = None; periods = None; errors = []
    for part in shards:
        if part.get('inventory_id') != inventory['inventory_id'] or part.get('site') != SITE:
            errors.append('inventory_mismatch'); continue
        if expected is None:
            expected, periods = part['shards'], part['periods']
        if part['shards'] != expected or part['periods'] != periods or part['shard'] in valid_shards:
            errors.append('shard_contract_mismatch'); continue
        ids = {p['post_id'] for p in sorted(inventory['posts'],key=lambda p:p['post_id'])[part['shard']::expected]}
        if any(r['post_id'] not in ids for r in part['posts']) or len({r['post_id'] for r in part['posts']}) != len(part['posts']):
            errors.append('shard_identity_mismatch'); continue
        if not part.get('complete'):
            errors.append('incomplete_shard')
        valid_shards.add(part['shard'])
        for row in part['posts']:
            measured[row['post_id']] = row
    rows = []
    for post in inventory['posts']:
        row = {**measured.get(post['post_id'], {}), **post}
        row.setdefault('index', {'status':'unavailable','reason':'missing_shard'})
        row.setdefault('performance', {})
        row.setdefault('search_segments', {'status':'unavailable','rows':[]})
        row['external'] = {kind:external.get(post['url'],{}).get(kind,{'status':'not_connected'})
                           for kind in ('demand','engagement','monetization')}
        reasons = []
        if row['index']['status'] != 'reported':
            reasons.append('index_unavailable')
        elif row['index'].get('verdict') != 'PASS':
            reasons.append('index_review')
        elif row['index'].get('googleCanonical'):
            try:
                if normalize_url(row['index']['googleCanonical']) != post['url']:
                    reasons.append('canonical_review')
            except ValueError:
                reasons.append('canonical_review')
        window = row['performance'].get('28d', {})
        data = window.get('metrics')
        if window.get('status') != 'reported' or not window.get('full_window') or not data or data['impressions'] < 100:
            reasons.append('performance_insufficient')
        else:
            if data['position'] > 10:
                reasons.append('ranking_review')
            if data['position'] <= 10 and data['clicks'] <= 2:
                reasons.append('ctr_review')
        if row['external']['demand'].get('engine') != 'google':
            reasons.append('google_demand_unmeasured')
        row['review_reasons'] = reasons; rows.append(row)
    return {'schema_version':1,'site':SITE,'inventory_id':inventory['inventory_id'],
            'generated_at':utc_now().isoformat(),'periods':periods,
            'inventory_complete':True,'collection_complete': len(valid_shards)==expected and not errors
                and all(r['index']['status']=='reported' and r['search_segments']['status']=='reported' and all(w['status'] != 'unavailable'
                    for w in r['performance'].values()) and r['performance'] for r in rows),
            'shards_received':sorted(valid_shards),'errors':errors,'posts':rows,
            'notes':['Review candidates are hypotheses, never deletion or automatic edits.',
                     '100 impressions / <=2 clicks are triage defaults, not universal CTR benchmarks.',
                     'Missing and private query rows do not establish zero demand.',
                     'Reader events require deployment and verified GA4 receipt; imports are optional.']}


def render_report(report):
    """Escaped static report; no external scripts, credentials, or hidden dashboards."""
    headers = ['ID','카테고리','글','색인','28일 노출','클릭','CTR','순위','상태','검토 사유','수요/행동/수익']
    output = io.StringIO(); writer = csv.writer(output); writer.writerow(headers)
    html_rows = []
    labels = {'index_unavailable':'색인 미확인','index_review':'색인 재확인','canonical_review':'표준 URL 확인',
              'performance_insufficient':'실적 표본/기간 부족','ranking_review':'순위 검토','ctr_review':'클릭 검토',
              'google_demand_unmeasured':'Google 수요 미측정'}
    for row in report['posts']:
        w = row['performance'].get('28d',{}); m = w.get('metrics') or {}
        external_parts = []
        for kind in ('demand','engagement','monetization'):
            value = row['external'][kind]
            if value['status'] != 'reported':
                external_parts.append(kind + ': ' + value['status'])
            else:
                numbers = ', '.join(f'{key}={value[key]}' for key in
                    ('monthly_searches','sessions','section_views','official_clicks','affiliate_clicks','revenue','cost','currency','engine','region') if key in value)
                external_parts.append(f"{kind}: {numbers} [{value['source']}, {value['period_start']}..{value['period_end']}]")
        external = ' / '.join(external_parts)
        values = [row['post_id'],row['category'],row['title'],row['index'].get('coverageState') or row['index']['status'],
                  m.get('impressions','—'),m.get('clicks','—'),f"{m['ctr']:.1%}" if 'ctr' in m else '—',
                  f"{m['position']:.1f}" if m.get('impressions',0) else '—',w.get('status','unavailable'),
                  ', '.join(labels[x] for x in row['review_reasons']),external]
        safe = ["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for v in values]
        writer.writerow(safe)
        cells=[escape(str(v)) for v in values];cells[2]=f'<a href="{escape(row["url"],quote=True)}">{cells[2]}</a>'
        html_rows.append('<tr>'+''.join('<td>'+c+'</td>' for c in cells)+'</tr>')
    html = '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>글별 측정 결과</title><style>body{font:16px/1.6 system-ui;margin:24px;color:#243047}table{border-collapse:collapse}th,td{padding:10px;border:1px solid #ddd;text-align:left}.scroll{overflow:auto}a{color:#354edb}</style><h1>글별 측정 결과</h1>'
    html += f'<p>공개 글 {len(report["posts"])}편 · 전체 수집 {"완료" if report["collection_complete"] else "일부 미완료"} · 미확인은 0점이 아닙니다.</p><p>기간: {escape(json.dumps(report["periods"],ensure_ascii=False))}</p>'
    html += '<p>검토 사유는 원인 확정이나 삭제 권고가 아닙니다. 수요/행동/수익 not_connected는 해당 자료 미연결입니다.</p><div class="scroll"><table><thead><tr>'+''.join('<th>'+escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join(html_rows)+'</tbody></table></div></html>'
    return output.getvalue(), html
