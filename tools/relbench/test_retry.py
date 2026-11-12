"""Unit tests for v10 refit timeout retry behavior."""
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import harness


class BaseRefitFixture(unittest.TestCase):
    def setUp(self):
        self.run = harness.Run.__new__(harness.Run)
        self.run.arm = harness.ARMS["mavra-retry"]
        self.run.url = "unused"
        self.run.tasks = {"t": {"entity_col": "id", "target_col": "y", "task_type": "binary_classification"}}
        self.run.prev_sql = {"t": (1, "SELECT id, seed_time, 1.0 AS f0 FROM {seeds}")}
        self.run.incumbent_cache = {}
        self.run.incumbent_frames = {}
        self.run.incumbent_work = {}
        self.run.refit_inputs = {}
        seeds = pd.DataFrame({"id": [1, 2, 3, 4], "seed_time": pd.to_datetime(["2020-06-01"] * 4), "y": [0, 1, 0, 1]})
        self.seeds = {"train_sample": seeds.copy(), "val": seeds.copy()}
        self.values = pd.DataFrame({"f0": [0.1, 0.9, 0.2, 0.8]})

    def fit(self, task_type, xt, yt, xv):
        return np.array([0.0, 1.0, 0.0, 1.0]), [("f0", 10.0)], 0.01


class RefitRetryTests(BaseRefitFixture):
    def refit(self, effects):
        with patch.object(harness, "features", side_effect=effects) as query, \
             patch.object(harness, "train_predict", side_effect=self.fit), \
             patch.object(self.run, "audit", return_value={"result": "clean"}), \
             patch.object(harness, "score", return_value=1.0):
            goal = self.run.incumbent("t", 2, self.seeds)
        return goal, [c.kwargs.get("timeout_s") for c in query.call_args_list]

    def test_timeout_is_retried_once_under_the_standard_limit(self):
        goal, limits = self.refit([harness.FeatureError("statement timeout"), (self.values, 30.0), (self.values, 20.0)])
        self.assertEqual(goal["val"], 1.0)
        self.assertTrue(goal["current_refit_retained"])
        self.assertEqual(limits, [45, harness.FEATURE_SQL_TIMEOUT_S, harness.FEATURE_SQL_TIMEOUT_S])
        work = self.run.incumbent_work[("t", 2)]
        self.assertEqual(work["attempt_timeouts"], [45, harness.FEATURE_SQL_TIMEOUT_S])
        self.assertGreater(work["seconds"], 0.0)

    def test_second_timeout_gives_up_as_before(self):
        goal, limits = self.refit(harness.FeatureError("statement timeout"))
        self.assertIsNone(goal["val"])
        self.assertEqual(goal["attempts"], 2)
        self.assertEqual(limits, [45, harness.FEATURE_SQL_TIMEOUT_S])

    def test_other_errors_are_not_retried(self):
        goal, limits = self.refit(harness.FeatureError('column "x" does not exist'))
        self.assertIsNone(goal["val"])
        self.assertEqual(goal["attempts"], 1)
        self.assertEqual(limits, [45])

    def test_only_the_retry_differs_from_v9(self):
        v9, v10 = harness.ARMS["mavra-delta-headers"], harness.ARMS["mavra-retry"]
        changed = {k for k in set(v9) | set(v10) if v9.get(k) != v10.get(k)}
        self.assertEqual(changed, {"current_refit_attempts", "current_refit_retry_timeout"})
        self.assertEqual(v9["current_refit_attempts"], 1)


if __name__ == "__main__":
    unittest.main()
