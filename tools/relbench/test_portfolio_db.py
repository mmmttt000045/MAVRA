"""Opt-in PostgreSQL check for portfolio SQL keys, ordering and renamed outputs."""
import os
import time
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import psycopg

import harness


@unittest.skipUnless(os.environ.get("AGENTDB_TEST_URL"), "requires an isolated PostgreSQL test server")
class PortfolioSqlTests(unittest.TestCase):
    def test_union_reproduces_both_sources_despite_different_key_names_and_order(self):
        admin = os.environ["AGENTDB_TEST_URL"]
        name = f"quality_union_test_{os.getpid()}_{time.time_ns()}"
        url = harness.base_url(admin) + "/" + name
        with psycopg.connect(admin, autocommit=True) as con:
            con.execute(f"CREATE DATABASE {name}")
        try:
            with psycopg.connect(url, autocommit=True) as con:
                con.execute("CREATE SCHEMA task")
                con.execute("CREATE TABLE task.t_val (id int,seed_time timestamp,label int)")
                con.execute("INSERT INTO task.t_val VALUES (1,'2020-01-01',0),(1,'2020-02-01',1),"
                            "(2,'2020-02-01',1),(3,'2020-03-01',0)")
            seeds = pd.DataFrame({"id": [1, 1, 2, 3], "seed_time": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-02-01", "2020-03-01"]),
                                  "label": [0, 1, 1, 0]})
            psql = "SELECT s.id,s.seed_time,s.id::double precision AS a,EXTRACT(month FROM s.seed_time)::double precision AS b FROM {seeds} s"
            dsql = ("SELECT s.id AS subject,s.seed_time AS cutoff,(s.id*s.id+EXTRACT(month FROM s.seed_time))::double precision AS c "
                    "FROM {seeds} s ORDER BY s.id DESC,s.seed_time DESC")
            px, _ = harness.features(url, psql, "task.t_val", seeds, "id")
            dx, _ = harness.features(url, dsql, "task.t_val", seeds, "id")
            run = harness.Run.__new__(harness.Run)
            run.url, run.arm = url, harness.ARMS["mavra-portfolio"]
            run.tasks = {"t": {"entity_col": "id", "target_col": "label", "task_type": "binary_classification"}}
            primary = {"rec": {"final_sql": psql, "best_val": 0.8, "higher_is_better": True,
                                 "validations": [], "agent_seconds": 0., "audit_seconds": 0.},
                       "frames": (psql, px, px, [("a", 2), ("b", 1)])}
            other = {"rec": {"final_sql": dsql, "best_val": 0.7, "attempt": 2},
                     "frames": (dsql, dx, dx, [("c", 1)])}

            def fit(task_type, xt, yt, xv):
                return np.zeros(len(xv)), [(c, 1.) for c in xt], 0.001

            # The synthetic SQL reads only seeds; this test checks actual SQL
            # reproduction, while separate tests exercise rejection by the audit.
            with patch.object(harness, "train_predict", side_effect=fit), \
                 patch.object(harness, "score", return_value=0.9), \
                 patch.object(run, "audit", return_value={"result": "clean"}):
                run.combine_cold_start("t", 1, {"train_sample": seeds, "val": seeds}, primary, [other])
            self.assertTrue(primary["rec"]["memory_union"].get("accepted"), primary["rec"]["memory_union"])
            result, _ = harness.features(url, primary["rec"]["final_sql"], "task.t_val", seeds, "id")
            np.testing.assert_allclose(result.to_numpy(), primary["frames"][2].to_numpy())
            self.assertEqual(len(result), 4)
        finally:
            with psycopg.connect(admin, autocommit=True) as con:
                con.execute(f"DROP DATABASE {name} WITH (FORCE)")


if __name__ == "__main__":
    unittest.main()
