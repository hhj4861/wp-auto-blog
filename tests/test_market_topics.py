from datetime import datetime, timezone, timedelta
import json
from unittest.mock import Mock

import pytest
import yaml

from src import market_topics as market


def evidence(url='https://example.go.kr/info'):
    return {'url': url, 'original_url': url, 'excerpt': '공식 시험 준비물 안내',
            'title': '시험 준비물', 'checked_on': datetime.now(timezone(timedelta(hours=9))).date().isoformat(),
            'sha256': 'test'}


def organic(url='https://independent.example/info'):
    from urllib.parse import urlsplit
    return {'url': url, 'domain': urlsplit(url).hostname,
            'title': '시험 준비물', 'snippet': '시험 응시 준비 안내'}


def analysis(keyword='시험준비물', category='취업', **extra):
    return {'supported': True, 'category': category, 'topic': keyword + ' 확인 방법',
            'intent': '무엇을 준비하나', 'gap': '공식 준비물 체크리스트',
            'source_index': 0, 'serp_indices': [0], 'valid_until': None, **extra}


@pytest.fixture(autouse=True)
def isolated_market_history(tmp_path, monkeypatch):
    monkeypatch.setattr(market, 'ROOT', tmp_path)
    monkeypatch.setattr(market, 'LEDGER', tmp_path / 'data/ledger.json')
    monkeypatch.setattr('requests.sessions.Session.request',
                        Mock(side_effect=AssertionError('Live HTTP is disabled in market topic tests')))
    monkeypatch.setattr('urllib.request.urlopen',
                        Mock(side_effect=AssertionError('Live HTTP is disabled in market topic tests')))


def candidate(category='취업', **extra):
    return {'source': market.SOURCE, 'category': category, 'status': 'pending',
            'selected_at': datetime.now(timezone.utc).isoformat(), 'monthly_search': 1200,
            'source_url': 'https://example.go.kr/info', 'organic_domains': ['blog.example'],
            'topic': '시험 준비물 확인 방법', 'keyword': '시험준비물', 'keywords': ['시험준비물'],
            'score': 50, 'selection_version': market.PROCESS_VERSION,
            'intent': '무엇을 준비하나', 'gap': '공식 준비물 체크리스트',
            'verified_sources': [evidence()], 'organic_results': [organic()],
            'intent_results': [organic()['url']], **extra}


def test_category_freshness_and_unknown_evidence():
    row = candidate()
    assert market.fresh_market_item(row, '취업')
    assert not market.fresh_market_item(row, '건강')
    assert not market.fresh_market_item(candidate(source='legacy'), '취업')
    assert not market.fresh_market_item(candidate(monthly_search=0), '취업')
    assert not market.fresh_market_item(candidate(organic_domains=[]), '취업')
    assert not market.fresh_market_item(candidate(selected_at=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()), '취업')


def test_enqueue_keeps_other_categories_and_does_not_fallback():
    health = candidate('건강')
    legacy = {'category': '취업', 'status': 'pending', 'topic': 'old'}
    old = candidate()
    queue = [health, legacy, old]
    with pytest.raises(RuntimeError):
        market.enqueue_report(queue, {'category': '취업', 'selected': []})
    assert old['status'] == 'pending'
    market.enqueue_report(queue, {'category': '취업', 'selected': [candidate()]})
    assert old['status'] == 'superseded'
    assert health['status'] == legacy['status'] == 'pending'


def test_inventory_failure_does_not_mean_unique(monkeypatch):
    for key, value in {'WP_GENERAL_URL':'https://trendpulse.blog', 'WP_GENERAL_USERNAME':'u', 'WP_GENERAL_APP_PASSWORD':'p'}.items():
        monkeypatch.setenv(key, value)
    response = Mock()
    response.raise_for_status.side_effect = RuntimeError('unavailable')
    monkeypatch.setattr(market.requests, 'get', lambda *a, **k: response)
    with pytest.raises(RuntimeError):
        market.existing_titles()


def test_selection_requires_measured_keyword_source_and_serp(monkeypatch):
    proposal = {'keyword': '시험준비물', 'topic': '시험준비물 확인 방법', 'category': '취업',
                'intent': '무엇을 준비하나', 'gap': '준비물 표', 'source_url': 'https://example.go.kr/info'}
    monkeypatch.setattr(market, 'fetch_trend_change', lambda *a: None)
    responses = iter([{'candidates':[proposal]}, analysis()])
    monkeypatch.setattr(market, 'ask', lambda *a, **k: next(responses))
    monkeypatch.setattr(market, 'demand_candidates', lambda seeds: {'시험준비물':{'keyword':'시험준비물','monthly':1200,'comp':'높음'}})
    monkeypatch.setattr(market, 'fetch_source', lambda *a: evidence())
    monkeypatch.setattr(market, 'official_search_urls', lambda _: [proposal['source_url']])
    monkeypatch.setattr(market, 'search_results', lambda *a: ('google_custom_search', [organic(), organic(proposal['source_url'])]))
    result = market.select_category('취업', titles=[])
    assert result['selected'][0]['monthly_search'] == 1200
    assert result['selected'][0]['advertising_competition'] == '높음' # not SEO rejection
    assert result['selected'][0]['trend_growth'] is None


def test_no_credentials_or_competition_cannot_pass(monkeypatch):
    monkeypatch.delenv('NAVER_AD_API_KEY', raising=False)
    with pytest.raises(RuntimeError):
        market.demand_candidates(['취업'])
    with pytest.raises(ValueError):
        market.score_candidate(100000, [], '취업')
    assert market.duplicate('건강 검진', '새로운 제목', ['2026 건강검진 대상'])


def test_analysis_uses_subscription_and_retries_invalid_json(monkeypatch):
    from src import codex_client
    client = Mock()
    client.generate.side_effect = ['{"incomplete":', '{"candidates": []}']
    factory = Mock(return_value=client)
    monkeypatch.setattr(codex_client, 'CodexSubscriptionClient', factory)
    monkeypatch.setenv('BLOG_CODEX_HOME', '/tmp/dedicated-test-home')
    monkeypatch.delenv('GOOGLE_AI_API_KEY', raising=False)
    assert market.ask('후보 분석') == {'candidates': []}
    assert factory.call_args.kwargs['home'] == '/tmp/dedicated-test-home'
    assert client.generate.call_count == 2


