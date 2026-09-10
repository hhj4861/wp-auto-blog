"""Public-only connectivity diagnostic contracts; no real HTTP requests."""
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from scripts import check_official_sources as probe


def public_source(url):
    return {'url': url, 'original_url': url, 'title': 'Public official guide',
            'checked_on': '2026-09-10', 'sha256': 'a' * 64,
            'excerpt': 'Public source body. ' * 500,
            'unrelated_metadata': 'PRIVATE-EXTRA-METADATA'}


def test_probe_keeps_case_order_continues_after_failure_and_exports_only_public_evidence(monkeypatch, tmp_path, capsys):
    first = public_source(probe.CASES[0][1])
    third = public_source(probe.CASES[2][1])
    fetch = Mock(side_effect=[first, RuntimeError('PRIVATE-ERROR-URL-HEADERS'), third])
    monkeypatch.setattr(probe, 'fetch_source', fetch)
    output = tmp_path / 'sources.json'
    assert probe.main(['--output', str(output)]) == 0
    assert [call.args[0] for call in fetch.call_args_list] == [url for _, url in probe.CASES]
    summary = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [row['case'] for row in summary] == [name for name, _ in probe.CASES]
    assert [row['success'] for row in summary] == [True, False, True]
    assert all(set(row) == {'case', 'success', 'title_chars', 'excerpt_chars', 'elapsed_seconds'} for row in summary)
    assert summary[0]['title_chars'] == len(first['title'])
    assert summary[0]['excerpt_chars'] == 8000
    assert summary[1]['title_chars'] == summary[1]['excerpt_chars'] == 0
    assert all(row['elapsed_seconds'] >= 0 for row in summary)
    artifact = json.loads(output.read_text())
    assert artifact['purpose'] == 'source_accessibility_only'
    assert artifact['schema_version'] == 1
    assert [row['source'] is not None for row in artifact['cases']] == [True, False, True]
    assert artifact['cases'][0]['source'] == {**{key: first[key] for key in probe.SOURCE_FIELDS}, 'excerpt': first['excerpt'][:8000]}
    assert 'PRIVATE' not in output.read_text()


@pytest.mark.parametrize('failure', [None, RuntimeError('PRIVATE-FAILURE'), {'excerpt': 'not a source'}])
def test_probe_all_failures_still_attempt_all_cases_and_write_artifact(monkeypatch, tmp_path, capsys, caplog, failure):
    fetch = Mock(side_effect=[failure, failure, failure])
    monkeypatch.setattr(probe, 'fetch_source', fetch)
    output = tmp_path / 'sources.json'
    assert probe.main(['--output', str(output)]) == 1
    assert fetch.call_count == 3
    assert all(row['source'] is None and not row['success'] for row in json.loads(output.read_text())['cases'])
    captured = capsys.readouterr()
    assert len(captured.out.splitlines()) == 3
    assert 'PRIVATE' not in captured.out + captured.err + caplog.text + output.read_text()


def test_probe_artifact_write_error_has_fixed_reason_without_path_or_exception(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(probe, 'fetch_source', Mock(return_value=None))
    monkeypatch.setattr(Path, 'write_text', Mock(side_effect=OSError('PRIVATE-PATH-ERROR')))
    assert probe.main(['--output', str(tmp_path / 'PRIVATE-PATH.json')]) == 2
    assert 'artifact_write_error' in caplog.text and 'PRIVATE' not in caplog.text


def test_public_probe_workflow_is_manual_main_only_and_has_no_auth_or_posting_dependencies():
    source = Path('.github/workflows/official-source-check.yml').read_text()
    workflow = yaml.safe_load(source)
    assert workflow.get('on', workflow.get(True)) == {'workflow_dispatch': None}
    assert workflow['permissions'] == {'contents': 'read'}
    assert 'concurrency' not in workflow and 'env' not in workflow
    job = workflow['jobs']['check']
    assert job['if'] == "github.ref == 'refs/heads/main'"
    assert job['timeout-minutes'] == 5 and 'env' not in job
    steps = job['steps']
    checkout = next(step for step in steps if step.get('uses') == 'actions/checkout@v4')
    assert checkout['with'] == {'ref': 'main', 'persist-credentials': False}
    python = next(step for step in steps if step.get('uses') == 'actions/setup-python@v5')
    assert python['with'] == {'python-version': '3.11'}
    commands = [step['run'] for step in steps if 'run' in step]
    assert commands == ['pip install requests beautifulsoup4',
                        'python scripts/check_official_sources.py --output "$RUNNER_TEMP/official-source-check.json"']
    artifact = next(step for step in steps if step.get('uses') == 'actions/upload-artifact@v4')
    assert artifact['if'] == 'always()'
    assert artifact['with']['path'] == '${{ runner.temp }}/official-source-check.json'
    assert artifact['with']['retention-days'] == 3
    assert all('env' not in step for step in steps)
    assert all(word not in source.lower() for word in ('secrets.', 'codex', 'wordpress', 'actions/cache'))
    assert probe.CASES[-1][1] == 'https://www.korea.kr/news/policyNewsView.do?newsId=148960444'
