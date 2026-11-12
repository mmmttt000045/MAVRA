"""Key aliases must come from successful execution, with all value/audit gates kept."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import pandas as pd

import harness
from delta_features import HEADER_ATTRIBUTE, cached_headers, remember_headers


class HeaderMetadataTests(unittest.TestCase):
    def test_metadata_preserves_values_and_survives_frame_copy(self):
        frame = pd.DataFrame({'signal': [1., 2.]})
        before = frame.copy()
        remember_headers('SELECT {seeds}', frame, ['Entity ID', 'Time"Alias'])
        pd.testing.assert_frame_equal(frame, before)
        self.assertEqual(cached_headers('SELECT {seeds}', frame, frame.copy()), ['Entity ID', 'Time"Alias'])

    def test_different_sql_or_missing_or_mismatched_metadata_uses_no_cached_names(self):
        train = pd.DataFrame({'signal': [1., 2.]})
        valid = train.copy()
        remember_headers('one', train, ['id', 'when'])
        self.assertIsNone(cached_headers('one', train, valid))
        remember_headers('two', valid, ['id', 'when'])
        self.assertIsNone(cached_headers('one', train, valid))
        remember_headers('one', valid, ['other_id', 'when'])
        self.assertIsNone(cached_headers('one', train, valid))
        remember_headers('one', valid, ['id', 'when'])
        self.assertIsNone(cached_headers('one ', train, valid))

    def test_malformed_header_metadata_is_refused(self):
        frame = pd.DataFrame({'signal': [1., 2.]})
        for keys in (['id'], ['id', 'id'], ['id', None], ['', 'when']):
            with self.subTest(keys=keys), self.assertRaises(ValueError):
                remember_headers('one', frame, keys)
        remember_headers('one', frame, ['id', 'when'])
        frame.attrs[HEADER_ATTRIBUTE]['keys'] = ['id', None]
        self.assertIsNone(cached_headers('one', frame, frame))

    def test_features_records_original_aliases_before_seed_alignment(self):
        seeds = pd.DataFrame({'id': [2, 1], 'seed_time': pd.to_datetime(['2020-01-01'] * 2)})
        raw = pd.DataFrame({'Original ID': [1, 2], 'Original Time': seeds.seed_time, 'signal': [3., 4.]})
        sql = 'SELECT * FROM {seeds}'
        with patch.object(harness, 'read_sql', return_value=(raw, 0.1)):
            result, _ = harness.features('unused', sql, 'seeds', seeds, 'id')
        self.assertEqual(list(result.signal), [4., 3.])
        self.assertEqual(cached_headers(sql, result, result.copy()), ['Original ID', 'Original Time'])


class HeaderToolTests(unittest.TestCase):
    def fixture(self):
        run = harness.Run.__new__(harness.Run)
        run.url, run.arm = 'unused', harness.ARMS['mavra-delta-headers']
        run.tasks = {'t': {'entity_col': 'id'}}
        seeds = pd.DataFrame({'id': [1, 2, 3], 'seed_time': pd.to_datetime(['2020-01-01'] * 3)})
        base_sql, added_sql = 'SELECT base FROM {seeds}', 'SELECT added FROM {seeds}'
        base = pd.DataFrame({'base': [1., 2., 3.]})
        added = pd.DataFrame({'added': [3., 1., 2.]})
        remember_headers(base_sql, base, ['Base ID', 'Base Time'])
        remember_headers(added_sql, added, ['Added ID', 'Added Time'])
        run.check_columns = Mock()
        return SimpleNamespace(run=run, seeds={'train_sample': seeds, 'val': seeds.copy()},
                               base=base, added=added, base_sql=base_sql, added_sql=added_sql)

    def prepare(self, f, read_sql):
        event = {}
        with patch.object(harness, 'features', return_value=(f.added.copy(), 0.1)) as reads, \
             patch.object(harness, 'read_sql', side_effect=read_sql) as headers:
            result = f.run.prepare_delta('t', 2, f.seeds,
                                        (f.base_sql, f.base, f.base.copy(), [('base', 1.)]), f.added_sql, event)
        return result, event, reads, headers

    def test_successful_metadata_removes_only_header_queries(self):
        f = self.fixture()
        (sql, train, valid), event, reads, headers = self.prepare(f, AssertionError('redundant header probe'))
        headers.assert_not_called()
        self.assertEqual(reads.call_count, 2)
        f.run.check_columns.assert_called_once()
        self.assertEqual(f.run.check_columns.call_args.kwargs['timeout_s'], 120)
        self.assertTrue(event['values_reproduced'])
        self.assertEqual([r['source'] for r in event['headers']], ['successful feature query'] * 2)
        self.assertEqual(cached_headers(sql, train, valid), ['Base ID', 'Base Time'])

    def test_join_without_primary_columns_keeps_the_additions_key_names(self):
        f = self.fixture()
        with patch.object(harness, 'MAX_FEATURES', 1):
            (sql, train, valid), event, _, _ = self.prepare(f, AssertionError('redundant header probe'))
        self.assertEqual(list(train), list(event['added_columns'].values()))
        self.assertEqual(cached_headers(sql, train, valid), ['Added ID', 'Added Time'])

    def test_stale_metadata_has_a_counted_fallback_under_the_real_statement_budget(self):
        f = self.fixture()
        remember_headers('stale SQL', f.base, ['Old ID', 'Old Time'])
        def query(*args, **kwargs):
            self.assertEqual(kwargs['timeout_s'], 45)
            return pd.DataFrame(columns=['Base ID', 'Base Time']), 0.2
        _, event, _, headers = self.prepare(f, query)
        self.assertEqual(headers.call_count, 1)
        self.assertEqual(event['headers'][0]['source'], 'SQL probe')
        self.assertAlmostEqual(event['sql_seconds'], 0.4)
        f.run.check_columns.assert_called_once()

    def test_original_arm_retains_the_five_second_probe(self):
        f = self.fixture()
        f.run.arm = harness.ARMS['mavra-delta']
        def query(*args, **kwargs):
            self.assertEqual(kwargs['timeout_s'], 5)
            return pd.DataFrame(columns=['id', 'seed_time']), 0.1
        _, event, _, headers = self.prepare(f, query)
        self.assertEqual(headers.call_count, 2)
        self.assertTrue(all(r['source'] == 'SQL probe' for r in event['headers']))

    def test_new_arm_changes_only_the_private_header_option(self):
        new = dict(harness.ARMS['mavra-delta-headers'])
        self.assertTrue(new.pop('reuse_header_metadata'))
        self.assertEqual(new, harness.ARMS['mavra-delta'])


if __name__ == '__main__':
    unittest.main()
