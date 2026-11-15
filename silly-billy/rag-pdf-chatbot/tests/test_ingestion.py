"""Offline filename and page identity ingestion coverage."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

import pymupdf
from rag_backend import database, python_reader
from rag_backend.chunk import chunk_pages, chunk_pdf


class IngestionTests(unittest.TestCase):
    def make_pdf(self, path, texts):
        with pymupdf.open() as pdf:
            for text in texts:
                page = pdf.new_page()
                if text:
                    page.insert_text((72, 72), text)
            pdf.save(path)

    def test_real_pdf_retains_empty_pages_and_original_page_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'temporary.pdf'
            self.make_pdf(path, ['First page', '', 'Third page'])
            pages = python_reader.extract_text(path)
            self.assertEqual(pages, {1: 'First page\n', 2: '', 3: 'Third page\n'})
            self.assertEqual(chunk_pdf(path), [
                {'page': 1, 'text': 'First page\n'},
                {'page': 3, 'text': 'Third page\n'},
            ])

    def test_chunk_mapping_preserves_nonconsecutive_identity_and_boundaries(self):
        self.assertEqual(chunk_pages({4: 'abcdef', 7: ' \n', 12: 'xyz'}, 4, 1), [
            {'page': 4, 'text': 'abcd'}, {'page': 4, 'text': 'def'},
            {'page': 12, 'text': 'xyz'},
        ])

    def test_extraction_closes_document_on_page_failure(self):
        doc = MagicMock()
        doc.__enter__.return_value = doc
        page = MagicMock()
        page.get_text.side_effect = RuntimeError('extraction failed')
        doc.__iter__.return_value = iter([page])
        with patch.object(python_reader.pymupdf, 'open', return_value=doc):
            with self.assertRaisesRegex(RuntimeError, 'extraction failed'):
                python_reader.extract_text('unused.pdf')
        doc.__exit__.assert_called_once()

    def test_new_document_persists_filename_pages_text_and_embeddings(self):
        for original in (None, 'Original upload.pdf'):
            with self.subTest(original=original), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'tmp123.pdf'
                self.make_pdf(path, ['First page', '', 'Third page'])
                conn = MagicMock()
                conn.__enter__.return_value = conn
                cur = conn.cursor.return_value
                cur.__enter__.return_value = cur
                cur.fetchone.side_effect = [None, (42,)]
                with patch.object(database.psycopg, 'connect', return_value=conn), patch.object(
                    database, 'get_database_url', return_value='postgresql://fixture'
                ), patch.object(database, 'register_vector'), patch.object(
                    database, 'get_embedding', side_effect=[[0.1], [0.2]]
                ) as embed:
                    result = (database.store_pdf(path) if original is None else
                              database.store_pdf(path, original_filename=original))
                    self.assertEqual(result, 42)
                statements = cur.execute.call_args_list
                self.assertEqual(len(statements), 4)
                self.assertIn('INSERT INTO documents', statements[1].args[0])
                self.assertEqual(statements[1].args[1], (
                    original if original is not None else path.name,
                    database.calculate_file_hash(path),
                ))
                self.assertEqual(statements[2].args[1], (42, 1, 'First page\n', [0.1]))
                self.assertEqual(statements[3].args[1], (42, 3, 'Third page\n', [0.2]))
                self.assertIn('page_number, text, embedding', statements[2].args[0])
                self.assertEqual(embed.call_args_list, [call('First page\n'), call('Third page\n')])

    def test_blank_pdf_is_rejected_before_insert_or_embedding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'blank.pdf'
            self.make_pdf(path, ['', ''])
            conn = MagicMock()
            conn.__enter__.return_value = conn
            cur = conn.cursor.return_value
            cur.__enter__.return_value = cur
            cur.fetchone.return_value = None
            with patch.object(database.psycopg, 'connect', return_value=conn), patch.object(
                database, 'get_database_url', return_value='postgresql://fixture'
            ), patch.object(database, 'register_vector'), patch.object(database, 'get_embedding') as embed:
                with self.assertRaisesRegex(ValueError, 'No text extracted'):
                    database.store_pdf(path)
            self.assertEqual(cur.execute.call_count, 1)
            embed.assert_not_called()

    def test_existing_document_keeps_metadata_without_extracting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'temporary.pdf'
            path.write_bytes(b'existing content')
            conn = MagicMock()
            conn.__enter__.return_value = conn
            cur = conn.cursor.return_value
            cur.__enter__.return_value = cur
            cur.fetchone.return_value = (17,)
            with patch.object(database.psycopg, 'connect', return_value=conn), patch.object(
                database, 'get_database_url', return_value='postgresql://fixture'
            ), patch.object(database, 'register_vector'), patch.object(database, 'chunk_pdf') as chunks:
                self.assertEqual(database.store_pdf(path, original_filename='Another name.pdf'), 17)
            self.assertEqual(cur.execute.call_count, 1)
            chunks.assert_not_called()
