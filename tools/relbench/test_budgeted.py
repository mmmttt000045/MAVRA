"""Exercise bounded memory selection without PostgreSQL or model requests."""
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import harness


class BudgetedStartTests(unittest.TestCase):
    def setUp(self):
        self.run = harness.Run.__new__(harness.Run)
        self.run.arm = harness.ARMS["mavra-budgeted"]
        self.run.url = "unused"
        self.run.tasks = {"task": {"entity_col": "id", "target_col": "label", "task_type": "binary_classification"}}
        self.x = pd.DataFrame(np.arange(240).reshape(6, 40), columns=[f"f{i}" for i in range(40)])
        labels = pd.DataFrame({"id": range(6), "seed_time": pd.to_datetime(["2020-01-01"] * 6), "label": [0, 1, 0, 1, 0, 1]})
        self.seeds = {"train_sample": labels.copy(), "val": labels.copy()}
        self.prog = {"program_sql": "select id, seed_time, f0 from {seeds}", "program": {"cutoff": "2019-01-01"}}
        self.fit_count = 0

    def fit(self, task_type, xt, yt, xv):
        self.fit_count += 1
        self.assertEqual(len(xt), len(yt))
        self.assertEqual(list(xt), list(xv))
        return np.full(len(xv), 0.5), [(c, 100 - i) for i, c in enumerate(xt)], 0.01

    def test_subset_selection_preserves_audited_incumbent_and_charges_fits(self):
        with patch.object(harness, "features", return_value=(self.x, 0.01)), \
             patch.object(harness, "read_sql", return_value=(pd.DataFrame(columns=["id", "seed_time"]), 0.0)), \
             patch.object(harness, "train_predict", side_effect=self.fit), \
             patch.object(harness, "score", return_value=0.8), \
             patch.object(self.run, "audit", return_value={"result": "clean"}):
            r = self.run._select_start("task", 2, self.seeds, self.prog, {"features": []}, None, "a", "s", [])
        self.assertEqual(r["chosen"]["name"], "program")
        self.assertEqual(r["subset_selection"][0]["fits"], 2)
        self.assertEqual(self.fit_count, 3)
        self.assertAlmostEqual(r["train_seconds"], 0.03)

    def test_failed_audit_cannot_supply_a_start(self):
        with patch.object(harness, "features", return_value=(self.x, 0.01)), \
             patch.object(harness, "read_sql", return_value=(pd.DataFrame(columns=["id", "seed_time"]), 0.0)), \
             patch.object(self.run, "audit", return_value={"result": "error", "why": "database error"}), \
             patch.object(harness, "train_predict") as fit:
            r = self.run._select_start("task", 2, self.seeds, self.prog, {"features": []}, None, "a", "s", [])
        self.assertIsNone(r["chosen"])
        self.assertIn("audit", r["error"])
        fit.assert_not_called()

    def test_existing_published_arm_does_not_gain_extra_fits(self):
        self.run.arm = harness.ARMS["mavra-push"]
        self.assertFalse(self.run.arm.get("subset_selection"))
        self.run.arm = harness.ARMS["mavra-select"]
        with patch.object(harness, "features", return_value=(self.x, 0.01)), \
             patch.object(harness, "read_sql", return_value=(pd.DataFrame(columns=["id", "seed_time"]), 0.0)), \
             patch.object(harness, "train_predict", side_effect=self.fit), \
             patch.object(harness, "score", return_value=0.8), \
             patch.object(self.run, "audit", return_value={"result": "clean"}):
            self.run._select_start("task", 2, self.seeds, self.prog, {"features": []}, None, "a", "s", [])
        self.assertEqual(self.fit_count, 1)


if __name__ == "__main__":
    unittest.main()
