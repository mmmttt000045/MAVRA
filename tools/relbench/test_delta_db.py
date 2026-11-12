"""Opt-in PostgreSQL proof of joined values, key alignment and future isolation."""
import os
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd
import psycopg
from psycopg import sql as psql

import harness


@unittest.skipUnless(os.environ.get('AGENTDB_REL_DELTA_TEST_URL'),'requires a separately created test database')
class DeltaDatabaseTests(unittest.TestCase):
    def test_only_additions_are_read_before_the_joined_value_and_future_checks(self):
        url=os.environ['AGENTDB_REL_DELTA_TEST_URL']
        if not psycopg.conninfo.conninfo_to_dict(url)['dbname'].startswith('quality_delta_test_'):
            self.fail('the opt-in URL must point to an isolated quality_delta_test_ database')
        nonce=f'{os.getpid()}_{time.time_ns()%1000000000}'
        table='delta_events_'+nonce
        task='delta_task_'+nonce
        train=f'{task}_train_sample'
        valid=f'{task}_val'
        rows=pd.DataFrame({'id':[1,1,2,3],'seed_time':pd.to_datetime(
            ['2020-01-10','2020-02-01','2020-01-10','2020-01-10']),'label':[0.,1.,0.,1.]})
        seeds={'train_sample':rows,'val':rows.copy()}
        try:
            with psycopg.connect(url,autocommit=True) as con:
                con.execute('CREATE SCHEMA IF NOT EXISTS task')
                con.execute(psql.SQL('CREATE TABLE {} (id bigint,happened_at timestamp,n double precision)').format(psql.Identifier(table)))
                con.execute(psql.SQL("INSERT INTO {} VALUES (1,'2020-01-01',2),(1,'2020-01-15',5),"
                    "(2,'2020-01-01',4),(2,'2020-01-05',NULL),(1,'2020-06-01',100)").format(psql.Identifier(table)))
                for name in (train,valid):
                    con.execute(psql.SQL('CREATE TABLE task.{} (id bigint,seed_time timestamp,label double precision)').format(psql.Identifier(name)))
                    harness.copy_rows(con,'task.'+name,rows)
            fact='public.'+harness.quote_ident(table)
            value=f'(SELECT sum(e.n) FROM {fact} e WHERE e.id=s.id AND e.happened_at<=s.seed_time)'
            base_sql=f'SELECT s.id AS original_id,s.seed_time AS original_time,coalesce({value},0) AS baseline FROM {{seeds}} s'
            added_sql=(f'SELECT s.id AS added_id,s.seed_time AS added_time,coalesce({value},0) AS duplicate_value,'
                       f'(SELECT count(*) FROM {fact} e WHERE e.id=s.id AND e.happened_at<=s.seed_time) AS activity '
                       'FROM {seeds} s')
            bx,_=harness.features(url,base_sql,'task.'+train,rows,'id')
            bv,_=harness.features(url,base_sql,'task.'+valid,rows,'id')
            run=harness.Run.__new__(harness.Run)
            run.url,run.arm=url,harness.ARMS['mavra-delta']
            run.tasks={task:{'entity_col':'id','target_col':'label'}}
            run.manifest={'tables':{table:{'time_col':'happened_at'}}}
            event={}
            with patch.object(harness,'features',wraps=harness.features) as spy:
                combined,xt,xv=run.prepare_delta(task,2,seeds,(base_sql,bx,bv,[('baseline',1.)]),added_sql,event)
            self.assertEqual(event['duplicate_columns'],['duplicate_value'])
            self.assertEqual(len(spy.call_args_list),3)
            self.assertTrue(all(c.args[1]==added_sql for c in spy.call_args_list[:2]))
            self.assertEqual(spy.call_args_list[2].args[1],combined)
            self.assertTrue(spy.call_args_list[2].args[2].startswith('select_'))
            self.assertTrue(event['values_reproduced'])
            got,_=harness.features(url,combined,'task.'+valid,rows,'id')
            pd.testing.assert_frame_equal(got,xv)
            self.assertEqual(list(got.baseline),[2.,7.,4.,0.])
            self.assertEqual(run.audit(task,2,combined,seeds)['result'],'clean')
            with psycopg.connect(url,autocommit=True) as con:
                con.execute(psql.SQL("INSERT INTO {} VALUES (1,'2020-04-01',99999)").format(psql.Identifier(table)))
            after,_=harness.features(url,combined,'task.'+valid,rows,'id')
            pd.testing.assert_frame_equal(after,xv)
        finally:
            with psycopg.connect(url,autocommit=True) as con:
                for name in (train,valid):
                    con.execute(psql.SQL('DROP TABLE IF EXISTS task.{}').format(psql.Identifier(name)))
                con.execute(psql.SQL('DROP TABLE IF EXISTS {}').format(psql.Identifier(table)))


if __name__=='__main__':
    unittest.main()