def test_source_search_reads_full_page_and_rejects_unsupported(monkeypatch):
    official = evidence('https://real.go.kr/info')
    monkeypatch.setattr(market, 'official_search_urls', lambda _: [official['url']])
    monkeypatch.setattr(market, 'fetch_source', lambda url: official if url == official['url'] else None)
    monkeypatch.setattr(market, 'ask', lambda prompt: analysis('자격증'))
    sources = market.candidate_sources('자격증', [organic('https://missing.or.kr/')])
    assert sources == [official]
    item, reason = market.topic_from_evidence('자격증', '취업', '2026-09-09', [organic()], sources)
    assert reason is None
    assert item['verified_sources'] == [official]
    monkeypatch.setattr(market, 'ask', lambda prompt: {'supported': False})
    assert market.topic_from_evidence('자격증', '취업', '2026-09-09', [organic()], sources)[0] is None


def test_official_search_excludes_nonofficial_and_decodes_redirects(monkeypatch):
    from src import market_search
    monkeypatch.delenv('GOOGLE_SEARCH_API_KEY', raising=False)
    response = Mock(url='https://html.duckduckgo.com/html/', text='''
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Freal.go.kr%2Finfo">정부</a>
      <a class="result__a" href="https://blog.example/info">블로그</a>''')
    monkeypatch.setattr(market_search.requests, 'get', lambda *a, **k: response)
    assert market.official_search_urls('시험') == ['https://real.go.kr/info']


def test_workflow_selects_before_existing_category_pipeline():
    from pathlib import Path
    workflow = yaml.safe_load(Path('.github/workflows/auto-post.yml').read_text())
    step = next(s for s in workflow['jobs']['post-queue']['steps'] if s.get('name', '').startswith('Run pipeline'))
    command = step['run']
    assert command.index('select_blog_keywords.py') < command.index('python -m src.main')
    assert '--category "$CAT" --enqueue --reuse' in command
    assert 'BLOG_REQUIRE_MARKET_TOPIC=1' in command
    selector = Path('.github/workflows/blog-keyword-select.yml').read_text()
    assert "inputs.top_n || '2'" in selector
    assert 'scaffold_post.py' not in selector


def test_trend_requires_complete_nonzero_baseline():
    assert market.trend_change([10]*7+[20]*7) == 1.0
    assert market.trend_change([0]*7+[20]*7) is None
    assert market.trend_change([10]*5) is None
    assert not market.fresh_market_item(candidate(valid_until='2000-01-01'), '취업')


def test_year_spacing_and_deleted_posts_remain_duplicates(tmp_path, monkeypatch):
    ledger = tmp_path / 'ledger.json'
    monkeypatch.setattr(market, 'LEDGER', ledger)
    item = candidate(keyword='2026 GSAT 일정', topic='2026 GSAT 일정 확인')
    market.record_published_keyword(item, 12, 'https://trendpulse.blog/old')
    market.record_published_keyword(item, 12, 'https://trendpulse.blog/old')
    import json
    assert len(json.loads(ledger.read_text())) == 1
    assert market.duplicate('2027 gsat일정', '새 제목', market.historical_terms())


def test_cli_empty_top_n_and_category_enqueue(tmp_path, monkeypatch):
    import json
    import scripts.select_blog_keywords as cli
    data = tmp_path / 'data'
    data.mkdir()
    queue_path = data / 'topic_queue_general.json'
    legacy = {'topic': 'old health topic', 'category': '건강', 'status': 'pending'}
    queue_path.write_text(json.dumps([legacy]))
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    monkeypatch.setattr(cli, 'REPORT', data / 'report.json')
    monkeypatch.setattr(cli, 'existing_titles', lambda: [])
    monkeypatch.setenv('SELECT_TOP_N', '')
    monkeypatch.setattr('sys.argv', ['select', '--category', '취업', '--enqueue'])
    calls = []
    def select(category, top_n, titles):
        calls.append((category, top_n))
        return {'category':category, 'selected':[candidate()]}
    monkeypatch.setattr(cli, 'select_category', select)
    assert cli.main() == 0
    assert calls == [('취업', 2)]
    queued = json.loads(queue_path.read_text())
    assert queued[0] == legacy
    assert market.fresh_market_item(queued[1], '취업')
    monkeypatch.setattr(cli, 'select_category', lambda *a: {'category':'취업','selected':[]})
    assert cli.main() == 1
    assert json.loads(queue_path.read_text()) == queued


def test_pool_keeps_measured_longtails_and_excludes_keyword_variants():
    stats = {f'브랜드이름{i}': {'keyword': f'브랜드이름{i}', 'monthly': 100000 - i}
             for i in range(80)}
    stats['환급서류'] = {'keyword': '환급서류', 'monthly': 900}
    stats['2027 GSAT일정'] = {'keyword': '2027 GSAT일정', 'monthly': 5000}
    pool = market.candidate_pool(stats, ['2026 ＧＳＡＴ&nbsp;일정 안내'])
    assert pool[0]['keyword'] == '환급서류'
    assert not any('GSAT' in row['keyword'] for row in pool)
    assert market.score_candidate(900, ['blog.example'], '환급서류') > market.score_candidate(
        500000, ['example.go.kr'] * 8 + ['blog.example'] * 2, '거대키워드')


