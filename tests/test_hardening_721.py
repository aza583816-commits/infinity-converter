"""Real security regressions; executable with unittest as well as pytest."""
import bz2
from dataclasses import replace
import io
import json
import lzma
import stat
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from config.settings import settings
from core.intelligence import sanitize_context, fallback_plan
from core.storage import TempWorkspace
from core.tooling import TOOLS
from core.tooling.runtime import assert_runtime_coverage
from converters.engine import ConversionEngine
from converters.mega_tools import regex_extract
from converters.validation import validate_output, OutputValidationError
from security.file_guard import validate_upload


class Upload:
    def __init__(self, name, data, mime='application/octet-stream'):
        self.filename, self.mimetype = name, mime
        self.stream = io.BytesIO(data)
    def read(self, n=-1):
        return self.stream.read(n)


def inspect(name, data, mime='application/octet-stream', limit=1024*1024):
    return validate_upload(Upload(name, data, mime), max_bytes=limit, inspect_only=True)


def archive(name='safe.txt', data=b'hello', mode=stat.S_IFREG | 0o600):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        info = zipfile.ZipInfo(name)
        info.external_attr = mode << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, data)
    return stream.getvalue()


class SecurityRegressionTests(unittest.TestCase):
    def test_registry_is_bijective(self):
        coverage = assert_runtime_coverage()
        self.assertTrue(coverage.healthy)
        self.assertEqual(coverage.tools, len(TOOLS))

    def test_empty(self):
        with self.assertRaises(ValueError): inspect('a.txt', b'')

    def test_oversized(self):
        with self.assertRaises(ValueError): inspect('a.txt', b'x'*20, limit=10)

    def test_wrong_signature(self):
        with self.assertRaises(ValueError): inspect('a.pdf', b'hello')

    def test_malformed_pdf(self):
        with self.assertRaises(ValueError): inspect('a.pdf', b'%PDF-1.7\ninvalid')

    def test_mime_mismatch(self):
        with self.assertRaises(ValueError): inspect('a.png', b'text', 'application/pdf')

    def test_bmp_is_not_a_tiff(self):
        stream = io.BytesIO(); Image.new('RGB', (10, 10)).save(stream, 'BMP')
        with self.assertRaises(ValueError): inspect('a.tiff', stream.getvalue())

    def test_image_pixel_limit(self):
        stream = io.BytesIO(); Image.new('RGB', (20, 20)).save(stream, 'PNG')
        with patch('security.file_guard.settings', replace(settings, max_image_pixels=100)):
            with self.assertRaises(ValueError): inspect('a.png', stream.getvalue())

    def test_zip_traversal(self):
        for name in ['../a', 'folder/..', '/a', 'C:/a', 'C:a', 'folder/../../a', '\\server\\a']:
            with self.subTest(name=name), self.assertRaises(ValueError): inspect('a.zip', archive(name))

    def test_zip_special_entries(self):
        for kind in [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR, stat.S_IFBLK, stat.S_IFSOCK]:
            with self.subTest(kind=kind), self.assertRaises(ValueError): inspect('a.zip', archive(mode=kind | 0o600))

    def test_zip_ratio(self):
        with self.assertRaises(ValueError): inspect('a.zip', archive(data=b'0'*200000))

    def test_zip_entry_limit(self):
        with patch('security.file_guard.settings', replace(settings, max_archive_entries=0)):
            with self.assertRaises(ValueError): inspect('a.zip', archive())

    def test_zip_valid(self):
        self.assertTrue(inspect('a.zip', archive())['safe'])

    def test_ooxml_missing_document(self):
        with self.assertRaises(ValueError): inspect('a.docx', archive('[Content_Types].xml', b'<Types/>'))

    def test_doc_signature_only_is_not_valid(self):
        with self.assertRaises(ValueError): inspect('a.doc', b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'+bytes(512))

    def test_truncated_compressed_streams(self):
        for suffix, compress in [('.bz2', bz2.compress), ('.xz', lzma.compress)]:
            with self.subTest(suffix=suffix), self.assertRaises(ValueError): inspect('a'+suffix, compress(b'hello')[:-8])

    def test_concatenated_stream_limit(self):
        for suffix, compress in [('.bz2', bz2.compress), ('.xz', lzma.compress)]:
            with patch('security.file_guard.settings', replace(settings, max_archive_uncompressed_mb=1)):
                with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                    inspect('a'+suffix, compress(b'a')+compress(b'b'*(1024*1024+1)))

    def test_unvalidated_input_cannot_enter_engine(self):
        with TempWorkspace() as ws:
            source=ws.input_dir/'a.txt'; source.write_text('hello')
            with self.assertRaises(ValueError):
                ConversionEngine().convert(tool=TOOLS['file-hash'], safe_inputs=[{'path':source}], workspace=ws, timeout=5, max_pdf_pages=10)

    def test_workspace_cleanup_on_error(self):
        root=None
        try:
            with TempWorkspace() as ws:
                root=ws.path
                (ws.input_dir/'a.txt').write_text('hello')
                raise ValueError('test')
        except ValueError: pass
        self.assertFalse(root.exists())
        ws.cleanup()

    def test_output_image_format(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'a.jpg'; Image.new('RGB',(10,10)).save(path, 'PNG')
            with self.assertRaises(OutputValidationError):
                validate_output(path, expected_extension='.jpg', expected_mime='image/jpeg')

    def test_output_zip_is_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'a.zip'; path.write_bytes(archive(data=b'0'*200000))
            with self.assertRaises(OutputValidationError):
                validate_output(path, expected_extension='.zip', expected_mime='application/zip')

    def test_context_drops_private_and_unknown_data(self):
        clean=sanitize_context({'tool':{'id':'pdf-compress','name':'SECRET'}, 'files':[{'filename':'SECRET.pdf','extension':'.pdf','size_bytes':100}], 'settings':{'password':'SECRET'}, 'error':{'message':'SECRET'}, 'arbitrary':{'payload':'SECRET'}})
        self.assertNotIn('SECRET', json.dumps(clean))
        self.assertEqual(clean['tool']['id'], 'pdf-compress')
        self.assertEqual(clean['files'][0]['extension'], '.pdf')

    def test_context_nonfinite(self):
        self.assertEqual(sanitize_context({'pages':float('nan')}), {})

    def test_fallback_arabic_workflow(self):
        result=fallback_plan('عندي PDF سكان وأبيه Word قابل للتعديل', lang='ar')
        self.assertEqual([s['tool_id'] for s in result['steps']], ['ocr-pdf-to-searchable','pdf-to-docx'])

    def test_regex_capture_groups(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'input.txt'; output=Path(td)/'out.txt'
            source.write_text('AB12 AB34')
            regex_extract(source, output, r'(AB)(\d+)')
            self.assertEqual(output.read_text().splitlines(), ['AB12','AB34'])

    def test_regex_backtracking_deadline(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'input.txt'; output=Path(td)/'out.txt'
            source.write_text('a'*100000+'!')
            start=time.monotonic()
            with self.assertRaises(ValueError): regex_extract(source, output, r'(a|aa)+$')
            self.assertLess(time.monotonic()-start, 6)


if __name__=='__main__':
    unittest.main()
