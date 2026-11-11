"""Real PostgreSQL checks: no self target, no future-window labels, exact bounds."""
import os
import time
import unittest

import numpy as np
import pandas as pd
import psycopg

import harness
from outcome_history import FEATURES, compile_history_features, relation


@unittest.skipUnless(os.environ.get('AGENTDB_TEST_URL'), 'requires an isolated PostgreSQL test server')
class HistorySqlTests(unittest.TestCase):
    def test_maturity_boundaries_and_future_label_perturbation(self):
        admin = os.environ['AGENTDB_TEST_URL']
        name = f'quality_history_test_{os.getpid()}_{time.time_ns()}'
        url = harness.base_url(admin) + '/' + name
        with psycopg.connect(admin, autocommit=True) as con:
            con.execute(f'CREATE DATABASE {name}')
        try:
            seeds = pd.DataFrame({'id': [1, 1, 3, 1, 2], 'seed_time': pd.to_datetime(
                ['2020-01-07', '2020-01-08', '2020-01-07', '2019-01-01', '2020-01-07'])})
            with psycopg.connect(url, autocommit=True) as con:
                con.execute('CREATE SCHEMA task')
                con.execute('CREATE TABLE task.t_train(id int,seed_time timestamp,label float8)')
                con.execute("INSERT INTO task.t_train VALUES (1,'2020-01-01',2),(1,'2020-01-05',4),"
                            "(1,'2020-01-07',77),(1,'2020-01-09',999),(2,'2020-01-01',10)")
                con.execute('CREATE TABLE task.check_seeds(id int,seed_time timestamp)')
                harness.copy_rows(con, 'task.check_seeds', seeds)
            sql = compile_history_features('task', 't_train', 'id', 'label', 86400000000)
            before, _ = harness.features(url, sql, 'task.check_seeds', seeds, 'id')
            self.assertEqual(list(before), list(FEATURES))
            self.assertEqual(before.loc[0, 'oh_count'], 2.)
            self.assertEqual(before.loc[0, 'oh_mean'], 3.)
            self.assertEqual(before.loc[0, 'oh_last'], 4.)
            self.assertEqual(before.loc[0, 'oh_count_recent'], 0.)
            self.assertEqual(before.loc[0, 'oh_mean_3h'], 4.)
            self.assertEqual(before.loc[0, 'oh_days_since_last'], 1.)
            self.assertEqual(before.loc[1, 'oh_count'], 3.)
            self.assertEqual(before.loc[1, 'oh_last'], 77.)
            self.assertEqual(before.loc[2, 'oh_count'], 0.)
            self.assertAlmostEqual(before.loc[2, 'oh_global_mean'], 16. / 3.)
            self.assertEqual(before.loc[3, 'oh_global_count'], 0.)
            self.assertEqual(before.loc[3, 'oh_days_since_last'], 1000000.)
            with psycopg.connect(url, autocommit=True) as con:
                con.execute("UPDATE task.t_train SET label=1000000000 WHERE seed_time='2020-01-09'")
            future_changed, _ = harness.features(url, sql, 'task.check_seeds', seeds, 'id')
            np.testing.assert_allclose(before, future_changed)
            with psycopg.connect(url, autocommit=True) as con:
                con.execute("UPDATE task.t_train SET label=7700000 WHERE seed_time='2020-01-07'")
            own_changed, _ = harness.features(url, sql, 'task.check_seeds', seeds, 'id')
            np.testing.assert_allclose(before.iloc[0], own_changed.iloc[0])
            self.assertNotEqual(before.loc[1, 'oh_last'], own_changed.loc[1, 'oh_last'])
            check = seeds[seeds.seed_time == pd.Timestamp('2020-01-07')].reset_index(drop=True)
            with psycopg.connect(url, autocommit=True) as con:
                con.execute('CREATE SCHEMA history_guard')
                con.execute("CREATE VIEW history_guard.t_train AS SELECT * FROM task.t_train "
                            "WHERE seed_time+INTERVAL '1 day'<='2020-01-07'")
                con.execute('CREATE TABLE task.audit_seeds(id int,seed_time timestamp)')
                harness.copy_rows(con, 'task.audit_seeds', check)
            normal, _ = harness.features(url, sql, 'task.audit_seeds', check, 'id')
            hidden_sql = sql.replace(relation('task', 't_train'), relation('history_guard', 't_train'))
            hidden, _ = harness.features(url, hidden_sql, 'task.audit_seeds', check, 'id')
            np.testing.assert_allclose(normal, hidden)
            bad = 'SELECT s.id,s.seed_time,(SELECT avg(label) FROM "task"."t_train") AS bad FROM {seeds} s'
            leaky, _ = harness.features(url, bad, 'task.audit_seeds', check, 'id')
            censored, _ = harness.features(url, bad.replace(relation('task', 't_train'), relation('history_guard', 't_train')),
                                           'task.audit_seeds', check, 'id')
            self.assertFalse(np.allclose(leaky, censored))
        finally:
            with psycopg.connect(admin, autocommit=True) as con:
                con.execute(f'DROP DATABASE {name} WITH (FORCE)')


if __name__ == '__main__':
    unittest.main()
