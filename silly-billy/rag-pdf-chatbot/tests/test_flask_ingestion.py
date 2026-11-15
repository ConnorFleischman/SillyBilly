import io
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
import pymupdf
from rag_backend import database, ingestion
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import app as web


def pdf_bytes(text=True, encrypted=False):
    with pymupdf.open() as pdf:
        pdf.new_page()
        page = pdf.new_page()
        if text:
            page.insert_text((72, 72), 'Course syllabus')
        if encrypted:
            return pdf.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw='owner', user_pw='secret')
        return pdf.tobytes()


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = web.app.test_client()

    def post(self, data, name='Course syllabus.pdf'):
        return self.client.post('/api/summarize', data={'syllabus': (io.BytesIO(data), name)})

    def test_validation_precedes_database(self):
        with patch.object(database.psycopg, 'connect') as connect, patch.object(database, 'get_database_url') as config:
            for data, status in [(b'bad', 400), (b'%PDF-broken', 400), (pdf_bytes(False), 422), (pdf_bytes(encrypted=True), 422)]:
                self.assertEqual(self.post(data).status_code, status)
            self.assertEqual(self.post(pdf_bytes(), 'x.txt').status_code, 400)
            connect.assert_not_called()
            config.assert_not_called()

    def test_indexing_identity_duplicate_and_retry(self):
        data = pdf_bytes()
        paths = []
        def store(path, original_filename, prepared_chunks):
            paths.append(path)
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(original_filename, 'Course syllabus.pdf')
            self.assertEqual({c['page'] for c in prepared_chunks}, {2})
            return 42
        with patch.object(ingestion, 'store_pdf', side_effect=store), patch.object(web, 'summarize_syllabus', side_effect=RuntimeError("private-key")) as summary:
            for _ in range(2):
                response = self.post(data)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn('private-key', response.get_data(as_text=True))
            self.assertEqual(summary.call_args.args, (42,))
        def fail(path, **kwargs):
            paths.append(path)
            raise RuntimeError('postgres://secret')
        with patch.object(ingestion, 'store_pdf', side_effect=fail):
            response = self.post(data)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('secret', response.get_data(as_text=True))
        with patch.object(ingestion, 'store_pdf', side_effect=store), patch.object(web, 'summarize_syllabus', side_effect=RuntimeError):
            self.assertEqual(self.post(data).status_code, 503)
        self.assertTrue(all(not p.parent.exists() for p in paths))

    def test_size_limits(self):
        data = pdf_bytes()
        with patch.object(ingestion, 'MAX_PDF_BYTES', len(data)), patch.object(ingestion, 'store_pdf', return_value=42), patch.object(web, 'summarize_syllabus', side_effect=RuntimeError):
            self.assertEqual(self.post(data).status_code, 503)
            self.assertEqual(self.post(data + b'x').status_code, 413)
        with patch.dict(web.app.config, MAX_CONTENT_LENGTH=128):
            response = self.post(data)
            self.assertEqual(response.status_code, 413)
            self.assertIsNotNone(response.json)

    def test_prepared_chunks_skip_reparsing_and_embed(self):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        cur = conn.cursor.return_value.__enter__.return_value
        cur.fetchone.side_effect = [None, (42,)]
        with patch.object(database, 'calculate_file_hash', return_value='hash'), patch.object(database, 'get_database_url', return_value='fixture'), patch.object(database.psycopg, 'connect', return_value=conn), patch.object(database, 'register_vector'), patch.object(database, 'chunk_pdf') as parse, patch.object(database, 'get_embedding', return_value=[0.1]) as embed:
            self.assertEqual(database.store_pdf('fixture.pdf', prepared_chunks=[{'page': 2, 'text': 'course'}]), 42)
            parse.assert_not_called()
            embed.assert_called_once_with('course')
            self.assertEqual(cur.execute.call_args.args[1], (42, 2, 'course', [0.1]))
