"""Offline upload lifecycle and transaction-exit coverage, not live atomicity."""
import io
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from rag_backend import database, ingestion


class UploadTests(unittest.TestCase):
    def test_short_reads_preserve_all_bytes_and_enforce_total_limit(self):
        class ShortStream(io.BytesIO):
            def read(self, size=-1):
                return super().read(min(size, 3))

        payload = b'%PDF-complete fixture'
        source = ShortStream(payload)
        stored = []

        def store(path, original_filename):
            stored.append(path.read_bytes())
            return 42

        with patch.object(ingestion, 'store_pdf', side_effect=store):
            self.assertEqual(ingestion.ingest_pdf(source, 'report.pdf'), 42)
        self.assertEqual(stored, [payload])
        self.assertFalse(source.closed)
        for size in (12, 13):
            with self.subTest(size=size), patch.object(ingestion, 'MAX_PDF_BYTES', 12), patch.object(
                ingestion, 'store_pdf', side_effect=store
            ) as storage:
                source = ShortStream(b'%PDF-' + b'x' * (size - 5))
                if size == 12:
                    self.assertEqual(ingestion.ingest_pdf(source, 'report.pdf'), 42)
                    self.assertEqual(len(stored[-1]), size)
                else:
                    with self.assertRaisesRegex(ValueError, 'limit'):
                        ingestion.ingest_pdf(source, 'report.pdf')
                    storage.assert_not_called()
                self.assertFalse(source.closed)

    def test_cleanup_and_identity_for_new_duplicate_and_failed_storage(self):
        for result in (42, 17, RuntimeError('storage failed')):
            with self.subTest(result=result):
                paths = []

                def store(path, original_filename):
                    paths.append(path)
                    self.assertTrue(path.is_file())
                    self.assertEqual(path.read_bytes(), b'%PDF-fixture')
                    self.assertEqual(original_filename, 'My syllabus.pdf')
                    if isinstance(result, Exception):
                        raise result
                    return result

                with patch.object(ingestion, 'store_pdf', side_effect=store):
                    if isinstance(result, Exception):
                        with self.assertRaisesRegex(RuntimeError, 'storage failed'):
                            ingestion.ingest_pdf(b'%PDF-fixture', '../folder\\My syllabus.pdf')
                    else:
                        self.assertEqual(ingestion.ingest_pdf(b'%PDF-fixture', '../folder\\My syllabus.pdf'), result)
                self.assertFalse(paths[0].exists())
                self.assertFalse(paths[0].parent.exists())

    def test_partial_write_failure_removes_temporary_directory(self):
        paths = []
        write = Path.write_bytes

        def fail(path, data):
            paths.append(path)
            write(path, data[:3])
            raise OSError('disk full')

        with patch.object(Path, 'write_bytes', fail), patch.object(ingestion, 'store_pdf') as store:
            with self.assertRaisesRegex(OSError, 'disk full'):
                ingestion.ingest_pdf(b'%PDF-fixture', 'report.pdf')
        store.assert_not_called()
        self.assertFalse(paths[0].parent.exists())

    def test_stream_read_is_bounded_and_caller_retains_ownership(self):
        stream = io.BytesIO(b'%PDF-fixture')
        with patch.object(ingestion, 'store_pdf', return_value=42):
            self.assertEqual(ingestion.ingest_pdf(stream, 'report.pdf'), 42)
        self.assertFalse(stream.closed)
        source = MagicMock()
        source.read.return_value = b'x' * (ingestion.MAX_PDF_BYTES + 1)
        with patch.object(ingestion, 'store_pdf') as store:
            with self.assertRaisesRegex(ValueError, 'limit'):
                ingestion.ingest_pdf(source, 'report.pdf')
        source.read.assert_called_once_with(ingestion.MAX_PDF_BYTES + 1)
        store.assert_not_called()

    def test_invalid_inputs_never_reach_storage(self):
        for data, name in ((b'', 'report.pdf'), (b'not pdf', 'report.pdf'), (b'%PDF-', '..'), (b'%PDF-', 'bad\x00.pdf')):
            with self.subTest(name=name), patch.object(ingestion, 'store_pdf') as store:
                with self.assertRaises(ValueError):
                    ingestion.ingest_pdf(data, name)
                store.assert_not_called()


class TransactionExitTests(unittest.TestCase):
    def test_success_and_failures_reach_connection_context(self):
        chunks = [{'page': 1, 'text': 'one'}, {'page': 3, 'text': 'two'}]
        for stage in ('success', 'extraction', 'textless', 'embedding', 'insert'):
            with self.subTest(stage=stage):
                conn = MagicMock()
                conn.__enter__.return_value = conn
                cur = conn.cursor.return_value
                cur.__enter__.return_value = cur
                cur.fetchone.side_effect = [None, (42,)]
                failure = RuntimeError(stage)
                if stage == 'insert':
                    cur.execute.side_effect = [None, None, None, failure]
                with patch.object(database, 'calculate_file_hash', return_value='hash'), patch.object(
                    database, 'get_database_url', return_value='fixture'
                ), patch.object(database.psycopg, 'connect', return_value=conn), patch.object(
                    database, 'register_vector'
                ), patch.object(database, 'chunk_pdf', side_effect=failure if stage == 'extraction' else None,
                                return_value=[] if stage == 'textless' else chunks), patch.object(
                    database, 'get_embedding', side_effect=[[0.1], failure] if stage == 'embedding' else [[0.1], [0.2]]
                ):
                    if stage == 'success':
                        self.assertEqual(database.store_pdf('fixture.pdf'), 42)
                        conn.__exit__.assert_called_once_with(None, None, None)
                        self.assertEqual(cur.execute.call_count, 4)
                    else:
                        with self.assertRaises(ValueError if stage == 'textless' else RuntimeError):
                            database.store_pdf('fixture.pdf')
                        self.assertIs(conn.__exit__.call_args.args[0], ValueError if stage == 'textless' else RuntimeError)
                        conn.commit.assert_not_called()
                        if stage in ('embedding', 'insert'):
                            self.assertEqual(cur.execute.call_args_list[2].args[1], (42, 1, 'one', [0.1]))
