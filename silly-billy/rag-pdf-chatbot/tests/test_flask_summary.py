"""Offline Flask-to-generation integration using real PDF parsing and validation."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pymupdf
from rag_backend import ingestion, summary_generation
from rag_backend.summary_retrieval import EvidencePassage

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import app as web
import summarize as bridge


class FlaskSummaryTests(unittest.TestCase):
    def setUp(self):
        self.client = web.app.test_client()
        with pymupdf.open() as pdf:
            pdf.new_page()  # Preserve physical page identity across a blank page.
            pdf.new_page().insert_text((72, 72), 'Biology 101. Final December 14.')
            self.pdf = pdf.tobytes()
        self.empty = {field: [] for field in summary_generation.SUMMARY_FIELDS}
        self.evidence = dict(self.empty, overview=[EvidencePassage(10, 2, 'Biology 101.')],
                             exam_dates=[EvidencePassage(11, 2, 'Final December 14.')])
        self.result = dict(self.empty, overview=['Biology 101. [Page 2]'],
                           exam_dates=['Final December 14. [Page 2]'])
        self.paths = []

        def store(path, original_filename, prepared_chunks):
            self.paths.append(path)
            self.assertEqual(path.read_bytes(), self.pdf)
            self.assertEqual({chunk['page'] for chunk in prepared_chunks}, {2})
            return 42

        self.storage = self.enter(patch.object(ingestion, 'store_pdf', side_effect=store))
        self.retrieval = self.enter(patch('rag_backend.summary_retrieval.retrieve_summary_evidence',
                                          return_value=self.evidence))
        self.provider = self.enter(patch.object(summary_generation, 'request_gemini_text',
                                                return_value=json.dumps(self.result)))

    def enter(self, context):
        result = context.start()
        self.addCleanup(context.stop)
        return result

    def post(self):
        return self.client.post('/api/summarize?document_id=999', data={
            'syllabus': (io.BytesIO(self.pdf), 'course.pdf'), 'document_id': '999'})

    def test_generated_facts_missing_sections_and_server_identity(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, self.result)
        self.retrieval.assert_called_once_with(42)
        envelope = json.loads(self.provider.call_args.args[0])
        self.assertEqual(envelope['document_id'], 42)
        self.assertEqual(envelope['section_evidence']['overview'], '[Page 2] Biology 101.')
        self.assertTrue(all(not path.parent.exists() for path in self.paths))

    def test_valid_all_empty_with_and_without_evidence(self):
        self.provider.return_value = json.dumps(self.empty)
        self.assertEqual(self.post().json, self.empty)
        self.assertEqual(self.post().status_code, 200)
        self.provider.reset_mock()
        self.retrieval.return_value = self.empty
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, self.empty)
        self.provider.assert_not_called()

    def test_invalid_generation_then_retry_uses_storage_identity(self):
        # Actual validation rejects a citation to a page absent from the evidence.
        invalid = dict(self.result, overview=['Biology 101. [Page 999]'])
        self.provider.side_effect = [json.dumps(invalid), json.dumps(self.result)]
        response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.post().json, self.result)
        self.assertEqual([call.args for call in self.retrieval.call_args_list], [(42,), (42,)])
        self.assertTrue(all(not path.parent.exists() for path in self.paths))

    def test_provider_and_retrieval_exceptions_are_safe_json(self):
        for boundary in (self.provider, self.retrieval):
            with self.subTest(boundary=boundary):
                boundary.side_effect = RuntimeError('private-key postgres://password PDF text')
                response = self.post()
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json, {
                    'error': 'Summary generation is unavailable. Please try again later.'})
                boundary.side_effect = None

    def test_bridge_forwards_id_and_preserves_result_and_failure(self):
        with patch.object(bridge, 'generate_syllabus_summary', return_value=self.result) as generate:
            self.assertIs(bridge.summarize_syllabus(42), self.result)
            generate.assert_called_once_with(42)
            error = RuntimeError('fixture')
            generate.side_effect = error
            with self.assertRaises(RuntimeError) as caught:
                bridge.summarize_syllabus(42)
            self.assertIs(caught.exception, error)
