"""An empty-information default cannot prematurely end feature engineering."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

import harness


class SignalStartTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        (Path(self.tmp.name) / 'sessions').mkdir()
        self.run = harness.Run.__new__(harness.Run)
        self.run.arm = harness.ARMS['mavra-signal']
        self.run.a = SimpleNamespace(arm='mavra-signal', run=1, out=self.tmp.name)
        self.run.url = 'unused'
        self.run.tasks = {'t': {'entity_col': 'id', 'entity_table': 'entities', 'target_col': 'label',
                                'task_type': 'regression', 'cutoffs': [{'test_timestamp': '2020-01-01'},
                                                                      {'test_timestamp': '2020-02-01'}]}}
        self.run.targets = {('t', 1): {'val': None}}
        self.run.incumbent_frames = {}
        self.run.incumbent_work = {}
        self.run.gmem = self.run.tecod = self.run.asm = None
        self.run.llm = Mock()
        self.run.llm.history.side_effect = lambda m: {'role': 'assistant', **m}
        self.seeds = {key: pd.DataFrame({'id': [1, 2, 3, 4], 'seed_time': pd.to_datetime(['2020-01-01']*4),
                                         'label': [0., 1., 0., 1.]}) for key in ('train_sample', 'val')}
        self.constant = pd.DataFrame({'constant': [1.] * 4})
        self.signal = pd.DataFrame({'events': [0., 1., 2., 3.]})
        self.sql = 'SELECT id, seed_time, 1 AS constant FROM {seeds}'
        self.agent_sql = 'SELECT id, seed_time, events FROM {seeds}'
        self.middle = Mock()
        self.middle.call.return_value = {}

    @staticmethod
    def response(name=None, sql=None):
        args = {'sql': sql} if sql else {}
        return {'message': {'content': '', 'tool_calls': [] if name is None else [
            {'id': 'tool', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}}

    def explore(self, reference=None, reference_audit='clean', agent_score=0.5):
        reference = self.constant if reference is None else reference
        def query(url, sql, *args, **kw):
            return (reference if sql == self.sql else self.signal).copy(), 0.01
        def fit(kind, xt, yt, xv):
            return np.zeros(len(xv)), [(c, 1.) for c in xt], 0.01
        with patch.object(self.run, 'system_prompt', return_value='fixed learner and original contract'), \
             patch.object(self.run, 'select_start', return_value=None), \
             patch.object(self.run, 'reference_sql', return_value=self.sql), \
             patch.object(harness, 'features', side_effect=query), \
             patch.object(harness, 'train_predict', side_effect=fit), \
             patch.object(harness, 'score', side_effect=[0.1, agent_score]), \
             patch.object(self.run, 'audit', side_effect=lambda t, k, sql, seeds: {
                 'result': reference_audit if sql == self.sql else 'clean'}):
            return self.run.explore('t', 1, self.seeds, self.middle)

    def test_clean_engineered_candidate_can_replace_a_better_scoring_constant_default(self):
        self.run.llm.chat.side_effect = [self.response('validate_features', self.agent_sql), self.response('submit')]
        st = self.explore()
        self.assertEqual(st['rec']['final_sql'], self.agent_sql)
        self.assertEqual(st['rec']['best_val'], 0.5)
        self.assertTrue(st['rec']['validations'][0]['improved'])
        self.assertNotIn('goal_reached', st['rec'])
        self.assertTrue(st['rec']['memory_reference']['fallback_only'])
        self.assertEqual([x['purpose'] for x in st['rec']['feature_fits']], ['reference_start', 'agent_validation'])
        prompt = st['msgs'][1]['content']
        self.assertNotIn(self.sql, prompt)
        self.assertNotIn('MAE=0.10000', prompt)

    def test_no_clean_engineering_still_returns_the_checked_fallback(self):
        self.run.llm.chat.side_effect = [self.response(), self.response(), self.response()]
        st = self.explore()
        self.assertEqual(st['rec']['final_sql'], self.sql)
        self.assertEqual(st['rec']['final_source'], 'checked_constant_fallback')
        self.assertEqual(st['rec']['best_val'], 0.1)
        self.assertGreater(st['rec']['agent_seconds'], 0)
        self.assertEqual(len(st['rec']['feature_fits']), 1)

    def test_audit_error_cannot_supply_an_emergency_default(self):
        self.run.llm.chat.side_effect = [self.response(), self.response(), self.response()]
        st = self.explore(reference_audit='error')
        self.assertIsNone(st['rec']['final_sql'])
        self.assertNotIn('used_checked_fallback', st['rec'])

    def test_informative_reference_keeps_original_validation_selection(self):
        self.run.llm.chat.side_effect = [self.response('validate_features', self.agent_sql), self.response('submit')]
        st = self.explore(reference=self.signal)
        self.assertEqual(st['rec']['final_sql'], self.sql)
        self.assertEqual(st['rec']['best_val'], 0.1)
        self.assertFalse(st['rec']['validations'][0]['improved'])

    def test_parent_arm_keeps_constant_as_its_original_best(self):
        self.run.arm = harness.ARMS['mavra-cached']
        self.run.llm.chat.side_effect = [self.response('validate_features', self.agent_sql), self.response('submit')]
        st = self.explore()
        self.assertEqual(st['rec']['final_sql'], self.sql)
        self.assertNotIn('fallback_only', st['rec']['memory_reference'])

    def test_cached_constant_is_not_a_goal_and_needs_no_duplicate_reference_query(self):
        self.run.prev_sql = {'t': (1, self.sql)}
        def fit(kind, xt, yt, xv):
            return np.zeros(len(xv)), [('constant', 0.)], 0.01
        with patch.object(harness, 'features', return_value=(self.constant, 25.)), \
             patch.object(harness, 'train_predict', side_effect=fit), \
             patch.object(self.run, 'audit', return_value={'result': 'clean'}):
            target = self.run.incumbent('t', 2, self.seeds)
        self.assertIsNone(target['val'])
        self.assertTrue(target['fallback_only'])
        self.run.targets[('t', 2)] = target
        self.run.llm.chat.side_effect = [self.response(), self.response(), self.response()]
        with patch.object(self.run, 'system_prompt', return_value='no score goal'), \
             patch.object(harness, 'features', side_effect=AssertionError('duplicate reference query')):
            st = self.run.explore('t', 2, self.seeds, self.middle)
        self.assertEqual(st['rec']['final_sql'], self.sql)
        self.assertEqual(st['rec']['final_source'], 'checked_constant_fallback')
        self.assertNotIn('goal_reached', st['rec'])
        self.assertNotIn('memory_reference', st['rec'])
        self.assertIn('charged_current_refit', st['rec'])

    def test_missing_only_defaults_and_mixed_missing_signal(self):
        self.assertFalse(self.run.start_is_informative(pd.DataFrame({'a': [np.nan]*4})))
        self.assertFalse(self.run.start_is_informative(self.constant))
        self.assertTrue(self.run.start_is_informative(pd.DataFrame({'a': [np.nan, 1., 1., 1.]})))


if __name__ == '__main__':
    unittest.main()
