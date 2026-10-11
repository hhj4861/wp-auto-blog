from copy import deepcopy
from unittest.mock import Mock
import hashlib
import pytest
from scripts import repair_safety_draft as m

RAW = '<p>'+m.OLD+'</p>'+''.join(f'<td>원서접수: 일정{i}</td>' for i in range(6))+'<script>keep()</script>'


def setup(monkeypatch):
    monkeypatch.setattr(m,'RAW_SHA',hashlib.sha256(RAW.encode()).hexdigest())
    p=dict(id=m.POST_ID,slug=m.SLUG,status='draft',content={'raw':RAW},modified_gmt='now',title={'raw':'산업안전기사'},categories=[107],featured_media=1926)
    response=lambda x:Mock(json=lambda:deepcopy(x))
    return p,response


def test_exact_corrections_and_metadata_preservation(monkeypatch):
    p,r=setup(monkeypatch);saved=deepcopy(p);saved['content']['raw']=m.corrected(RAW)
    session=Mock();session.get.side_effect=[r(p),r(p),r(saved)]
    assert m.repair(session)['verified']
    assert session.post.call_args.kwargs['json']=={'content':RAW.replace(m.OLD,m.NEW).replace('원서접수:','원서접수(휴일 제외):')}
    with pytest.raises(ValueError):m.corrected(RAW+'changed')


@pytest.mark.parametrize('change',[{'status':'publish'},{'id':999},{'slug':'another'}])
def test_other_posts_never_changed(monkeypatch,change):
    p,r=setup(monkeypatch);p.update(change);session=Mock();session.get.return_value=r(p)
    with pytest.raises(ValueError):m.repair(session)
    session.post.assert_not_called()


def test_concurrent_edits_never_overwritten(monkeypatch):
    p,r=setup(monkeypatch);changed=deepcopy(p);changed['modified_gmt']='later';session=Mock();session.get.side_effect=[r(p),r(changed)]
    with pytest.raises(ValueError,match='changed'):m.repair(session)
    session.post.assert_not_called()
