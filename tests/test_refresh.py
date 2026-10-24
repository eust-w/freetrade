import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import refresh
from scripts.export_run_history import summarize
from scripts.verify_site import Links


@pytest.fixture
def snapshot():
    return refresh.read_snapshot(refresh.ROOT / 'examples/demo_snapshot.json')


def test_offline_demo_does_not_contact_provider(tmp_path, monkeypatch):
    def unexpected():
        raise AssertionError('demo contacted provider')
    monkeypatch.setattr(refresh, 'live_snapshot', unexpected)
    result = refresh.run('demo', tmp_path, tmp_path / 'cache.json')
    assert result['mode'] == 'demo'
    assert result['source'] == 'synthetic'
    assert not (tmp_path / 'cache.json').exists()
    page = (tmp_path / 'index.html').read_text()
    assert '合成数据' in page and '2026-06-15' in page
    links = Links()
    links.feed(page)
    assert {'https://github.com/eust-w', 'https://claworkers.com/'} <= links.urls


def test_fallback_preserves_original_data_date(tmp_path, monkeypatch, snapshot):
    snapshot['source'] = 'eastmoney-akshare'
    cache = tmp_path / 'cache.json'
    refresh.atomic_json(cache, snapshot)
    original = cache.read_bytes()
    def fail():
        raise ConnectionError('private upstream details')
    monkeypatch.setattr(refresh, 'live_snapshot', fail)
    result = refresh.run('live', tmp_path / 'out', cache, True)
    assert result['mode'] == 'fallback'
    assert result['data_as_of'] == '2026-06-15'
    assert cache.read_bytes() == original
    assert 'private upstream' not in json.dumps(result)
    assert '历史缓存' in (tmp_path / 'out/index.html').read_text()


def test_default_live_failure_does_not_overwrite_page(tmp_path, monkeypatch):
    (tmp_path / 'index.html').write_text('last good page')
    def fail():
        raise RuntimeError('provider down')
    monkeypatch.setattr(refresh, 'live_snapshot', fail)
    with pytest.raises(RuntimeError):
        refresh.run('live', tmp_path, tmp_path / 'missing.json')
    assert (tmp_path / 'index.html').read_text() == 'last good page'


def test_demo_cannot_be_live_fallback(tmp_path, monkeypatch, snapshot):
    cache = tmp_path / 'cache.json'
    refresh.atomic_json(cache, snapshot)
    def fail():
        raise RuntimeError('provider down')
    monkeypatch.setattr(refresh, 'live_snapshot', fail)
    with pytest.raises(ValueError, match='demo data'):
        refresh.run('live', tmp_path / 'out', cache, True)


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), True, '80'])
def test_reject_invalid_metrics(snapshot, bad):
    snapshot['stocks'][0]['score'] = bad
    with pytest.raises(ValueError):
        refresh.validate_snapshot(snapshot)


def test_reject_duplicate_symbols(snapshot):
    snapshot['stocks'][1]['code'] = snapshot['stocks'][0]['code']
    with pytest.raises(ValueError, match='duplicate'):
        refresh.validate_snapshot(snapshot)


def test_untrusted_strings_are_escaped(snapshot):
    snapshot['stocks'][0]['name'] = '</script><img src=x onerror=alert(1)>'
    page = refresh.render(snapshot, 'demo', '2026-10-24')
    assert '</script><img' not in page
    assert '&lt;/script&gt;&lt;img' in page


def test_cache_round_trip(tmp_path, snapshot):
    snapshot['source'] = 'eastmoney-akshare'
    cache = tmp_path / 'cache.json'
    refresh.atomic_json(cache, snapshot)
    assert refresh.read_snapshot(cache) == snapshot
    result = refresh.run('cached', tmp_path / 'out', cache)
    assert result['mode'] == 'cached'


def test_log_export_only_allowlisted_fields(tmp_path):
    log = tmp_path / 'refresh-20261024-120000.log'
    log.write_text('{"status":"ok","mode":"fallback","stocks":["private name"],"output":"/private/path"}\nhttps_status=200 bytes=123\nSECRET_TOKEN=private\n')
    row = summarize(log)
    assert row['candidate_count'] == 1
    assert row['http_status'] == 200
    assert 'private' not in json.dumps(row)
    assert len(row['source_sha256']) == 64