def test_failed_sources_and_competitive_heads_trigger_next_measured_candidate(monkeypatch):
    stats = {key: {'keyword': key, 'monthly': volume} for key, volume in
             [('거대키워드', 100000), ('서류준비', 5000), ('환급서류', 1500)]}
    monkeypatch.setattr(market, 'demand_candidates', lambda _: stats)
    monkeypatch.setattr(market, 'fetch_trend_change', lambda _: None)
    monkeypatch.setattr(market, 'candidate_sources', lambda key, _: [] if key == '서류준비' else [evidence()])
    monkeypatch.setattr(market, 'research_official_sources', lambda *args: ([], None))
    def search(key):
        return 'google_custom_search', [organic('https://example.go.kr/info') if key == '거대키워드' else organic()]
    monkeypatch.setattr(market, 'search_results', search)
    prompts = []
    responses = iter([{'candidates': [{'keyword': '거대키워드'}, {'keyword': '서류준비'}]},
                      {'candidates': [{'keyword': '환급서류'}]}, analysis('환급서류', '생활정보')])
    def ask(prompt):
        prompts.append(prompt)
        return next(responses)
    monkeypatch.setattr(market, 'ask', ask)
    report = market.select_category('생활정보', 1, titles=[])
    assert report['research_rounds'] == 2
    assert report['evaluated_candidates'] == 3
    assert report['selected'][0]['keyword'] == '환급서류'
    assert report['selected'][0]['score_components']['trend'] == 0
    assert report['selected'][0]['verified_sources'] == [evidence()]
    assert '공식 시험 준비물 안내' in prompts[-1] and 'independent.example' in prompts[-1]
    assert len(report['rejected']) == 2


@pytest.mark.parametrize('change', [
    {'source_index': True}, {'source_index': 99}, {'serp_indices': []},
    {'serp_indices': [99]}, {'category': '건강'}, {'topic': '무관한 제목'},
    {'valid_until': '2000-01-01'}, {'gap': ''}, {'supported': 'true'},
])
def test_article_plan_rejects_unverified_or_wrong_intent(monkeypatch, change):
    monkeypatch.setattr(market, 'ask', lambda _: analysis(**change))
    item, reason = market.topic_from_evidence('시험준비물', '취업', '2026-09-09', [organic()], [evidence()])
    assert item is None and reason


def test_old_reports_and_incomplete_new_reports_cannot_publish():
    assert not market.fresh_market_item(candidate(selection_version=1), '취업')
    assert not market.fresh_market_item(candidate(verified_sources=[]), '취업')
    assert not market.fresh_market_item(candidate(intent_results=[]), '취업')
    assert not market.fresh_market_item(candidate(score=float('nan')), '취업')


def test_completed_queue_and_renamed_post_keyword_remain_reserved(tmp_path, monkeypatch):
    import json
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'topic_queue_general.json').write_text(json.dumps([
        {'keyword': 'GSAT일정', 'topic': '이름이 바뀐 글', 'status': 'completed'},
        {'keyword': '새로운서류', 'status': 'pending'}]))
    assert market.duplicate('2027 gsat 일정', '새로운 제목', market.historical_terms())
    assert not market.duplicate('새로운서류', '새로운 제목', market.historical_terms())
    for key, value in {'WP_GENERAL_URL':'https://trendpulse.blog', 'WP_GENERAL_USERNAME':'u',
                       'WP_GENERAL_APP_PASSWORD':'p'}.items():
        monkeypatch.setenv(key, value)
    response = Mock(headers={'X-WP-TotalPages': '1'})
    response.json.return_value = [{'title': {'rendered': '완전히 바꾼 제목'},
                                   'meta': {'_yoast_wpseo_focuskw': '건강 검진'}}]
    monkeypatch.setattr(market.requests, 'get', lambda *a, **kw: response)
    assert market.duplicate('2027 건강검진', '새 제목', market.existing_titles())


def test_all_categories_reserve_selected_keywords_from_other_categories(tmp_path, monkeypatch):
    import scripts.select_blog_keywords as cli
    monkeypatch.setattr(cli, 'REPORT', tmp_path / 'report.json')
    monkeypatch.setattr(cli, 'existing_titles', lambda: [])
    monkeypatch.setattr('sys.argv', ['select', '--category', 'all'])
    seen = []
    def select(category, top_n, titles):
        seen.append(list(titles))
        return {'category': category, 'selected': [candidate(category, keyword=category + '서류')]}
    monkeypatch.setattr(cli, 'select_category', select)
    assert cli.main() == 0
    assert '취업서류' in seen[1]
    assert '생활정보서류' in seen[2]


@pytest.fixture
def market_pipeline(mock_env_vars, monkeypatch, tmp_path):
    from src.pipeline import BlogPipeline, PipelineConfig
    from src.content_generator import GeneratedContent, ContentType
    from src.wordpress_client import CreatedPost, PostStatus
    from src import pipeline as module
    monkeypatch.setattr(module, 'POST_REGISTRY_DIR', tmp_path / 'data')
    pipeline = BlogPipeline(PipelineConfig(mode='general', category='취업', auto_publish=True,
                                           use_llm_topics=False))
    pipeline.content_generator = Mock()
    pipeline.content_generator.generate.return_value = GeneratedContent(
        title='시험준비물 확인 방법', html='<h2>시험준비물</h2><p>공식 안내</p>',
        meta_description='공식 준비물 안내', keywords=['시험준비물'], word_count=1000,
        content_type=ContentType.GUIDE, focus_keyphrase='시험 준비물', sources=[evidence()])
    pipeline.trend_detector = Mock()
    pipeline.wp_client = Mock()
    pipeline.wp_client.create_post.return_value = CreatedPost(
        123, 'https://trendpulse.blog/checklist/', '시험준비물 확인 방법', PostStatus.PUBLISH)
    monkeypatch.setattr(module, 'evaluate_keyword', lambda *a: {'verdict': 'go', 'reason': 'measured'})
    monkeypatch.setattr(module, 'check_quality', lambda **kw: [])
    monkeypatch.setattr(module, 'editorial_checks', lambda *a: [])
    monkeypatch.setattr(module, 'validate_identity', lambda **kw: [])
    monkeypatch.setattr(module, 'format_general_article', lambda html, **kw: html)
    monkeypatch.setattr(module, 'ping_urls', lambda *a: None)
    monkeypatch.setattr('src.editorial_thumbnail.create_editorial_thumbnail', lambda *a: Mock())
    monkeypatch.setattr(pipeline, '_get_related_posts', lambda **kw: [])
    monkeypatch.setattr(market, 'existing_titles', lambda: market.historical_terms())
    return pipeline


