import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from rag_backend import embeddings, generation

ROOT = Path(__file__).resolve().parents[1]


class PackageTests(unittest.TestCase):
    def test_pdf_extraction_and_chunking_pipeline(self):
        import pymupdf
        from rag_backend.chunk import chunk_pdf
        from rag_backend.python_reader import extract_text

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.pdf'
            with pymupdf.open() as pdf:
                page = pdf.new_page()
                page.insert_text((72, 72), 'A shared backend fixture.')
                pdf.save(path)
            self.assertIn('shared backend fixture', extract_text(path)[1])
            self.assertEqual(chunk_pdf(path), [{'page': 1, 'text': extract_text(path)[1]}])

    def test_embedding_model_is_lazy_cached_and_schema_compatible(self):
        embeddings._get_model.cache_clear()
        self.addCleanup(embeddings._get_model.cache_clear)
        provider = types.ModuleType('sentence_transformers')
        provider.SentenceTransformer = MagicMock()
        provider.SentenceTransformer.return_value.encode.return_value = [0.0] * 384
        with patch.dict(sys.modules, {'sentence_transformers': provider}):
            self.assertEqual(len(embeddings.get_embedding('one')), embeddings.EMBEDDING_DIMENSIONS)
            embeddings.get_embedding('two')
        provider.SentenceTransformer.assert_called_once_with('all-MiniLM-L6-v2')

    def test_real_gemini_dotenv_loader_retains_both_locations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'src/rag_backend').mkdir(parents=True)
            for location in (root / 'src/.env', root / '.env'):
                with self.subTest(location=location):
                    location.write_text('GEMINI_API_KEY=fixture-key\nGEMINI_MODEL=fixture-model\n')
                    with patch.dict(os.environ, {}, clear=True), patch.object(generation, '__file__', str(root / 'src/rag_backend/generation.py')):
                        self.assertEqual(generation.get_gemini_config(), ('fixture-key', 'fixture-model'))
                    location.unlink()
