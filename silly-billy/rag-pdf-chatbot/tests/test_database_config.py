"""Run with: py -m unittest discover -s tests -v (from rag-pdf-chatbot)."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


config = load_module("database_config", ROOT / "src/database_config.py")


class ConfigurationTests(unittest.TestCase):
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
        vector = types.ModuleType("pgvector.psycopg")
        vector.register_vector = MagicMock()
        embeddings = types.ModuleType("embeddings")
        embeddings.get_embedding = MagicMock(return_value=[0.1, 0.2])
        chunk = types.ModuleType("chunk")
        chunk.chunk_pdf = MagicMock(return_value=[{"page": 1, "text": "text"}])
        chunk.all_chunks = []
        self.modules = patch.dict(sys.modules, {
            "database_config": config, "psycopg": self.driver,
            "pgvector": types.ModuleType("pgvector"), "pgvector.psycopg": vector,
            "embeddings": embeddings, "chunk": chunk,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.env = patch.dict(os.environ, {"DATABASE_URL": "postgresql://test/db"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_store_existing_document_uses_shared_url_and_returns_id(self):
        module = load_module("database_under_test", ROOT / "src/database.py")
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "sample.pdf"
            pdf.write_bytes(b"sample PDF bytes")
            self.assertEqual(module.store_pdf(pdf), 42)
        self.driver.connect.assert_called_once_with("postgresql://test/db")

    def test_retrieval_preserves_document_filter_and_results(self):
        module = load_module("retrieval_under_test", ROOT / "src/retrieval.py")
        self.assertEqual(module.retrieve_chunks("question", 42), [("matching text", 3)])
        self.driver.connect.assert_called_once_with("postgresql://test/db")
        self.assertEqual(self.cur.execute.call_args.args[1], (42, [0.1, 0.2]))

    def test_missing_configuration_does_not_connect(self):
        module = load_module("retrieval_under_test", ROOT / "src/retrieval.py")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "DATABASE_URL"):
                module.retrieve_chunks("question", 42)
        self.driver.connect.assert_not_called()

    def test_examples_use_same_configuration(self):
        load_module("database_demo_under_test", ROOT / "examples/database_demo.py")
        self.driver.connect.assert_called_once_with("postgresql://test/db")
        self.driver.connect.reset_mock()
        module = load_module("retrieval_demo_under_test", ROOT / "examples/retrieval_demo.py")
        self.assertEqual(module.retrieve_chunks("question"), [("matching text", 3)])
        self.driver.connect.assert_called_once_with("postgresql://test/db")


if __name__ == "__main__":
    unittest.main()