def test_selection_to_scheduled_publication_carries_brief_and_never_reposts(tmp_path, monkeypatch, market_pipeline):
    """Exercise the real selector, report, queue, CLI, pipeline and durable ledger.

    Paid/search providers, writing, quality review and WordPress are test doubles.
    """
    import json
    from src import main as main_module
    from scripts import select_blog_keywords as cli
    data = tmp_path / 'data'
    data.mkdir()
    queue_path = data / 'topic_queue_general.json'
    queue_path.write_text('[]')
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    monkeypatch.setattr(cli, 'REPORT', data / 'report.json')
    monkeypatch.setattr(cli, 'load_dotenv', lambda: None)
    monkeypatch.setattr(cli, 'existing_titles', lambda: market.historical_terms())
    monkeypatch.setenv('SELECT_TOP_N', '1')
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {'시험준비물': {'keyword': '시험준비물', 'monthly': 1200}})
    monkeypatch.setattr(market, 'search_results', lambda _: ('google_custom_search', [organic()]))
    monkeypatch.setattr(market, 'official_search_urls', lambda _: [evidence()['url']])
    monkeypatch.setattr(market, 'fetch_source', lambda _: evidence())
    monkeypatch.setattr(market, 'fetch_trend_change', lambda _: None)
    responses = iter([{'candidates': [{'keyword': '시험준비물'}]}, analysis()])
    monkeypatch.setattr(market, 'ask', lambda _: next(responses))
    monkeypatch.setattr('sys.argv', ['select', '--category', '취업', '--enqueue'])
    assert cli.main() == 0
    queued = json.loads(queue_path.read_text())[0]
    assert queued['verified_sources'] == [evidence()]

    monkeypatch.setattr(main_module, '__file__', str(tmp_path / 'src/main.py'))
    monkeypatch.setattr(main_module, 'load_dotenv', lambda: None)
    monkeypatch.setattr(main_module, 'setup_logging', lambda **kw: None)
    monkeypatch.setattr(main_module, 'BlogPipeline', lambda *a, **kw: market_pipeline)
    monkeypatch.setenv('BLOG_REQUIRE_MARKET_TOPIC', '1')
    monkeypatch.setattr('sys.argv', ['main', '--mode', 'general', '--from-queue', '--auto-publish', '--category', '취업'])
    assert main_module.main() == 0
    market_pipeline.wp_client.create_post.assert_called_once()
    passed = market_pipeline.content_generator.generate.call_args.kwargs
    assert passed['market_brief']['gap'] == analysis()['gap']
    assert passed['market_brief']['verified_sources'] == [evidence()]
    assert json.loads(queue_path.read_text())[0]['status'] == 'completed'
    assert json.loads(market.LEDGER.read_text())[0]['post_id'] == 123

    # Even a deleted WordPress post and a renamed title cannot re-admit its keyword.
    report = market.select_category
    with pytest.raises(RuntimeError, match='No uncovered measured candidates in this category'):
        report('취업', 1)
    again = market_pipeline.run_single(queued['topic'], queued['keywords'], '취업', market_brief=queued)
    assert not again.success and 'Duplicate' in again.error
    market_pipeline.wp_client.create_post.assert_called_once()


@pytest.mark.parametrize('failure', ['keyword_changed', 'concurrent_post', 'source_expired'])
def test_market_publication_rechecks_keyword_and_history(market_pipeline, monkeypatch, failure):
    item = candidate()
    if failure == 'keyword_changed':
        market_pipeline.content_generator.generate.return_value.focus_keyphrase = '전혀다른키워드'
    elif failure == 'concurrent_post':
        monkeypatch.setattr(market, 'existing_titles', Mock(side_effect=[[], ['시험 준비물 안내']]))
    else:
        monkeypatch.setattr(market, 'fresh_market_item', Mock(side_effect=[True, False]))
    result = market_pipeline.run_single(item['topic'], item['keywords'], '취업', market_brief=item)
    assert not result.success
    market_pipeline.wp_client.create_post.assert_not_called()
    assert not market.LEDGER.exists()


def test_published_history_survives_failure_after_wordpress_write(market_pipeline, monkeypatch):
    item = candidate()
    monkeypatch.setattr('src.pipeline.ping_urls', Mock(side_effect=RuntimeError('ping failed')))
    result = market_pipeline.run_single(item['topic'], item['keywords'], '취업', market_brief=item)
    assert not result.success
    assert market.duplicate(item['keyword'], '새 제목', market.historical_terms())


def test_held_draft_is_reserved_without_claiming_publication(market_pipeline, monkeypatch):
    from src.wordpress_client import PostStatus
    item = candidate()
    monkeypatch.setattr('src.pipeline.check_quality', lambda **kw: ['review issue'])
    market_pipeline.wp_client.create_post.return_value.status = PostStatus.DRAFT
    result = market_pipeline.run_single(item['topic'], item['keywords'], '취업', market_brief=item)
    assert result.success and result.post.status == PostStatus.DRAFT
    assert not market.LEDGER.exists()
    assert market.duplicate(item['keyword'], item['topic'], market.historical_terms())


