"""Scheduled selection and publication must use the tested native provider."""
from pathlib import Path

import yaml


def workflow(name):
    return yaml.safe_load(Path('.github/workflows', name).read_text())


def test_selection_and_queue_research_use_the_same_explicit_provider():
    select = workflow('blog-keyword-select.yml')['jobs']['select']
    publish = workflow('auto-post.yml')['jobs']['post-queue']
    for job in (select, publish):
        steps = [step for step in job['steps']
                 if 'select_blog_keywords.py' in step.get('run', '')]
        assert len(steps) == 1
        env = steps[0]['env']
        assert env['MARKET_SEARCH_PROVIDER'] == 'codex_native_search'
        assert 'GOOGLE_SEARCH_API_KEY' not in env
        assert 'GOOGLE_SEARCH_ENGINE_ID' not in env


def test_live_sample_diagnostic_uses_the_production_adapter_with_auth_cleanup():
    diagnostic = workflow('codex-search-sample.yml')
    job = diagnostic['jobs']['sample']
    steps = job['steps']
    checks = [(i, step) for i, step in enumerate(steps)
              if step.get('run') == 'python scripts/check_market_search.py']
    assert len(checks) == 1
    index, sample = checks[0]
    assert sample['env'] == {'MARKET_SEARCH_PROVIDER': 'codex_native_search'}
    assert any('codex_worker_auth.py restore' in step.get('run', '') for step in steps[:index])
    assert any(step.get('if') == 'always()' and 'codex_worker_auth.py persist' in step.get('run', '')
               for step in steps[index + 1:])
    assert diagnostic['concurrency'] == workflow('auto-post.yml')['jobs']['post-queue']['concurrency']
    assert diagnostic['concurrency'] == workflow('blog-keyword-select.yml')['concurrency']
