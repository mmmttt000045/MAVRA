"""Compiler guards for outcome availability; real value checks are opt-in."""
import unittest

from outcome_history import compile_history_features, interval_sql, relation


class HistoryCompilerTests(unittest.TestCase):
    def test_horizon_is_strictly_positive_integer_microseconds(self):
        for invalid in (0, -1, True, 1.5, '1 day', None):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                interval_sql(invalid)
        self.assertEqual(interval_sql(1), "INTERVAL '1 microseconds'")

    def test_identifiers_are_quoted_and_cannot_terminate_the_source(self):
        self.assertEqual(relation('task', 'x";select'), '"task"."x"";select"')
        with self.assertRaises(ValueError):
            relation('task', 'x\x00')

    def test_only_training_source_is_used_and_no_label_generation_query_is_needed(self):
        sql = compile_history_features('task', 't_train', 'id', 'label', 86400000000)
        self.assertIn('FROM "task"."t_train"', sql)
        self.assertIn('h.available_at<=s.seed_time', sql)
        self.assertNotIn('s."label"', sql)
        self.assertNotIn('_val', sql)
        self.assertNotIn('_test', sql)


if __name__ == '__main__':
    unittest.main()