@pytest.mark.parametrize('available', [True, False])
def test_writer_rereads_selected_source_and_uses_the_brief(mock_env_vars, monkeypatch, available):
    from src import content_generator as module
    generator = module.ContentGenerator(module.ContentConfig(language='ko'))
    item = candidate()
    current_source = evidence()
    current_source['excerpt'] = '작성 시점에 갱신된 공식 안내'
    fetch = Mock(return_value=current_source if available else None)
    monkeypatch.setattr(module, 'fetch_source', fetch)
    monkeypatch.delenv('BLOG_OFFICIAL_SOURCE_URLS', raising=False)
    grounding = Mock(side_effect=AssertionError('The selected source must be used'))
    monkeypatch.setattr(generator, 'research_with_grounding', grounding)
    writer = Mock(return_value='---SEO-META---\nFOCUS_KEYPHRASE: 시험준비물\nMETA_DESCRIPTION: 공식 준비물 안내\n'
                   '---CONTENT---\n<section id="quick-answer">준비물 안내</section><h1>시험준비물 확인 방법</h1>'
                   '<h2>준비물</h2><p>본문</p>')
    monkeypatch.setattr(generator, '_call_llm', writer)
    monkeypatch.setattr(module, 'review_evidence', lambda *a: [])
    if available:
        content = generator.generate(item['topic'], item['keywords'], module.ContentType.GUIDE,
                                     category='취업', market_brief=item)
        assert content.sources == [current_source]
        prompt = writer.call_args_list[0].args[0]
        assert item['intent'] in prompt and item['gap'] in prompt
        assert current_source['excerpt'] in prompt
    else:
        with pytest.raises(RuntimeError, match='no longer accessible'):
            generator.generate(item['topic'], item['keywords'], module.ContentType.GUIDE,
                               category='취업', market_brief=item)
        writer.assert_not_called()
    fetch.assert_called_once_with(item['source_url'])
    grounding.assert_not_called()


def web_evidence(url='https://example.go.kr/info', origin='native_open', **extra):
    return {**evidence(url), 'locator_origin': origin, **extra}


def web_research_evidence(*sources):
    return {'provider': 'codex_web', 'searched': True,
            'locators': [{'url': source['original_url'], 'origin': source['locator_origin']}
                         for source in sources]}


def web_candidate(origin='native_open', **extra):
    source = web_evidence(origin=origin)
    return candidate(evidence_mode='official_pages', organic_provider=None,
                     organic_domains=[], organic_results=[], dominant_result_ratio=None,
                     verified_sources=[source], research_evidence=web_research_evidence(source),
                     score_components={'demand': 24.63, 'organic_opportunity': 0,
                                       'specificity': 15, 'trend': 0},
                     intent_results=[source['url']], **extra)


def test_native_research_requires_observed_search_and_refetched_official_pages(monkeypatch):
    from src import codex_client
    source = evidence()
    client = Mock()
    client.research.return_value = {'text': 'https://invented.go.kr/info', 'searched': True,
        'opened_urls': ['https://blog.example/post', 'https://missing.go.kr/page', source['url'], source['url']]}
    monkeypatch.setattr(codex_client, 'CodexSubscriptionClient', Mock(return_value=client))
    fetch = Mock(side_effect=lambda url: source if url == source['url'] else None)
    monkeypatch.setattr(market, 'fetch_source', fetch)
    sources, trace = market.research_official_sources('시험준비물', '취업', '2026-09-10')
    assert sources == [{**source, 'locator_origin': 'native_open'}]
    assert trace['searched'] is True and trace['provider'] == 'codex_web'
    assert trace['locators'] == [
        {'url': 'https://missing.go.kr/page', 'origin': 'native_open'},
        {'url': source['url'], 'origin': 'native_open'}]
    assert [call.args[0] for call in fetch.call_args_list] == ['https://missing.go.kr/page', source['url']]
    client.research.return_value['searched'] = False
    fetch.reset_mock()
    assert market.research_official_sources('시험준비물', '취업', '2026-09-10') == ([], None)
    fetch.assert_not_called()


def test_source_locators_filter_unverified_proposals_and_preserve_native_origin():
    native = 'https://example.go.kr/info'
    reported = 'https://second.go.kr/info'
    trace = {'searched': True, 'opened_urls': [native], 'text': json.dumps({
        'candidate_urls': [native, reported, 'http://example.go.kr/info',
                           'https://user:secret@example.go.kr/info', 'https://blog.example/post',
                           'turn0search0', None, {'url': reported}]})}
    assert market.research_source_locators(trace) == [
        {'url': native, 'origin': 'native_open'},
        {'url': reported, 'origin': 'model_reported_locator'}]


@pytest.mark.parametrize('message', [
    'Official source: https://example.go.kr/info',
    '{"candidate_urls":"https://example.go.kr/info"}',
    '["https://example.go.kr/info"]',
    '{"candidate_urls":',
])
def test_unstructured_final_message_does_not_become_source_evidence(message):
    assert market.research_source_locators({'searched': True, 'opened_urls': [], 'text': message}) == []


def test_model_reported_locator_requires_observed_search_before_fetch(monkeypatch):
    from src import codex_client
    client = Mock()
    client.research.return_value = {
        'searched': False, 'opened_urls': [],
        'text': json.dumps({'candidate_urls': ['https://example.go.kr/info'], 'searched': True})}
    monkeypatch.setattr(codex_client, 'CodexSubscriptionClient', Mock(return_value=client))
    fetch = Mock()
    monkeypatch.setattr(market, 'fetch_source', fetch)
    assert market.research_source_locators(client.research.return_value) == []
    assert market.research_official_sources('시험준비물', '취업', '2026-09-10') == ([], None)
    fetch.assert_not_called()


@pytest.mark.parametrize('fetchable,reason', [
    (False, 'no accessible official source supports topic'),
    (True, 'search intent or official evidence does not support an article'),
])
def test_model_reported_locator_cannot_replace_accessible_relevant_body(monkeypatch, fetchable, reason):
    from src import codex_client
    source = evidence()
    source['excerpt'] = '이 자료는 시험 준비와 무관한 기관 연혁 안내입니다.'
    client = Mock()
    client.research.return_value = {
        'searched': True, 'opened_urls': [],
        'text': json.dumps({'candidate_urls': [source['url']],
                            'supported': True, 'excerpt': 'invented source support'})}
    monkeypatch.setattr(codex_client, 'CodexSubscriptionClient', Mock(return_value=client))
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {
        '시험준비물': {'keyword': '시험준비물', 'monthly': 1200}})
    monkeypatch.setattr(market, 'search_results', lambda _: ('duckduckgo_proxy', []))
    fetch = Mock(return_value=source if fetchable else None)
    monkeypatch.setattr(market, 'fetch_source', fetch)
    analyze = Mock(side_effect=[{'candidates': [{'keyword': '시험준비물'}]}, {'supported': False}])
    monkeypatch.setattr(market, 'ask', analyze)
    report = market.select_category('취업', 1, titles=[])
    fetch.assert_called_once_with(source['url'])
    assert report['selected'] == []
    assert report['rejected'] == [{'keyword': '시험준비물', 'reason': reason}]
    assert analyze.call_count == (2 if fetchable else 1)
    if fetchable:
        prompt = analyze.call_args.args[0]
        assert source['excerpt'] in prompt and 'invented source support' not in prompt


