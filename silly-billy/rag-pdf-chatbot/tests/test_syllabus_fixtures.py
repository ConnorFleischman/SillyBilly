"""Real text-PDF fixture contracts; no DB, embeddings, provider or semantic mocks."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from rag_backend.chunk import chunk_pdf
from rag_backend.python_reader import extract_text
from rag_backend.summary_generation import SUMMARY_FIELDS, _validate_response
from rag_backend.summary_retrieval import EvidencePassage

FIXTURES = Path(__file__).resolve().parents[3] / 'tests' / 'fixtures'


class SyllabusFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = json.loads((FIXTURES / 'manifest.json').read_text(encoding='utf-8'))['documents']
        cls.source = json.loads((FIXTURES / 'syllabi.json').read_text(encoding='utf-8'))['documents']

    def test_committed_pdfs_extract_all_source_text_on_original_pages(self):
        for document, source in zip(self.documents, self.source):
            with self.subTest(document=document['id']):
                self.assertEqual(document['id'], source['id'])
                pages = extract_text(FIXTURES / document['pdf'])
                self.assertEqual(list(pages), list(range(1, document['page_count'] + 1)))
                self.assertEqual(len(source['pages']), len(pages))
                for page, lines in enumerate(source['pages'], 1):
                    self.assertEqual(' '.join(pages[page].split()), ' '.join(' '.join(lines).split()))
                self.assertEqual([p for p,t in pages.items() if not t.strip()], document['blank_pages'])

    def test_real_chunks_preserve_page_identity_and_cover_expected_facts(self):
        for document in self.documents:
            path = FIXTURES / document['pdf']
            pages = extract_text(path)
            chunks = chunk_pdf(path)
            self.assertEqual({c['page'] for c in chunks}, {p for p,t in pages.items() if t.strip()})
            for chunk in chunks:
                self.assertIn(chunk['text'], pages[chunk['page']])
            for facts in document['expected_facts'].values():
                for fact in facts:
                    self.assertIn(fact['text'], pages[fact['page']])
                    self.assertTrue(any(fact['text'] in c['text'] and c['page'] == fact['page'] for c in chunks))

    def test_expected_facts_and_canonical_citations(self):
        for document in self.documents:
            self.assertEqual(set(document['expected_facts']), set(SUMMARY_FIELDS))
            self.assertEqual(document['missing_sections'], [f for f in SUMMARY_FIELDS if not document['expected_facts'][f]])
            evidence = {}
            for field, facts in document['expected_facts'].items():
                self.assertEqual(document['canonical_summary'][field],
                                 [f"{f['text']} [Page {f['page']}]" for f in facts])
                pages = extract_text(FIXTURES / document['pdf'])
                evidence[field] = [EvidencePassage(i+1, f['page'], pages[f['page']]) for i,f in enumerate(facts)]
            self.assertEqual(_validate_response(json.dumps(document['canonical_summary']), evidence), document['canonical_summary'])

    def test_missing_sections_are_absent_and_conflicting_documents_stay_distinct(self):
        by_id = {d['id']: d for d in self.documents}
        missing_text = '\n'.join(extract_text(FIXTURES / by_id['missing']['pdf']).values()).lower()
        self.assertEqual(by_id['missing']['missing_sections'], ['due_dates', 'exam_dates', 'grading'])
        for word in ('deadline', 'due ', 'exam', 'midterm', 'grading', '%'):
            self.assertNotIn(word, missing_text)
        complete = by_id['complete']
        alternate = by_id['conflicting']
        for left, right in ((complete, alternate), (alternate, complete)):
            other_text = '\n'.join(extract_text(FIXTURES / right['pdf']).values())
            for field in SUMMARY_FIELDS:
                for fact in left['expected_facts'][field]:
                    self.assertNotIn(fact['text'], other_text)
        self.assertIn('October 7, 2030', complete['expected_facts']['due_dates'][0]['text'])
        self.assertIn('October 21, 2030', alternate['expected_facts']['due_dates'][0]['text'])

    def test_regeneration_preserves_extracted_content(self):
        spec = importlib.util.spec_from_file_location('fixture_generator', FIXTURES / 'generate.py')
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        with tempfile.TemporaryDirectory() as folder:
            generator.generate(folder)
            for document in self.documents:
                self.assertEqual(extract_text(Path(folder) / document['pdf']),
                                 extract_text(FIXTURES / document['pdf']))
