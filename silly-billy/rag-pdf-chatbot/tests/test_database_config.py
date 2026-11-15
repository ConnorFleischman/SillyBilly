"""Run with: py -m unittest discover -s tests -v (from rag-pdf-chatbot)."""
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from rag_backend import database_config as config
from rag_backend import database, retrieval


class ConfigurationTests(unittest.TestCase):
    def test_dotenv_database_url_is_loaded_before_connecting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src/rag_backend").mkdir(parents=True)
            for location in (root / ".env", root / "src/.env"):
                with self.subTest(location=location):
                    location.write_text("DATABASE_URL=postgresql://fixture/local\n", encoding="utf-8")
                    with patch.dict(os.environ, {}, clear=True), patch.object(
                        config, "__file__", str(root / "src/rag_backend/database_config.py")
                    ):
                        self.assertEqual(config.get_database_url(), "postgresql://fixture/local")
                    location.unlink()

    def test_missing_empty_and_whitespace_have_actionable_error(self):
        for env in ({}, {"DATABASE_URL": ""}, {"DATABASE_URL": "  "}):
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(ValueError, "DATABASE_URL.*postgresql://"):
                    config.get_database_url()

    def test_url_is_preserved_and_environment_is_read_each_time(self):
        urls = [
            "postgresql://alice:p%40ss@db:5433/custom?sslmode=require",
            "postgresql:///local_db",
        ]
        with patch.dict(os.environ, {}, clear=True):
            for url in urls:
                os.environ["DATABASE_URL"] = url
                self.assertEqual(config.get_database_url(), url)


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.driver = types.ModuleType("psycopg")
        self.driver.connect = MagicMock()
        self.conn = self.driver.connect.return_value
        self.conn.__enter__.return_value = self.conn
        self.cur = self.conn.cursor.return_value
        self.cur.__enter__.return_value = self.cur
        self.cur.fetchone.return_value = (42,)
        self.cur.fetchall.return_value = [("matching text", 3)]
        for context in (
            patch.object(database.psycopg, "connect", self.driver.connect),
            patch.object(database, "register_vector"),
            patch.object(retrieval, "register_vector"),
            patch.object(retrieval, "get_embedding", return_value=[0.1, 0.2]),
            patch.object(database, "get_embedding", return_value=[0.1, 0.2]),
            patch.object(database, "chunk_pdf", return_value=[{"page": 1, "text": "text"}]),
        ):
            context.start()
            self.addCleanup(context.stop)
        self.env = patch.dict(os.environ, {"DATABASE_URL": "postgresql://test/db"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_store_existing_document_uses_shared_url_and_returns_id(self):
        module = database
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "sample.pdf"
            pdf.write_bytes(b"sample PDF bytes")
            self.assertEqual(module.store_pdf(pdf), 42)
        self.driver.connect.assert_called_once_with("postgresql://test/db")

    def test_retrieval_preserves_document_filter_and_results(self):
        module = retrieval
        self.assertEqual(module.retrieve_chunks("question", 42), [("matching text", 3)])
        self.driver.connect.assert_called_once_with("postgresql://test/db")
        self.assertEqual(self.cur.execute.call_args.args[1], (42, [0.1, 0.2]))

    def test_missing_configuration_does_not_connect(self):
        module = retrieval
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "DATABASE_URL"):
                module.retrieve_chunks("question", 42)
        self.driver.connect.assert_not_called()



if __name__ == "__main__":
    unittest.main()