@pytest.mark.parametrize('origin', ['native_open', 'model_reported_locator'])
def test_search_outage_uses_verified_longtail_without_invented_competition(monkeypatch, origin):
    from src import codex_client
    source = evidence()
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {
        key: {'keyword': key, 'monthly': volume} for key, volume in
        [('거대신청방법', 60000), ('시험브랜드', 1200), ('시험준비물', 1200)]})
    responses = iter([{'candidates': [{'keyword': key} for key in ['거대신청방법', '시험브랜드', '시험준비물']]},
                      analysis(source_indices=[0])])
    prompts = []
    def ask(prompt):
        prompts.append(prompt)
        return next(responses)
    monkeypatch.setattr(market, 'ask', ask)
    monkeypatch.setattr(market, 'search_results', lambda _: ('duckduckgo_proxy', []))
    client = Mock()
    client.research.return_value = {
        'searched': True, 'opened_urls': [source['url']] if origin == 'native_open' else [],
        'text': json.dumps({'candidate_urls': [source['url']], 'excerpt': 'invented model evidence'})}
    monkeypatch.setattr(codex_client, 'CodexSubscriptionClient', Mock(return_value=client))
    fetch = Mock(return_value=source)
    monkeypatch.setattr(market, 'fetch_source', fetch)
    monkeypatch.setattr(market, 'fetch_trend_change', lambda _: None)
    report = market.select_category('취업', 1, titles=[])
    row = report['selected'][0]
    assert client.research.call_count == 1
    fetch.assert_called_once_with(source['url'])
    assert row['keyword'] == '시험준비물' and row['monthly_search'] == 1200
    assert row['evidence_mode'] == 'official_pages'
    assert row['organic_provider'] is None and row['dominant_result_ratio'] is None
    assert row['organic_results'] == row['organic_domains'] == []
    assert row['score_components']['organic_opportunity'] == 0
    assert row['verified_sources'] == [{**source, 'locator_origin': origin}]
    assert row['research_evidence'] == web_research_evidence(web_evidence(origin=origin))
    assert row['intent_results'] == [source['url']]
    assert row['selection_version'] == 4
    assert market.fresh_market_item(row, '취업')
    assert '검색 순위나 경쟁 결과는 확보하지 못했습니다' in prompts[-1]
    assert 'invented model evidence' not in prompts[-1]
    queued = market.enqueue_report([], report)
    assert queued == [row]
    market.record_published_keyword(row, 123, 'https://trendpulse.blog/test')
    assert market.candidate_pool({'2027 시험 준비물': {'keyword': '2027 시험 준비물', 'monthly': 1200}},
                                 market.historical_terms()) == []


@pytest.mark.parametrize('changes', [
    {'research_evidence': None},
    {'research_evidence': {'provider': 'codex_web', 'searched': False,
                           'locators': [{'url': 'https://example.go.kr/info', 'origin': 'native_open'}]}},
    {'research_evidence': {'provider': 'codex_web', 'searched': True,
                           'locators': [{'url': 'https://other.go.kr/info', 'origin': 'native_open'}]}},
    {'research_evidence': {'provider': 'codex_web', 'searched': True,
                           'locators': [{'url': 'https://example.go.kr/info', 'origin': 'invented'}]}},
    {'research_evidence': {'provider': 'codex_web', 'searched': True,
                           'opened_urls': ['https://example.go.kr/info']}},
    {'organic_provider': 'google_custom_search'}, {'dominant_result_ratio': 0},
    {'organic_results': [organic()]}, {'organic_domains': ['blog.example']},
    {'score_components': {'organic_opportunity': 40}}, {'monthly_search': 50000},
    {'keyword': '시험브랜드'}, {'intent_results': ['https://unread.go.kr/']},
    {'verified_sources': []}, {'selection_version': 3}, {'evidence_mode': 'invented'},
])
def test_native_research_cache_cannot_pass_without_provenance(changes):
    row = web_candidate()
    assert market.fresh_market_item(row, '취업')
    row.update(changes)
    assert not market.fresh_market_item(row, '취업')


def test_model_locator_redirect_uses_original_url_and_matching_origin(monkeypatch):
    from src import codex_client
    original = 'https://example.go.kr/old-guide'
    source = evidence('https://example.go.kr/current-guide')
    source['original_url'] = original
    client = Mock()
    client.research.return_value = {
        'searched': True, 'opened_urls': [], 'text': json.dumps({'candidate_urls': [original]})}
    monkeypatch.setattr(codex_client, 'CodexSubscriptionClient', Mock(return_value=client))
    fetch = Mock(return_value=source)
    monkeypatch.setattr(market, 'fetch_source', fetch)
    sources, research = market.research_official_sources('시험준비물', '취업', '2026-09-10')
    fetch.assert_called_once_with(original)
    row = web_candidate(origin='model_reported_locator')
    row.update(source_url=source['url'], verified_sources=sources,
               intent_results=[source['url']], research_evidence=research)
    assert market.fresh_market_item(row, '취업')
    row['verified_sources'][0]['locator_origin'] = 'native_open'
    assert not market.fresh_market_item(row, '취업')


