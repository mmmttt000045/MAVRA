"""A complementary union is admitted only after SQL reproduction and an audit."""
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import harness
from feature_selection import select_union


class ColdPortfolioTests(unittest.TestCase):
    def setUp(self):
        self.run = harness.Run.__new__(harness.Run)
        self.run.arm = harness.ARMS["mavra-portfolio"]
        self.run.url = "unused"
        self.run.tasks = {"t": {"target_col": "label", "task_type": "binary_classification"}}
        self.p = pd.DataFrame({"a": [1., 2., 3.], "b": [2., 4., 1.]})
        self.s = pd.DataFrame({"c": [9., 8., 7.]})
        self.seeds = {"train_sample": pd.DataFrame({"label": [0, 1, 0]}),
                      "val": pd.DataFrame({"label": [0, 1, 0]})}
        self.primary = {"rec": {"final_sql": "select id,seed_time,a,b from {seeds}", "best_val": 0.8,
                                 "higher_is_better": True, "validations": [], "agent_seconds": 0., "audit_seconds": 0.},
                        "frames": ("select id,seed_time,a,b from {seeds}", self.p, self.p, [("a", 2), ("b", 1)])}
        self.other = {"rec": {"final_sql": "select id,seed_time,c from {seeds}", "best_val": 0.7, "attempt": 2},
                      "frames": ("select id,seed_time,c from {seeds}", self.s, self.s, [("c", 1)])}

    def fit(self, task_type, xt, yt, xv):
        return np.full(len(xv), 0.9), [(c, 1.) for c in xt], 0.001

    def call(self, audit):
        with patch.object(harness, "train_predict", side_effect=self.fit), \
             patch.object(harness, "score", return_value=0.9), \
             patch.object(harness, "read_sql", return_value=(pd.DataFrame(columns=["id", "seed_time"]), 0.)), \
             patch.object(self.run, "audit", return_value={"result": audit}), \
             patch.object(self.run, "evaluate", side_effect=AssertionError("test evaluation must not run")):
            self.run.combine_cold_start("t", 1, self.seeds, self.primary, [self.other])

    def test_successful_union_is_checked_before_replacing_the_single_attempt(self):
        with patch.object(self.run, "check_columns") as reproduce:
            self.call("clean")
        rec = self.primary["rec"]
        reproduce.assert_called_once()
        self.assertTrue(rec["memory_union"]["accepted"])
        self.assertIn("mem_program", rec["final_sql"])
        self.assertIn("p2_0_c", rec["final_sql"])
        self.assertGreater(rec["best_val"], 0.8)
        self.assertEqual(rec["memory_union"]["primary_before"]["val"], 0.8)

    def test_leaking_union_keeps_the_original_candidate(self):
        with patch.object(self.run, "check_columns"):
            self.call("leak")
        self.assertEqual(self.primary["rec"]["best_val"], 0.8)
        self.assertNotIn("accepted", self.primary["rec"]["memory_union"])
        self.assertIn("rejected", self.primary["rec"]["memory_union"])

    def test_reproduction_failure_keeps_the_original_candidate(self):
        with patch.object(self.run, "check_columns", side_effect=harness.FeatureError("different values")):
            self.call("clean")
        self.assertEqual(self.primary["rec"]["best_val"], 0.8)
        self.assertIn("different values", self.primary["rec"]["memory_union"]["error"])


class FixedLearnerComplementTests(unittest.TestCase):
    def test_complementary_signal_improves_with_the_unchanged_learner(self):
        rng = np.random.RandomState(1729)
        train = pd.DataFrame(rng.normal(size=(1200, 3)), columns=["a", "noise", "b"])
        valid = pd.DataFrame(rng.normal(size=(400, 3)), columns=train.columns)
        yt = (train.a + train.b + rng.normal(scale=0.2, size=len(train)) > 0).astype(int)
        yv = (valid.a + valid.b + rng.normal(scale=0.2, size=len(valid)) > 0).astype(int)
        predict, _, _ = harness.train_predict("binary_classification", train[["a", "noise"]], yt, valid[["a", "noise"]])
        incumbent = harness.score("binary_classification", yv, predict)
        selected = select_union(train, yt, valid, yv, ["a", "noise"], incumbent, True,
                                lambda a, b, c: harness.train_predict("binary_classification", a, b, c),
                                lambda y, p: harness.score("binary_classification", y, p), max_features=2)
        self.assertGreater(selected["chosen"]["val"], incumbent + 0.04)
        self.assertIn("b", selected["chosen"]["columns"])
        self.assertLessEqual(len(selected["chosen"]["columns"]), 2)


class CheckedProjectionTests(unittest.TestCase):
    def setUp(self):
        self.run = harness.Run.__new__(harness.Run)
        self.run.arm = harness.ARMS["mavra-portfolio"]
        self.run.url = "unused"
        self.run.tasks = {"t": {"target_col": "label", "task_type": "binary_classification"}}
        self.x = pd.DataFrame({"good": [1., 2., 3.], "bad": [9., 8., 7.]})
        self.seeds = {"train_sample": pd.DataFrame({"label": [0, 1, 0]}),
                      "val": pd.DataFrame({"label": [0, 1, 0]})}
        self.sql = "select id,seed_time,good,bad from {seeds}"
        self.leak = {"result": "leak", "all_columns_differing": ["bad"]}

    def test_only_explicit_bad_outputs_are_removed_and_the_projection_is_reaudited(self):
        with patch.object(harness, "read_sql", return_value=(pd.DataFrame(columns=["id", "seed_time"]), 0.)), \
             patch.object(self.run, "check_columns") as reproduce, \
             patch.object(self.run, "audit", return_value={"result": "clean"}) as audit, \
             patch.object(harness, "train_predict", return_value=(np.zeros(3), [("good", 1.)], 0.01)) as fit, \
             patch.object(harness, "score", return_value=0.8):
            event, repaired = self.run.sanitize_candidate("t", 1, self.seeds, self.sql, self.x, self.x, self.leak)
        self.assertTrue(event["accepted"])
        self.assertEqual(event["removed_columns"], ["bad"])
        self.assertEqual(list(repaired[1]), ["good"])
        self.assertEqual(list(fit.call_args.args[1]), ["good"])
        reproduce.assert_called_once()
        audit.assert_called_once()

    def test_an_error_in_the_fresh_audit_does_not_grant_use(self):
        with patch.object(harness, "read_sql", return_value=(pd.DataFrame(columns=["id", "seed_time"]), 0.)), \
             patch.object(self.run, "check_columns"), \
             patch.object(self.run, "audit", return_value={"result": "error"}), \
             patch.object(harness, "train_predict") as fit:
            event, repaired = self.run.sanitize_candidate("t", 1, self.seeds, self.sql, self.x, self.x, self.leak)
        self.assertFalse(event["accepted"])
        self.assertIsNone(repaired)
        fit.assert_not_called()

    def test_unknown_original_audit_cannot_be_repaired_by_guessing_columns(self):
        with patch.object(harness, "read_sql") as query:
            event, repaired = self.run.sanitize_candidate("t", 1, self.seeds, self.sql, self.x, self.x, {"result": "error"})
        self.assertIsNone(event)
        self.assertIsNone(repaired)
        query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
