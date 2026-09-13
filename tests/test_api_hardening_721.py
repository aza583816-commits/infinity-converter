import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from app_factory import create_app
from core.storage import TempWorkspace
from api import ai, routes


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path / "test.db"}')
    monkeypatch.setenv('PUBLIC_AUTH_ENABLED', '0')
    monkeypatch.setenv('PUBLIC_BILLING_ENABLED', '0')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    return create_app().test_client()


@pytest.mark.parametrize('payload', [[], ['x'], 'text', 123, None])
@pytest.mark.parametrize('endpoint', ['plan', 'ask'])
def test_ai_rejects_nonobject_json(client, payload, endpoint):
    response = client.post(f'/api/v2/ai/{endpoint}', json=payload)
    assert response.status_code == 400


def test_provider_never_receives_filename_password_or_error_text(client, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'unit-test-only')
    captured = []
    def provider(prompt, system, **kwargs):
        captured.append(prompt)
        return json.dumps({'steps':[{'tool_id':'invented-tool'}]})
    with patch.object(ai, '_call_gemini', provider):
        response = client.post('/api/v2/ai/plan', json={
            'prompt':'compress pdf', 'context':{
                'files':[{'filename':'PRIVATE_NAME.pdf','extension':'.pdf'}],
                'settings':{'password':'PRIVATE_PASSWORD'},
                'error':{'message':'PRIVATE_PATH'},
            }})
    assert response.status_code == 200
    assert not any('PRIVATE_' in item for item in captured)
    assert response.json['steps'][0]['tool_id'] == 'pdf-compress'


def test_provider_outage_preserves_local_plan(client, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'unit-test-only')
    with patch.object(ai, '_call_gemini', side_effect=TimeoutError):
        response = client.post('/api/v2/ai/plan', json={'prompt':'صغر PDF'})
    assert response.status_code == 200
    assert response.json['enhanced'] is False
    assert response.json['steps'][0]['tool_id'] == 'pdf-compress'


def test_stream_close_cleans_workspace(client):
    roots = []
    class Tracked(TempWorkspace):
        def __enter__(self):
            result = super().__enter__(); roots.append(self.path); return result
    with patch.object(routes, 'TempWorkspace', Tracked):
        response = client.post('/api/v2/convert', data={'tool':'file-hash','files':(io.BytesIO(b'hello'),'a.txt')}, buffered=False)
        assert response.status_code == 200
        assert response.get_data()
        response.close()
    assert roots and all(not p.exists() for p in roots)


def test_rejected_upload_cleans_workspace(client):
    roots = []
    class Tracked(TempWorkspace):
        def __enter__(self):
            result = super().__enter__(); roots.append(self.path); return result
    with patch.object(routes, 'TempWorkspace', Tracked):
        response = client.post('/api/v2/convert', data={'tool':'pdf-compress','files':(io.BytesIO(b'bad'),'a.pdf')})
    assert response.status_code == 400
    assert roots and all(not p.exists() for p in roots)


def test_api_has_no_store(client):
    response = client.post('/api/v2/ai/plan', json={'prompt':'compress PDF'})
    assert response.headers['Cache-Control'] == 'no-store, private'


def test_language_switch_overrides_saved_english_choice(client):
    english = client.get('/?lang=en').get_data(as_text=True)
    assert 'href="/?lang=ar"' in english
    arabic = client.get('/?lang=ar').get_data(as_text=True)
    assert '<html lang="ar" dir="rtl">' in arabic
    assert 'hreflang="ar" href="https://infinityconverter.com/?lang=ar"' in arabic


def test_incompatible_ai_steps_return_safe_local_path(client, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'unit-test-only')
    with patch.object(ai, '_call_gemini', return_value=json.dumps({'steps':[{'tool_id':'pdf-ocr'},{'tool_id':'pdf-to-docx'}]})):
        response = client.post('/api/v2/ai/plan', json={'prompt':'scanned PDF to editable Word'})
    assert [s['tool_id'] for s in response.json['steps']] == ['ocr-pdf-to-searchable','pdf-to-docx']


def test_nonobject_context_is_ignored(client):
    response = client.post('/api/v2/ai/plan', json={'prompt':'compress PDF','context':[{'filename':'private.pdf'}]})
    assert response.status_code == 200
    assert response.json['steps'][0]['tool_id'] == 'pdf-compress'


def test_two_file_batch_reports_inputs_and_downloads_zip(client):
    import zipfile
    response = client.post('/api/v2/convert', data={'tool':'file-hash','files':[(io.BytesIO(b'one'),'one.txt'),(io.BytesIO(b'two'),'two.txt')]}, buffered=True)
    assert response.status_code == 200
    assert response.headers['X-Batch-Total'] == '2'
    assert response.headers['X-Batch-Succeeded'] == '2'
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        assert len(archive.namelist()) == 2
        for name in archive.namelist():
            assert json.loads(archive.read(name))
    response.close()
