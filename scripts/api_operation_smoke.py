"""All registry operations via HTTP upload/download, with isolated test storage.

Run inside the built production image: python scripts/api_operation_smoke.py
No provider keys, production database, or production endpoint are used.
"""
from __future__ import annotations
import io
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def verify_download_semantics(tool_id: str, body: bytes) -> None:
    """Verify security-sensitive properties on the exact HTTP download bytes."""
    if tool_id == 'pdf-password-protect':
        reader = PdfReader(io.BytesIO(body), strict=False)
        assert reader.is_encrypted, 'HTTP password-protect download is not encrypted'
        assert reader.decrypt('secret'), 'HTTP password-protect download rejects requested password'
        assert len(reader.pages) >= 1, 'HTTP password-protect download has no pages after decryption'
    elif tool_id == 'pdf-unlock':
        reader = PdfReader(io.BytesIO(body), strict=False)
        assert not reader.is_encrypted, 'HTTP unlock download is still encrypted'
        assert len(reader.pages) >= 1, 'HTTP unlock download has no pages'


def run():
    with tempfile.TemporaryDirectory(prefix='infinity-api-gate-') as td:
        base = Path(td)
        os.environ['DATABASE_URL'] = f'sqlite:///{base / "test.db"}'
        os.environ['PUBLIC_AUTH_ENABLED'] = '0'
        os.environ['PUBLIC_BILLING_ENABLED'] = '0'
        os.environ['GEMINI_API_KEY'] = ''
        from app_factory import create_app
        from core.tooling import TOOLS
        from core.storage import TempWorkspace
        from scripts.full_operation_smoke import make_fixtures, choose_fixture, options_for, param_for
        from api import routes
        make_fixtures(base / 'fixtures')
        app = create_app()
        app.config.update(TESTING=True, RATELIMIT_ENABLED=False)
        roots = []
        class TrackedWorkspace(TempWorkspace):
            def __enter__(self):
                result = super().__enter__()
                roots.append(self.path)
                return result
        failed = []
        with patch.object(routes, 'TempWorkspace', TrackedWorkspace), app.test_client() as client:
            for index, tool in enumerate(TOOLS.values(), 1):
                data = {'tool': tool.id, 'param': param_for(tool), **options_for(tool)}
                if tool.input_required:
                    count = 2 if tool.id in {'pdf-merge','pdf-compare','text-diff','checksum-compare','zip-create','tar-create','tar-gzip-create','tar-bzip2-create','csv-merge-deduplicate','image-to-pdf'} else 1
                    source = choose_fixture(tool, base / 'fixtures')
                    data['files'] = [(io.BytesIO(source.read_bytes()), f'{n}-{source.name}') for n in range(count)]
                try:
                    response = client.post('/api/v2/convert', data=data, content_type='multipart/form-data', buffered=False, environ_overrides={'REMOTE_ADDR': f'192.0.2.{index}'})
                    try:
                        body = response.get_data()
                        assert response.status_code == 200, f'HTTP {response.status_code}'
                        assert body and response.headers.get('Content-Disposition', '').startswith('attachment;')
                        assert response.headers.get('X-Conversion-Engine')
                        assert response.headers.get('Cache-Control') == 'no-store, private'
                        verify_download_semantics(tool.id, body)
                    finally:
                        response.close()
                    assert not any(root.exists() for root in roots), 'workspace leaked after streaming close'
                    print(f'API PASS {tool.id}')
                except Exception as exc:
                    failed.append(tool.id)
                    print(f'API FAIL {tool.id}: {type(exc).__name__}: {exc}')
            for index, tool in enumerate(TOOLS.values(), 1):
                if not tool.input_required:
                    continue
                for name, content in [('empty.txt', b''), ('wrong.exe', b'invalid')]:
                    response = client.post('/api/v2/convert', data={'tool':tool.id, 'files':(io.BytesIO(content),name)}, buffered=True, environ_overrides={'REMOTE_ADDR': f'198.51.100.{index}'})
                    assert 400 <= response.status_code < 500, (tool.id, response.status_code)
                    response.close()
            assert not any(root.exists() for root in roots), 'workspace leaked after invalid uploads'
        print(f'API RESULT {len(TOOLS)-len(failed)}/{len(TOOLS)}')
        if failed:
            raise SystemExit(1)


if __name__ == '__main__':
    run()
