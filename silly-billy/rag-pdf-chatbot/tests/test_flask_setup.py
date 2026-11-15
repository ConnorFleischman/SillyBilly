"""Verify the installed backend and Flask app coexist without live services."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FlaskSetupTests(unittest.TestCase):
    def test_flask_routes_with_installed_backend(self):
        code = r'''
import importlib, io, sys
from unittest.mock import patch
import psycopg
import pymupdf
with patch.object(psycopg, 'connect', side_effect=AssertionError('unexpected DB')):
    for name in ('database', 'retrieval', 'generation', 'embeddings'):
        importlib.import_module('rag_backend.' + name)
    sys.path.insert(0, sys.argv[1])
    from app import app
    client = app.test_client()
    assert client.get('/').status_code == 200
    assert client.get('/app.js').status_code == 200
    assert client.post('/api/summarize').status_code == 400
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), 'Course syllabus fixture')
        data = pdf.tobytes()
    with patch('app.ingest_pdf', return_value=42):
        response = client.post('/api/summarize', data={'syllabus': (io.BytesIO(data), 'course.pdf')})
    assert response.status_code == 501, response.data
assert 'sentence_transformers' not in sys.modules
assert 'google.genai' not in sys.modules
'''
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run([sys.executable, '-c', code, str(ROOT.parent)],
                           cwd=directory, check=True)

class DotenvPrecedenceTests(unittest.TestCase):
    def test_process_then_src_then_project(self):
        import os
        from unittest.mock import patch
        from rag_backend import database_config, generation

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'src/rag_backend').mkdir(parents=True)
            (root / '.env').write_text('DATABASE_URL=postgresql://project\nGEMINI_API_KEY=project\nGEMINI_MODEL=project\n')
            source = root / 'src/.env'
            source.write_text('DATABASE_URL=postgresql://src\nGEMINI_API_KEY=src\nGEMINI_MODEL=src\n')
            with patch.object(database_config, '__file__', str(root / 'src/rag_backend/database_config.py')), patch.object(generation, '__file__', str(root / 'src/rag_backend/generation.py')):
                for env, expected in [({}, 'src'), ({'DATABASE_URL': 'postgresql://process', 'GEMINI_API_KEY': 'process', 'GEMINI_MODEL': 'process'}, 'process')]:
                    with patch.dict(os.environ, env, clear=True):
                        self.assertEqual(database_config.get_database_url(), 'postgresql://' + expected)
                        self.assertEqual(generation.get_gemini_config(), (expected, expected))
                source.unlink()
                with patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(database_config.get_database_url(), 'postgresql://project')
                    self.assertEqual(generation.get_gemini_config(), ('project', 'project'))
