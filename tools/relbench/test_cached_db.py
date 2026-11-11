"""Opt-in: real fixed learner and PostgreSQL current-refit reuse, no LLM."""
import os
import time
import unittest
from unittest.mock import patch

import pandas as pd
import psycopg

import harness


@unittest.skipUnless(os.environ.get('AGENTDB_TEST_URL'), 'requires an isolated PostgreSQL test server')
class CachedSqlTests(unittest.TestCase):
    def test_current_refit_preserves_seed_alignment_and_future_isolation(self):
        admin = os.environ['AGENTDB_TEST_URL']
        name = f'quality_cache_test_{os.getpid()}_{time.time_ns()}'
        url = harness.base_url(admin) + '/' + name
        with psycopg.connect(admin, autocommit=True) as con:
            con.execute(f'CREATE DATABASE {name}')
        try:
            train = pd.DataFrame({'id': range(1, 81), 'seed_time': pd.to_datetime(['2020-01-01'] * 80),
                                  'label': [i % 2 for i in range(1, 81)]})
            valid = train.copy()
            valid['seed_time'] = pd.Timestamp('2020-02-01')
            with psycopg.connect(url, autocommit=True) as con:
                con.execute('CREATE SCHEMA task')
                con.execute('CREATE TABLE entities(id int PRIMARY KEY,created_at timestamp)')
                con.execute("INSERT INTO entities SELECT i,'2000-01-01' FROM generate_series(1,80) i")
                con.execute('CREATE TABLE events(id int,event_time timestamp,amount numeric)')
                con.execute("INSERT INTO events SELECT i,'2019-06-01',(i%7) FROM generate_series(1,80) i")
                con.execute("INSERT INTO events SELECT i,'2019-12-01',(i%3) FROM generate_series(1,80) i")
                con.execute("INSERT INTO events SELECT i,'2021-01-01',10000 FROM generate_series(1,80) i")
                for split, seeds in (('train_sample', train), ('val', valid)):
                    con.execute(f'CREATE TABLE task.t_{split}(id int,seed_time timestamp,label int)')
                    harness.copy_rows(con, f'task.t_{split}', seeds)
            sql = ('SELECT s.id,s.seed_time,count(e.id)::double precision AS n,'
                   'coalesce(sum(e.amount),0)::double precision AS amount FROM {seeds} s '
                   'LEFT JOIN events e ON e.id=s.id AND e.event_time<=s.seed_time '
                   'GROUP BY s.id,s.seed_time ORDER BY s.id DESC')
            run = harness.Run.__new__(harness.Run)
            run.url, run.arm = url, harness.ARMS['mavra-cached']
            run.tasks = {'t': {'entity_col': 'id', 'target_col': 'label', 'task_type': 'binary_classification',
                               'cutoffs': [{'test_timestamp': '2020-01-01'}, {'test_timestamp': '2020-02-01'}]}}
            run.manifest = {'tables': {'entities': {'time_col': 'created_at'}, 'events': {'time_col': 'event_time'}}}
            run.prev_sql = {'t': (1, sql)}
            run.incumbent_frames, run.incumbent_work = {}, {}
            seeds = {'train_sample': train, 'val': valid}
            goal = run.incumbent('t', 2, seeds)
            self.assertIsNotNone(goal.get('val'), goal)
            cache = run.current_incumbent('t', 2, seeds)
            self.assertEqual(cache['audit'], 'clean')
            self.assertEqual(cache['train']['n'].tolist(), [2.] * 80)
            self.assertEqual(cache['train']['amount'].tolist(), [float(i % 7 + i % 3) for i in range(1, 81)])
            with patch.object(harness, 'features', side_effect=AssertionError('no duplicate feature query')):
                start = run.select_start('t', 2, seeds, {'program_sql': sql}, {}, None, 'a', 's')
            self.assertEqual(start['chosen']['val'], goal['val'])
            self.assertEqual(start['chosen']['sql'], sql)
            record = {'agent_seconds': 0., 'feature_fits': []}
            run.charge_incumbent_work('t', 2, record)
            self.assertGreater(record['agent_seconds'], 0.)
            self.assertEqual(len(record['feature_fits']), 1)
        finally:
            with psycopg.connect(admin, autocommit=True) as con:
                con.execute(f'DROP DATABASE {name} WITH (FORCE)')


if __name__ == '__main__':
    unittest.main()
