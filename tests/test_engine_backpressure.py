"""Real admission locks must preserve capacity and HTTP responsiveness."""
import io
import time
from types import SimpleNamespace

import pytest

from core import admission
from core.storage import TempWorkspace
from converters import engine
from converters.contracts import ConversionBusyError, Operation


@pytest.fixture
def capacity(tmp_path, monkeypatch):
    monkeypatch.setattr(admission, '_ADMISSION_DIR', tmp_path / 'locks')
    monkeypatch.setattr(engine, 'settings', SimpleNamespace(
        admission_wait_milliseconds=250, max_concurrent_conversions=1,
        max_concurrent_ocr=1, max_concurrent_office=1))


def run_ocr(monkeypatch, handler):
    monkeypatch.setattr(engine, 'get_operation', lambda _: Operation('probe', 'generator', handler, 'tesseract'))
    with TempWorkspace() as workspace:
        return engine.ConversionEngine().convert(tool=SimpleNamespace(id='probe'), safe_inputs=[],
            workspace=workspace, timeout=180, max_pdf_pages=1000)


def assert_free(name):
    token = admission.acquire_slot(name, 1, 0)
    assert token is not None, name
    token.release()


def test_waiting_ocr_does_not_reserve_general_capacity(capacity, monkeypatch):
    held = admission.acquire_slot('ocr', 1, 0)
    assert held is not None
    try:
        started = time.monotonic()
        with pytest.raises(ConversionBusyError):
            run_ocr(monkeypatch, lambda *args: pytest.fail('busy work must not execute'))
        assert time.monotonic() - started < 1
        assert_free('conversion')
    finally:
        held.release()
    assert_free('ocr')


def test_general_rejection_releases_acquired_ocr_slot(capacity, monkeypatch):
    held = admission.acquire_slot('conversion', 1, 0)
    assert held is not None
    try:
        with pytest.raises(ConversionBusyError):
            run_ocr(monkeypatch, lambda *args: pytest.fail('busy work must not execute'))
        assert_free('ocr')
    finally:
        held.release()
    assert_free('conversion')


def test_native_handler_failure_releases_both_capacity_pools(capacity, monkeypatch):
    def broken(*args):
        raise ValueError('synthetic native conversion failure')
    with pytest.raises(ValueError, match='synthetic native'):
        run_ocr(monkeypatch, broken)
    assert_free('conversion')
    assert_free('ocr')


def test_busy_api_has_retry_hint_and_cleans_uploaded_workspace(capacity, tmp_path, monkeypatch):
    from app_factory import create_app
    from api import routes
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path}/accounts.db')
    monkeypatch.setenv('PUBLIC_AUTH_ENABLED', '0')
    monkeypatch.setenv('PUBLIC_BILLING_ENABLED', '0')
    roots = []
    class Tracked(TempWorkspace):
        def __enter__(self):
            result = super().__enter__()
            roots.append(self.path)
            return result
    monkeypatch.setattr(routes, 'TempWorkspace', Tracked)
    held = admission.acquire_slot('conversion', 1, 0)
    assert held is not None
    try:
        client = create_app().test_client()
        response = client.post('/api/v2/convert', data={
            'tool': 'file-hash', 'files': (io.BytesIO(b'synthetic bilingual 00123'), 'fixture.txt')})
        assert response.status_code == 503
        assert response.headers['Retry-After'] == '3'
        assert roots and all(not root.exists() for root in roots)
        assert client.get('/api/v2/readyz').status_code == 200
    finally:
        held.release()
    assert_free('conversion')


def test_workload_and_general_wait_share_one_deadline(capacity, monkeypatch):
    import threading
    engine.settings.admission_wait_milliseconds = 500
    ocr = admission.acquire_slot('ocr', 1, 0)
    general = admission.acquire_slot('conversion', 1, 0)
    assert ocr is not None and general is not None
    release = threading.Timer(.30, ocr.release)
    release.start()
    try:
        started = time.monotonic()
        with pytest.raises(ConversionBusyError):
            run_ocr(monkeypatch, lambda *args: pytest.fail('general pool remains full'))
        elapsed = time.monotonic() - started
        assert .45 <= elapsed < .70, elapsed
        assert_free('ocr')
    finally:
        release.join(1)
        ocr.release()
        general.release()
