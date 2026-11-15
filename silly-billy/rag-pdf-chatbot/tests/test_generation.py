import builtins
import importlib
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from rag_backend import generation
SOURCE = Path(generation.__file__)


def load():
    return importlib.reload(generation)

class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.module = load()
        self.dotenv = types.ModuleType('dotenv')
        self.dotenv.load_dotenv = MagicMock()
        self.retrieval = types.ModuleType('rag_backend.retrieval')
        self.retrieval.retrieve_chunks = MagicMock(return_value=[('PDF fact', 7)])
        self.genai = MagicMock()
        self.client = self.genai.Client.return_value.__enter__.return_value
        self.client.models.generate_content.return_value.text = 'Answer (page 7)'
        google = types.ModuleType('google')
        google.genai = self.genai
        for context in (patch.dict(sys.modules, {'dotenv': self.dotenv, 'rag_backend.retrieval': self.retrieval, 'google': google}),
                        patch.dict(os.environ, {'GEMINI_API_KEY': 'secret'}, clear=True)):
            context.start()
            self.addCleanup(context.stop)

    def test_import_without_credentials_or_heavy_dependencies(self):
        original = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name.split('.')[0] in {'google', 'dotenv', 'retrieval', 'embeddings', 'sentence_transformers', 'psycopg'}:
                raise AssertionError('Unexpected import: ' + name)
            return original(name, *args, **kwargs)
        with patch.dict(os.environ, {}, clear=True), patch('builtins.__import__', side_effect=guarded):
            load()

    def test_missing_and_blank_keys(self):
        for env in ({}, {'GEMINI_API_KEY': ''}, {'GEMINI_API_KEY': '  '}):
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(ValueError, 'GEMINI_API_KEY is required.*environment'):
                    self.module.generate_answer('question', 42)
        self.genai.Client.assert_not_called()

    def test_default_and_blank_model(self):
        self.assertEqual(self.module.get_gemini_config(), ('secret', 'gemini-3.5-flash-lite'))
        for value in ('', '  '):
            with patch.dict(os.environ, {'GEMINI_MODEL': value}):
                with self.assertRaisesRegex(ValueError, 'GEMINI_MODEL must be nonblank'):
                    self.module.generate_answer('question', 42)
        self.genai.Client.assert_not_called()

    def test_configured_generation_and_environment_refresh(self):
        for key, model in [(' secret ', ' custom-model '), ('new-key', 'new-model')]:
            os.environ.update(GEMINI_API_KEY=key, GEMINI_MODEL=model)
            self.assertEqual(self.module.generate_answer('What fact?', 42), 'Answer (page 7)')
            self.assertEqual(self.genai.Client.call_args.kwargs, {'api_key': key.strip()})
            self.retrieval.retrieve_chunks.assert_called_with('What fact?', 42)
            call = self.client.models.generate_content.call_args.kwargs
            self.assertEqual(call['model'], model.strip())
            for text in ('What fact?', 'Page 7: PDF fact', 'using only the PDF context', 'page numbers'):
                self.assertIn(text, call['contents'])
        paths = [c.args[0] for c in self.dotenv.load_dotenv.call_args_list]
        self.assertEqual(paths[:2], [SOURCE.parents[1] / '.env', SOURCE.parents[2] / '.env'])
        self.assertTrue(all(not c.kwargs.get('override', False) for c in self.dotenv.load_dotenv.call_args_list))
        self.assertEqual(self.genai.Client.return_value.__exit__.call_count, 2)

    def test_no_chunks_skips_configuration(self):
        os.environ.clear()
        self.retrieval.retrieve_chunks.return_value = []
        self.assertEqual(self.module.generate_answer('question', 9), 'No relevant PDF content was found for this document.')
        self.dotenv.load_dotenv.assert_not_called()
        self.genai.Client.assert_not_called()

    def test_provider_errors_are_secret_safe(self):
        for target in (self.genai.Client, self.client.models.generate_content):
            target.side_effect = RuntimeError('request key=secret')
            with self.assertRaisesRegex(RuntimeError, 'Check GEMINI_API_KEY, GEMINI_MODEL') as caught:
                self.module.generate_answer('question', 42)
            self.assertNotIn('secret', str(caught.exception))
            self.assertTrue(caught.exception.__suppress_context__)
            target.side_effect = None

if __name__ == '__main__':
    unittest.main()
