"""Check selection direction, fallback, feature alignment and fit budgets."""
import unittest

import numpy as np
import pandas as pd

from feature_selection import select_subset


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


if __name__ == "__main__":
    unittest.main()