def test_native_plan_keeps_each_cited_official_source_and_rejects_invalid_index(monkeypatch):
    sources = [evidence(), evidence('https://second.go.kr/info')]
    monkeypatch.setattr(market, 'ask', lambda _: analysis(source_indices=[1]))
    row, reason = market.topic_from_evidence('시험준비물', '취업', '2026-09-10', [], sources,
                                            evidence_mode='official_pages')
    assert reason is None and row['verified_sources'] == sources
    assert row['intent_results'] == [sources[1]['url']]
    monkeypatch.setattr(market, 'ask', lambda _: analysis(source_indices=[2]))
    assert market.topic_from_evidence('시험준비물', '취업', '2026-09-10', [], sources,
                                     evidence_mode='official_pages')[0] is None


@pytest.mark.parametrize('change', [{'excerpt': ''}, {'original_url': 'https://unopened.go.kr/'},
                                    {'checked_on': '2000-01-01'}, {'sha256': ''},
                                    {'locator_origin': None}, {'locator_origin': 'model_reported_locator'}])
def test_every_native_intent_source_requires_fresh_read_evidence(change):
    row = web_candidate()
    source = web_evidence('https://second.go.kr/info')
    row['verified_sources'].append({**source, **change})
    row['intent_results'].append(source['url'])
    row['research_evidence']['locators'].append({'url': source['url'], 'origin': source['locator_origin']})
    assert not market.fresh_market_item(row, '취업')


def test_later_native_research_timeout_preserves_selected_candidate(monkeypatch):
    source = web_evidence()
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {
        key: {'keyword': key, 'monthly': 1200} for key in ['시험준비물', '시험신청방법']})
    responses = iter([{'candidates': [{'keyword': '시험준비물'}, {'keyword': '시험신청방법'}]},
                      analysis(source_indices=[0])])
    monkeypatch.setattr(market, 'ask', lambda _: next(responses))
    monkeypatch.setattr(market, 'search_results', lambda _: ('duckduckgo_proxy', []))
    monkeypatch.setattr(market, 'research_official_sources', Mock(side_effect=[
        ([source], web_research_evidence(source)),
        RuntimeError('raw diagnostic must not be included')]))
    monkeypatch.setattr(market, 'fetch_trend_change', lambda _: None)
    report = market.select_category('취업', 1, titles=[])
    assert report['selected'][0]['keyword'] == '시험준비물'
    assert report['rejected'] == [{'keyword': '시험신청방법',
                                  'reason': 'codex web research unavailable: request_failed'}]


def test_native_source_check_can_cross_korean_midnight():
    row = web_candidate(selected_at='2026-09-09T14:59:00+00:00')
    row['verified_sources'][0]['checked_on'] = '2026-09-10'
    now = datetime.fromisoformat('2026-09-09T15:10:00+00:00')
    assert market.fresh_market_item(row, '취업', now)
    row['verified_sources'][0]['checked_on'] = '2026-09-11'
    assert not market.fresh_market_item(row, '취업', now)


@pytest.mark.parametrize('keyword,category', [
    ('국가기술자격증종류', '취업'),
    ('2026 국가 기술 자격증 종류', '취업'),
    ('자격증종류', '취업'),
    ('공기업채용일정', '취업'),
    ('건강보험공단채용일정', '취업'),
    ('예방접종관련자격증', '취업'),
    ('건강보험료환급금', '건강'),
    ('건강보험자격증명서', '건강'),
    ('국가건강검진대상', '건강'),
    ('예방접종일정', '건강'),
    ('종합소득세신고방법', '생활정보'),
    ('전기요금계산', '생활정보'),
    ('전세보증금반환', '생활정보'),
])
def test_clear_keyword_domain_does_not_follow_requested_category(keyword, category):
    assert market.inferred_keyword_category(keyword) == category
    assert market.category_matches(keyword, category)
    assert all(not market.category_matches(keyword, other)
               for other in market.CATEGORIES if other != category)


@pytest.mark.parametrize('category', ['취업', '건강', '생활정보'])
def test_unclear_keyword_domain_is_left_for_evidence_review(category):
    assert market.inferred_keyword_category('안내확인방법') is None
    assert market.category_matches('안내확인방법', category)


@pytest.mark.parametrize('keyword', ['자격', '지원금', '신청자격'])
def test_generic_eligibility_terms_do_not_imply_employment(keyword):
    assert market.inferred_keyword_category(keyword) != '취업'


@pytest.mark.parametrize('keyword', [
    '수급자격증명서', '수급자격증빙서류', '의료비세액공제', '건강보험료연말정산',
])
def test_eligibility_documents_and_mixed_health_tax_terms_remain_undecided(keyword):
    assert market.inferred_keyword_category(keyword) is None
    assert all(market.category_matches(keyword, category) for category in market.CATEGORIES)


@pytest.mark.parametrize('keyword', ['의료비세액공제', '건강보험료연말정산'])
def test_mixed_health_tax_topic_can_follow_living_information_evidence_review(monkeypatch, keyword):
    review = Mock(return_value=analysis(keyword, '생활정보'))
    monkeypatch.setattr(market, 'ask', review)
    item, reason = market.topic_from_evidence(keyword, '생활정보', '2026-09-10',
                                              [organic()], [evidence()])
    review.assert_called_once()
    assert reason is None and item['category'] == '생활정보'
    assert '의료비세액공제' in review.call_args.args[0].replace(' ', '')


@pytest.mark.parametrize('category,expected', [
    ('취업', {'국가기술자격증종류', '안내확인방법'}),
    ('건강', {'건강보험료환급금', '안내확인방법'}),
    ('생활정보', {'전기요금계산', '안내확인방법'}),
])
def test_category_pool_excludes_cross_category_related_keywords(category, expected):
    stats = {keyword: {'keyword': keyword, 'monthly': 1200} for keyword in
             ('국가기술자격증종류', '건강보험료환급금', '전기요금계산', '안내확인방법')}
    assert {row['keyword'] for row in market.candidate_pool(stats, [], category)} == expected
    assert {row['keyword'] for row in market.candidate_pool(stats, [])} == set(stats)


