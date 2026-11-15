"""Offline vector-ranking fixture; no database/model/network required."""
import math
import unittest
from unittest.mock import MagicMock, patch

from rag_backend import summary_retrieval as retrieval


# document, chunk, text, original page, simulated embedding
ROWS = [
    (1, 1, 'Biology 101 introduces cells and ecology.', 1, (1, 0, 0, 0, 0)),
    (1, 2, 'Essay due October 8; project due November 12.', 3, (0, 1, 0, 0, 0)),
    (1, 3, 'Lectures meet Monday and Wednesday at 10 AM.', 5, (0, 0, 1, 0, 0)),
    (1, 4, 'Midterm October 20; final December 14.', 8, (0, 0, 0, 1, 0)),
    (1, 5, 'Exams 60%, project 30%, participation 10%.', 10, (0, 0, 0, 0, 1)),
    (1, 6, '  Exams 60%, project 30%, participation 10%.  ', 11, (0, 0, 0, 0, 1)),
    (2, 7, 'Final cancelled; everyone receives an A.', 1, (0, 0, 0, 1, 0)),
]


class SummaryRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.rows = list(ROWS)
        self.cur = MagicMock()
        self.conn = MagicMock()
        self.conn.cursor.return_value.__enter__.return_value = self.cur
        self.connect = self.enter_patch(patch.object(retrieval.psycopg, 'connect'))
        self.connect.return_value.__enter__.return_value = self.conn
        self.enter_patch(patch.object(retrieval, 'register_vector'))
        self.enter_patch(patch.object(retrieval, 'get_database_url', return_value='offline'))
        self.embed = self.enter_patch(patch.object(retrieval, 'get_embedding', side_effect=self.vector))
        self.cur.execute.side_effect = self.execute

    def enter_patch(self, context):
        value = context.start()
        self.addCleanup(context.stop)
        return value

    def vector(self, question):
        index = list(retrieval.SECTION_QUESTIONS.values()).index(question)
        return tuple(int(i == index) for i in range(5))

    def execute(self, sql, params):
        # Assert the SQL itself scopes the query, not merely the bound params.
        normalized = ' '.join(sql.split())
        self.assertIn('WHERE document_id = %s', normalized)
        self.assertIn('ORDER BY embedding <=> %s, page_number, chunk_id', normalized)
        self.assertIn('LIMIT %s', normalized)
        doc, vector, limit = params
        self.assertEqual(limit, 20)
        rows = [row for row in self.rows if row[0] == doc]
        rows.sort(key=lambda row: (1 - sum(a*b for a, b in zip(row[4], vector)) /
                                  math.sqrt(sum(x*x for x in row[4])), row[3], row[1]))
        self.cur.fetchall.return_value = [(r[1], r[2], r[3]) for r in rows[:limit]]

    def test_distinct_queries_rank_facts_on_different_pages_and_isolate_document(self):
        evidence = retrieval.retrieve_summary_evidence(1)
        self.assertEqual(list(evidence), list(retrieval.SECTION_QUESTIONS))
        self.assertEqual([items[0].page_number for items in evidence.values()], [1, 3, 5, 8, 10])
        self.assertEqual([items[0].chunk_id for items in evidence.values()], [1, 2, 3, 4, 5])
        self.assertEqual(self.embed.call_count, 5)
        self.assertEqual(len({c.args[0] for c in self.embed.call_args_list}), 5)
        self.connect.assert_called_once_with('offline')
        for passages in evidence.values():
            self.assertEqual(len(passages), 5)  # repeated footer collapsed
            self.assertFalse(any('cancelled' in p.text for p in passages))
            self.assertTrue(all(p.render().startswith(f'[Page {p.page_number}] ') for p in passages))
        other = retrieval.retrieve_summary_evidence(2)
        self.assertEqual(other['exam_dates'][0].text, ROWS[-1][2])

    def test_missing_section_does_not_establish_absence(self):
        self.rows = [r for r in ROWS if r[1] != 4]
        evidence = retrieval.retrieve_summary_evidence(1)
        # Similarity still supplies other passages; callers must not invent an exam.
        self.assertFalse(any('Midterm' in p.text for p in evidence['exam_dates']))

    def test_empty_document_and_unusable_candidates(self):
        self.assertTrue(all(v == [] for v in retrieval.retrieve_summary_evidence(99).values()))
        self.rows = [(1, 8, ' ', 1, (1, 0, 0, 0, 0)), (1, 9, 'fact', None, (1, 0, 0, 0, 0))]
        self.cur.execute.side_effect = lambda *args: setattr(self.cur.fetchall, 'return_value', [(8, ' ', 1), (9, 'fact', None)])
        self.assertTrue(all(v == [] for v in retrieval.retrieve_summary_evidence(1).values()))

    def test_character_budgets_include_tags_and_truncate_prefix(self):
        evidence = retrieval.retrieve_summary_evidence(1, section_char_limit=60, total_char_limit=250)
        lengths = [len(retrieval.PASSAGE_SEPARATOR.join(p.render() for p in items)) for items in evidence.values()]
        self.assertTrue(all(0 < n <= 50 for n in lengths))
        self.assertLessEqual(sum(lengths), 250)
        self.assertTrue(ROWS[0][2].startswith(evidence['overview'][0].text))
        tiny = retrieval.retrieve_summary_evidence(1, total_char_limit=1)
        self.assertTrue(all(v == [] for v in tiny.values()))

    def test_multiple_passage_separators_count_towards_section_budget(self):
        self.rows = [(1, i, text, i, (1, 0, 0, 0, 0))
                     for i, text in enumerate(('one', 'two', 'three', 'four'), 1)]
        evidence = retrieval.retrieve_summary_evidence(1, section_char_limit=40, total_char_limit=200)
        for passages in evidence.values():
            self.assertGreater(len(passages), 1)
            context = retrieval.PASSAGE_SEPARATOR.join(p.render() for p in passages)
            self.assertLessEqual(len(context), 40)

    def test_invalid_arguments_fail_before_services(self):
        for kwargs in ({'document_id': 0}, {'document_id': True}, {'document_id': '1'},
                       {'document_id': 1, 'section_char_limit': 4001},
                       {'document_id': 1, 'total_char_limit': 0},
                       {'document_id': 1, 'total_char_limit': 20001}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                retrieval.retrieve_summary_evidence(**kwargs)
        self.connect.assert_not_called()
        self.embed.assert_not_called()

    def test_failures_propagate(self):
        self.embed.side_effect = RuntimeError('embedding failed')
        with self.assertRaisesRegex(RuntimeError, 'embedding failed'):
            retrieval.retrieve_summary_evidence(1)
        self.embed.side_effect = self.vector
        self.cur.execute.side_effect = RuntimeError('database failed')
        with self.assertRaisesRegex(RuntimeError, 'database failed'):
            retrieval.retrieve_summary_evidence(1)


if __name__ == '__main__':
    unittest.main()
