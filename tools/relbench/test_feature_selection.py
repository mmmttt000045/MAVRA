"""Check selection direction, fallback, feature alignment and fit budgets."""
import unittest

import numpy as np
import pandas as pd

from feature_selection import complementary_pool, select_subset, select_union


class FeatureSelectionTests(unittest.TestCase):
    def setUp(self):
        self.x = pd.DataFrame(np.arange(240).reshape(6, 40), columns=[f"f{i}" for i in range(40)])
        self.y = pd.Series([0, 1, 0, 1, 0, 1])
        self.imp = [(c, 100 - i) for i, c in enumerate(self.x)]
        self.calls = []

    def fit(self, xt, yt, xv):
        self.calls.append(list(xt.columns))
        self.assertEqual(list(xt.columns), list(xv.columns))
        self.assertEqual(list(yt), list(self.y))
        return np.zeros(len(xv)), [], 0.01

    def select(self, values, higher=True, baseline=0.8, **kwargs):
        it = iter(values)
        return select_subset(self.x, self.y, self.x, self.y, self.imp, baseline,
                             higher, self.fit, lambda y, p: next(it), **kwargs)

    def test_auc_keeps_incumbent_when_pruning_hurts(self):
        result = self.select([0.7, 0.79])
        self.assertEqual(result["chosen"]["columns"], list(self.x))
        self.assertEqual(result["fits"], 2)

    def test_mae_minimizes_instead_of_maximizing(self):
        result = self.select([9.0, 8.0], higher=False, baseline=10.0)
        self.assertEqual(result["chosen"]["val"], 8.0)
        self.assertEqual(len(result["chosen"]["columns"]), 32)

    def test_tiny_auc_changes_do_not_replace_the_incumbent(self):
        result = self.select([0.8001, 0.8004])
        self.assertEqual(result["chosen"]["name"], "unchanged")

    def test_expired_budget_does_not_start_a_fit(self):
        result = self.select([], budget_seconds=0)
        self.assertEqual(result["fits"], 0)
        self.assertEqual(self.calls, [])

    def test_incompatible_feature_order_is_rejected(self):
        with self.assertRaises(ValueError):
            select_subset(self.x, self.y, self.x.iloc[:, ::-1], self.y, self.imp,
                          0.8, True, self.fit, lambda y, p: 0.9)


class ComplementaryFeaturesTests(unittest.TestCase):
    def setUp(self):
        self.p = pd.DataFrame({"a": [1., 2., 3.], "b": [2., 3., 4.]})
        self.s = pd.DataFrame({"copy": [1., 2., 3.], "new": [9., 8., 7.]})

    def test_equal_values_are_deduplicated_across_different_names(self):
        xt, xv, names, duplicates = complementary_pool(self.p, self.p, self.s, self.s, [("copy", 10), ("new", 5)])
        self.assertEqual(duplicates, ["copy"])
        self.assertEqual(set(names), {"new"})
        self.assertEqual(list(xt), list(xv))
        self.assertTrue(xt[names["new"]].equals(self.s["new"]))

    def test_training_duplicates_that_diverge_on_validation_are_retained(self):
        val = self.s.copy()
        val.loc[0, "copy"] = 100
        _, _, names, duplicates = complementary_pool(self.p, self.p, self.s, val, [("copy", 10)])
        self.assertIn("copy", names)
        self.assertEqual(duplicates, [])

    def test_alternate_pool_respects_the_column_budget(self):
        xt, _, names, _ = complementary_pool(self.p, self.p, self.s, self.s, [("new", 5)], max_extra=0)
        self.assertEqual(list(xt), list(self.p))
        self.assertEqual(names, {})

    def test_misaligned_seed_order_is_rejected(self):
        with self.assertRaises(ValueError):
            complementary_pool(self.p, self.p, self.s.iloc[::-1], self.s, [("new", 5)])

    def test_union_keeps_the_single_attempt_if_validation_does_not_improve(self):
        x = self.p.assign(extra=[4., 6., 5.])
        y = pd.Series([0, 1, 0])
        calls = []

        def fit(xt, yt, xv):
            calls.append(list(xt))
            return np.full(len(xv), 0.7), [(c, 1) for c in xt], 0.01

        result = select_union(x, y, x, y, list(self.p), 0.8, True, fit, lambda y, p: p[0])
        self.assertEqual(result["chosen"]["name"], "single_attempt")
        self.assertLessEqual(result["fits"], 4)
        self.assertTrue(calls)

    def test_union_can_add_a_complementary_signal_without_exceeding_the_limit(self):
        x = self.p.assign(signal=[4., 6., 5.])
        y = pd.Series([0, 1, 0])

        def fit(xt, yt, xv):
            return np.full(len(xv), 0.9 if "signal" in xt else 0.7), [(c, 1) for c in xt], 0.01

        result = select_union(x, y, x, y, list(self.p), 0.8, True, fit, lambda y, p: p[0], max_features=3)
        self.assertGreater(result["chosen"]["val"], 0.8)
        self.assertIn("signal", result["chosen"]["columns"])
        self.assertLessEqual(len(result["chosen"]["columns"]), 3)


if __name__ == "__main__":
    unittest.main()
