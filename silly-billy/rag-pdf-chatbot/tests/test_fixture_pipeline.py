"""Fixture Flask regression with real parsing/chunking/validation; controlled ranking."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from rag_backend import ingestion, summary_generation
from rag_backend.summary_retrieval import EvidencePassage

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import app as web

FIXTURES = Path(__file__).resolve().parents[3] / 'tests/fixtures'


class FixturePipelineTests(unittest.TestCase):
    def test_conflicts_missing_sections_failure_and_duplicate_retry(self):
        documents = json.loads((FIXTURES / 'manifest.json').read_text())['documents']
        stored, paths, identities = {}, [], []

        def store(path, original_filename, prepared_chunks):
            paths.append(path)
            data = path.read_bytes()
            if data not in stored:
                stored[data] = (len(stored)+1, prepared_chunks)
            identity, chunks = stored[data]
            identities.append(identity)
            return identity

        def retrieve(identity):
            chunks = next(chunks for key, chunks in stored.values() if key == identity)
            return {field: [EvidencePassage(i+1, c['page'], c['text'])
                            for i, c in enumerate(chunks)]
                    for field in summary_generation.SUMMARY_FIELDS}

        def provider(contents, **kwargs):
            envelope = json.loads(contents)
            document = documents[envelope['document_id']-1]
            prompt = json.dumps(envelope)
            for facts in document['expected_facts'].values():
                for fact in facts:
                    self.assertIn(fact['text'], prompt)
            for other in documents:
                if other['id'] != document['id']:
                    for facts in other['expected_facts'].values():
                        for fact in facts:
                            self.assertNotIn(fact['text'], prompt)
            return json.dumps(document['canonical_summary'])

        with patch.object(ingestion, 'store_pdf', side_effect=store), patch(
                'rag_backend.summary_retrieval.retrieve_summary_evidence', side_effect=retrieve), patch.object(
                summary_generation, 'request_gemini_text', side_effect=provider) as generate:
            client = web.app.test_client()

            def post(document):
                return client.post('/api/summarize?document_id=999', data={
                    'syllabus': (io.BytesIO((FIXTURES / document['pdf']).read_bytes()), document['pdf'])})

            for document in documents:
                response = post(document)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json, document['canonical_summary'])
                for field in document['missing_sections']:
                    self.assertEqual(response.json[field], [])
            generate.side_effect = RuntimeError('private document postgres://password')
            failure = post(documents[0])
            self.assertEqual(failure.status_code, 503)
            self.assertNotIn('private', failure.get_data(as_text=True))
            generate.side_effect = provider
            self.assertEqual(post(documents[0]).json, documents[0]['canonical_summary'])
            self.assertEqual(identities, [1, 2, 3, 1, 1])
            self.assertEqual(generate.call_count, 5)
        self.assertTrue(all(not path.parent.exists() for path in paths))
