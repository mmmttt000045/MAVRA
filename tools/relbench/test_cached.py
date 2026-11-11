"""A clean current refit survives a tighter later timeout, with full cost records."""
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import harness


class CurrentRefitTests(unittest.TestCase):
    def setUp(self):
        self.run = harness.Run.__new__(harness.Run)
        self.run.arm = harness.ARMS['mavra-cached']
        self.run.url = 'unused'
        self.sql = 'select id, seed_time, good, other from {seeds}'
        self.run.prev_sql = {'t': (1, self.sql)}
        self.run.incumbent_frames = {}
        self.run.incumbent_work = {}
        self.run.tasks = {'t': {'entity_col': 'id', 'target_col': 'label', 'task_type': 'binary_classification',
                                'cutoffs': [{'test_timestamp': '2020-01-01'}, {'test_timestamp': '2020-02-01'}]}}
        sample = pd.DataFrame({'id': [1, 2, 3, 4], 'seed_time': pd.to_datetime(['2020-01-01'] * 4), 'label': [0, 1, 0, 1]})
        self.seeds = {'train_sample': sample.copy(), 'val': sample.copy()}
        self.values = pd.DataFrame({'good': [0., 1., 0., 1.], 'other': [9., 8., 1., 2.]})

    def fit(self, task_type, xt, yt, xv):
        return np.array([0., 1., 0., 1.])[:len(xv)], [(c, 1.) for c in xt], 0.01

    def prepare(self, audit='clean'):
        with patch.object(harness, 'features', return_value=(self.values, 25.)) as query, \
             patch.object(harness, 'train_predict', side_effect=self.fit), \
             patch.object(self.run, 'audit', return_value={'result': audit, 'why': 'audit failed'}):
            goal = self.run.incumbent('t', 2, self.seeds)
        self.assertEqual(query.call_count, 2)
        return goal

    def test_reuses_exact_current_values_without_a_second_sql_or_fit(self):
        goal = self.prepare()
        self.assertEqual(goal['val'], 1.)
        self.assertTrue(goal['charged_to_session'])
        cached = self.run.current_incumbent('t', 2, self.seeds)
        with patch.object(harness, 'features', side_effect=AssertionError('duplicate SQL')), \
             patch.object(harness, 'train_predict', side_effect=AssertionError('duplicate fit')):
            start = self.run.select_start('t', 2, self.seeds, {'program_sql': self.sql}, {}, None, 'a', 's')
        self.assertEqual(start['chosen']['sql'], self.sql)
        self.assertEqual(start['chosen']['val'], goal['val'])
        self.assertEqual(start['_frames'][1].to_dict(), cached['train'].to_dict())
        self.assertTrue(start['pruning_closed'])
        self.assertEqual(len(self.run.incumbent_work[('t', 2)]['feature_fits']), 1)

    def test_cache_is_bound_to_task_cutoff_sql_and_complete_seed_rows(self):
        self.prepare()
        self.assertIsNone(self.run.current_incumbent('t', 3, self.seeds))
        reordered = {key: frame.iloc[::-1] for key, frame in self.seeds.items()}
        self.assertIsNone(self.run.current_incumbent('t', 2, reordered))
        relabelled = {key: frame.copy() for key, frame in self.seeds.items()}
        relabelled['val'].loc[0, 'label'] = 1
        self.assertIsNone(self.run.current_incumbent('t', 2, relabelled))
        self.run.prev_sql['t'] = (1, self.sql + ' changed')
        self.assertIsNone(self.run.current_incumbent('t', 2, self.seeds))

    def test_unknown_or_failed_audit_is_never_a_cached_candidate(self):
        for status in ('error', 'unknown'):
            with self.subTest(status=status):
                self.assertIsNone(self.prepare(status)['val'])
                self.assertIsNone(self.run.current_incumbent('t', 2, self.seeds))
                self.assertFalse(self.run.incumbent_work[('t', 2)]['cached'])

    def test_failed_preflight_attempts_remain_charged_when_no_cache_exists(self):
        with patch.object(harness, 'features', side_effect=harness.FeatureError('statement timeout')) as query:
            goal = self.run.incumbent('t', 2, self.seeds)
        self.assertEqual(query.call_count, 2)
        self.assertIsNone(goal['val'])
        work = self.run.incumbent_work[('t', 2)]
        self.assertGreater(work['seconds'], 0.)
        self.assertEqual(work['agent_seconds'], work['seconds'] - work['audit_seconds'])
        self.assertFalse(work['cached'])

    def test_projection_failure_keeps_the_complete_audited_incumbent(self):
        self.prepare()
        self.run.incumbent_work[('t', 2)]['sql_seconds'] = 1.
        cached = self.run.current_incumbent('t', 2, self.seeds)
        cached['val'] = 0.8
        selected = {'chosen': {'columns': ['good'], 'val': 0.9, 'importance': [('good', 1.)]},
                    'trials': [], 'train_seconds': 0., 'seconds': 0., 'fits': 0}
        with patch('feature_selection.select_subset', return_value=selected), \
             patch.object(harness, 'read_sql', return_value=(pd.DataFrame(columns=['id', 'seed_time']), 0.)), \
             patch.object(self.run, 'check_columns'), patch.object(self.run, 'audit', return_value={'result': 'error'}):
            start = self.run.cached_start('t', 2, self.seeds, cached)
        self.assertEqual(start['chosen']['sql'], self.sql)
        self.assertEqual(start['projection_rejected'], 'error')

    def test_all_preflight_work_is_charged_exactly_once_and_cache_is_freed(self):
        self.prepare()
        work = self.run.incumbent_work[('t', 2)]
        record = {'agent_seconds': 5., 'feature_fits': []}
        self.run.charge_incumbent_work('t', 2, record)
        self.assertAlmostEqual(record['agent_seconds'], 5. + work['agent_seconds'])
        self.assertEqual(len(record['feature_fits']), 1)
        self.assertNotIn(('t', 2), self.run.incumbent_frames)
        charged = record['agent_seconds']
        self.run.charge_incumbent_work('t', 2, record)
        self.assertEqual(record['agent_seconds'], charged)
        self.assertEqual(len(record['feature_fits']), 1)


if __name__ == '__main__':
    unittest.main()
