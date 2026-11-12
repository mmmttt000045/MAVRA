"""v10: a refit cut by the short limit is retried once under the standard limit; nothing else changes."""
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import harness
import test_cached


class RefitRetryTests(test_cached.CurrentRefitTests):
    def setUp(self):
        super().setUp()
        self.run.arm = harness.ARMS['mavra-retry']
        self.run.refit_inputs = {}

    def refit(self, effects):
        with patch.object(harness, 'features', side_effect=effects) as query, \
             patch.object(harness, 'train_predict', side_effect=self.fit), \
             patch.object(self.run, 'audit', return_value={'result': 'clean'}):
            goal = self.run.incumbent('t', 2, self.seeds)
        return goal, [c.kwargs.get('timeout_s') for c in query.call_args_list]

    def test_timeout_is_retried_once_under_the_standard_limit(self):
        goal, limits = self.refit([harness.FeatureError('statement timeout'), (self.values, 30.), (self.values, 20.)])
        self.assertEqual(goal['val'], 1.)
        self.assertTrue(goal['current_refit_retained'])
        self.assertEqual(limits, [45, harness.FEATURE_SQL_TIMEOUT_S, harness.FEATURE_SQL_TIMEOUT_S])
        work = self.run.incumbent_work[('t', 2)]
        self.assertEqual(work['attempt_timeouts'], [45, harness.FEATURE_SQL_TIMEOUT_S])
        self.assertGreater(work['seconds'], 0.)  # the failed first attempt stays charged to the session

    def test_second_timeout_gives_up_as_before(self):
        goal, limits = self.refit(harness.FeatureError('statement timeout'))
        self.assertIsNone(goal['val'])
        self.assertEqual(goal['attempts'], 2)
        self.assertEqual(limits, [45, harness.FEATURE_SQL_TIMEOUT_S])

    def test_other_errors_are_not_retried(self):
        goal, limits = self.refit(harness.FeatureError('column "x" does not exist'))
        self.assertIsNone(goal['val'])
        self.assertEqual(goal['attempts'], 1)
        self.assertEqual(limits, [45])

    def test_only_the_retry_differs_from_v9(self):
        v9, v10 = harness.ARMS['mavra-delta-headers'], harness.ARMS['mavra-retry']
        changed = {k for k in set(v9) | set(v10) if v9.get(k) != v10.get(k)}
        self.assertEqual(changed, {'current_refit_attempts', 'current_refit_retry_timeout'})
        self.assertEqual(v9['current_refit_attempts'], 1)


class V9UnchangedTests(test_cached.CurrentRefitTests):
    def test_v9_still_tries_once_at_45_seconds(self):
        self.run.arm = harness.ARMS['mavra-delta-headers']
        self.run.refit_inputs = {}
        with patch.object(harness, 'features', side_effect=harness.FeatureError('statement timeout')) as query:
            goal = self.run.incumbent('t', 2, self.seeds)
        self.assertEqual(goal['attempts'], 1)
        self.assertEqual([c.kwargs.get('timeout_s') for c in query.call_args_list], [45])


if __name__ == '__main__':
    unittest.main()