def test_selection_passes_requested_category_to_pool(monkeypatch):
    category = '생활정보'
    keyword = '전기요금계산'
    stats = {key: {'keyword': key, 'monthly': 1200}
             for key in ('국가기술자격증종류', keyword)}
    monkeypatch.setattr(market, 'demand_candidates', lambda _: stats)
    original_pool = market.candidate_pool
    seen_categories = []

    def pool(stats, titles, category=None):
        seen_categories.append(category)
        return original_pool(stats, titles, category)

    monkeypatch.setattr(market, 'candidate_pool', pool)
    monkeypatch.setattr(market, 'ask', Mock(side_effect=[
        {'candidates': [{'keyword': keyword}]}, analysis(keyword, category)]))
    monkeypatch.setattr(market, 'search_results', lambda _: ('google_custom_search', [organic()]))
    monkeypatch.setattr(market, 'candidate_sources', lambda *args: [evidence()])
    monkeypatch.setattr(market, 'fetch_trend_change', lambda _: None)
    report = market.select_category(category, 1, titles=[])
    assert seen_categories == [category]
    assert [item['keyword'] for item in report['selected']] == [keyword]


def test_cross_category_proposal_is_rejected_even_if_it_reaches_pool(monkeypatch):
    keyword = '국가기술자격증종류'
    measured = {'keyword': keyword, 'monthly': 1200}
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {keyword: measured})
    monkeypatch.setattr(market, 'candidate_pool', lambda *args, **kwargs: [measured])
    monkeypatch.setattr(market, 'ask', lambda _: {'candidates': [{'keyword': keyword}]})
    search = Mock(side_effect=AssertionError('Mismatched category must not trigger research'))
    monkeypatch.setattr(market, 'search_results', search)
    report = market.select_category('생활정보', 1, titles=[])
    assert report['selected'] == []
    assert report['rejected'] == [{'keyword': keyword, 'reason': 'category mismatch'}]
    search.assert_not_called()


@pytest.mark.parametrize('evidence_mode', ['serp', 'official_pages'])
@pytest.mark.parametrize('keyword,category,accepted', [
    ('국가기술자격증종류', '생활정보', False),
    ('국가기술자격증종류', '취업', True),
    ('건강보험료환급금', '생활정보', False),
    ('건강보험료환급금', '건강', True),
])
def test_requested_category_in_model_json_cannot_override_keyword_domain(
        monkeypatch, evidence_mode, keyword, category, accepted):
    result = analysis(keyword, category, source_indices=[0])
    if keyword == '국가기술자격증종류':
        result['topic'] = '국가기술자격증종류: 기능사·산업기사·기사·기능장·기술사 등급 비교'
    monkeypatch.setattr(market, 'ask', lambda _: result)
    sources = [web_evidence()]
    organic_results = [organic()] if evidence_mode == 'serp' else []
    item, reason = market.topic_from_evidence(keyword, category, '2026-09-10', organic_results,
                                              sources, evidence_mode=evidence_mode)
    if accepted:
        assert reason is None and item['category'] == category
    else:
        assert item is None and reason == 'category mismatch'


@pytest.mark.parametrize('evidence_mode', ['serp', 'official_pages'])
def test_generated_title_cannot_move_unknown_keyword_into_other_category(monkeypatch, evidence_mode):
    keyword = '안내확인방법'
    result = analysis(keyword, '생활정보', source_indices=[0],
                      topic='안내확인방법: 국가기술자격증종류와 기능사 등급 비교')
    monkeypatch.setattr(market, 'ask', lambda _: result)
    item, reason = market.topic_from_evidence(keyword, '생활정보', '2026-09-10',
                                              [organic()] if evidence_mode == 'serp' else [],
                                              [web_evidence()], evidence_mode=evidence_mode)
    assert item is None and reason == 'category mismatch'


@pytest.mark.parametrize('supported,model_category,accepted', [
    (True, '생활정보', True), (False, '생활정보', False), (True, '건강', False),
])
def test_unknown_keyword_still_requires_independent_model_category_review(
        monkeypatch, supported, model_category, accepted):
    review = Mock(return_value=analysis('안내확인방법', model_category, supported=supported))
    monkeypatch.setattr(market, 'ask', review)
    item, reason = market.topic_from_evidence('안내확인방법', '생활정보', '2026-09-10',
                                              [organic()], [evidence()])
    review.assert_called_once()
    assert '"category":"생활정보"' not in review.call_args.args[0].replace(' ', '')
    assert (item is not None) is accepted
    assert bool(reason) is not accepted


@pytest.mark.parametrize('evidence_mode', ['serp', 'official_pages'])
@pytest.mark.parametrize('keyword,topic', [
    ('국가기술자격증종류', '국가기술자격증종류: 기능사·산업기사·기사·기능장·기술사 등급 비교'),
    ('건강보험료환급금', '건강보험료환급금 확인 방법'),
    ('안내확인방법', '안내확인방법: 국가기술자격증종류와 기능사 등급 비교'),
])
def test_cached_wrong_category_report_cannot_be_enqueued(evidence_mode, keyword, topic):
    row = web_candidate() if evidence_mode == 'official_pages' else candidate()
    row.update(category='생활정보', keyword=keyword, topic=topic, keywords=[keyword])
    queue = [{'source': 'manual', 'status': 'pending', 'topic': '기존 보존 항목'}]
    before = [dict(item) for item in queue]
    assert not market.fresh_market_item(row, '생활정보')
    with pytest.raises(RuntimeError, match='no verified market topic'):
        market.enqueue_report(queue, {'category': '생활정보', 'selected': [row]})
    assert queue == before


@pytest.mark.parametrize('evidence_mode', ['serp', 'official_pages'])
@pytest.mark.parametrize('keyword,category', [
    ('국가기술자격증종류', '취업'), ('건강보험료환급금', '건강'),
])
def test_correct_category_cached_report_remains_usable(evidence_mode, keyword, category):
    row = web_candidate() if evidence_mode == 'official_pages' else candidate()
    row.update(category=category, keyword=keyword, topic=keyword + ' 확인 방법', keywords=[keyword])
    assert market.fresh_market_item(row, category)
    assert market.enqueue_report([], {'category': category, 'selected': [row]}) == [row]
