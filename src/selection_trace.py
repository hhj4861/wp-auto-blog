"""Bounded, per-selection public-source audit; no credentials or raw exceptions."""
from contextvars import ContextVar
from functools import wraps

_events = ContextVar('selection_source_events', default=None)


def record(keyword, category, stage, **details):
    events = _events.get()
    if events is not None and len(events) < 600:
        events.append({'keyword': keyword, 'category': category, 'stage': stage, **details})


def capture(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        events = []
        token = _events.set(events)
        try:
            report = function(*args, **kwargs)
            report['source_discovery_audit'] = events
            report['selection_outcome'] = (
                'selected' if report['selected'] else
                'analysis_unavailable' if report.get('operational_error') else
                'research_budget_exhausted' if report.get('research_stop_reason') in ('round_limit', 'time_budget')
                else 'no_pass_among_evaluated')
            report['selection_funnel'] = {
                'measured': report.get('measured_candidates', 0),
                'pool': report.get('research_pool_size', 0),
                'shortlist_offered_unique': len({key for row in report.get('proposal_rounds', [])
                                                for key in row['offered_keywords']}),
                'evaluated': report.get('evaluated_candidates', 0),
                'held': len(report['held']), 'rejected': len(report['rejected']),
                'selected': len(report['selected']),
                'stop_reason': report.get('research_stop_reason', 'unknown'),
            }
            return report
        finally:
            _events.reset(token)
    return wrapped
