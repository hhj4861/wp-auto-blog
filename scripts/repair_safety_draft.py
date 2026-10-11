"""Apply two evidence-review corrections to one exact, backed-up draft."""
import hashlib
import json
import os
import requests

POST_ID = 1927
SLUG = 'industrial-safety-engineer-2026'
RAW_SHA = '8bb030de423fbc3c4222d65901f2db76bbbf9961332f73bbad26d6274ce57935'
OLD = '해당 과정 이수 후 동일·유사 직무분야 실무경력 2년 이상'
NEW = '동일·유사 직무분야의 산업기사 수준 기술훈련과정 이수 후, 응시 종목과 동일·유사 직무분야에서 실무경력 2년 이상'


def corrected(raw):
    if hashlib.sha256(raw.encode()).hexdigest() != RAW_SHA:
        raise ValueError('Draft differs from reviewed backup')
    if raw.count(OLD) != 1 or raw.count('원서접수:') != 6:
        raise ValueError('Expected exact reviewed fragments')
    return raw.replace(OLD, NEW).replace('원서접수:', '원서접수(휴일 제외):')


def repair(session):
    endpoint = f'https://trendpulse.blog/wp-json/wp/v2/posts/{POST_ID}'
    def read():
        response = session.get(endpoint, params={'context':'edit'}, timeout=45, allow_redirects=False)
        response.raise_for_status()
        return response.json()
    original = read()
    if (original.get('id'), original.get('slug'), original.get('status')) != (POST_ID, SLUG, 'draft'):
        raise ValueError('Exact draft identity required')
    fixed = corrected(original['content']['raw'])
    current = read()
    if current != original:
        raise ValueError('Draft changed during inspection')
    response = session.post(endpoint, json={'content':fixed}, timeout=45, allow_redirects=False)
    response.raise_for_status()
    saved = read()
    if saved['content']['raw'] != fixed or any(saved.get(k) != original.get(k) for k in
            ('id','slug','status','title','excerpt','meta','date_gmt','featured_media','categories','tags')):
        raise RuntimeError('Draft preservation verification failed')
    return {'post_id':POST_ID,'status':saved['status'],'verified':True}


if __name__ == '__main__':
    if os.environ['WP_GENERAL_URL'].rstrip('/') != 'https://trendpulse.blog' or os.environ['POC_POST_ID'] != str(POST_ID):
        raise ValueError('Unexpected site or post')
    session = requests.Session()
    session.auth = (os.environ['WP_GENERAL_USERNAME'], os.environ['WP_GENERAL_APP_PASSWORD'])
    session.headers['User-Agent'] = 'Mozilla/5.0 (TrendPulse reviewed draft correction)'
    print(json.dumps(repair(session)), flush=True)
