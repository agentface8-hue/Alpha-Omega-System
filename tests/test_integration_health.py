import io
import json
import urllib.error
from unittest.mock import patch
from core import airtable, system_health


def test_json_mode_does_not_probe_unused_supabase():
    with patch('core.storage_paths.use_supabase', return_value=False), patch('urllib.request.urlopen') as call:
        result = system_health.check_supabase()
    assert result['status'] == 'GREEN'
    assert 'Disabled' in result['detail']
    call.assert_not_called()


def test_airtable_health_is_read_only_and_cached():
    with patch.object(airtable, 'APIKEY', 'test'), patch.object(airtable, '_health_cache', None), patch.object(airtable, '_health_cache_until', 0), patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps({'records':[]}).encode())) as call:
        first = airtable.check_connection()
        second = airtable.check_connection()
        assert first == second
        assert first['status'] == 'GREEN'
        assert 'write access not tested' in first['detail']
        assert call.call_count == 1
        assert call.call_args.args[0].get_method() == 'GET'


def test_airtable_429_obeys_cooldown_without_replaying_requests():
    error = urllib.error.HTTPError('https://example.invalid',429,'limit',{'Retry-After':'120'},None)
    with patch.object(airtable, 'APIKEY', 'test'), patch.object(airtable, '_health_cache', None), patch.object(airtable, '_health_cache_until', 0), patch('urllib.request.urlopen', side_effect=error) as call:
        assert '120s' in airtable.check_connection()['detail']
        assert airtable.check_connection()['status'] == 'YELLOW'
        assert call.call_count == 1
