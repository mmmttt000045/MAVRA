"""A checked base must survive failed, unsafe or unhelpful additions."""
import contextlib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

import harness
import test_signal as signal_tests
import test_directed as directed_tests


class DeltaWorkflowTests(unittest.TestCase):
    def fixture(self):
        f=signal_tests.SignalStartTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.run.arm=harness.ARMS['mavra-delta']
        f.run.a.arm='mavra-delta'
        f.run.prev_sql={}
        return f

    def warm(self,actions,validation=0.4,audits=None,reproduction_error=None):
        f=self.fixture()
        base_sql=f.agent_sql
        addition='SELECT id, seed_time, n AS extra FROM {seeds}'
        new=pd.DataFrame({'extra':[3.,1.,4.,0.]})
        f.run.targets[('t',2)]={'val':0.5}
        chosen={'name':'program','val':0.5,'sql':base_sql,'columns':['events'],
                'importance':['events'],'top':[('events',1.)]}
        selected={'chosen':chosen,'candidates':[],'_frames':(base_sql,f.signal,f.signal,[('events',1.)]),
                  'audit_seconds':0.,'seconds':0.,'pruning_closed':True}
        specifications=[]
        pending=iter(actions)
        def chat(messages,specs):
            specifications.append({s['function']['name'] for s in specs})
            action=next(pending)
            return f.response(action,addition if action=='validate_additions' else None)
        def features(url,sql,*args,**kwargs):
            self.assertEqual(sql,addition,'the complete incumbent must not be recomputed as a candidate')
            self.assertEqual(kwargs['timeout_s'],45)
            return new.copy(),0.01
        def fit(kind,xt,yt,xv):
            return np.zeros(len(xv)),[(c,1.) for c in xt],0.01
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(f.run,'system_prompt',return_value='fixed original learner'))
            stack.enter_context(patch.object(f.run,'select_start',return_value=selected))
            stack.enter_context(patch.object(f.run,'typed_reference_start',return_value=(None,None,{'audit_seconds':0.,'audit':'error'})))
            query=stack.enter_context(patch.object(harness,'features',side_effect=features))
            stack.enter_context(patch.object(harness,'read_sql',return_value=(pd.DataFrame(columns=['id','seed_time']),0.01)))
            learner=stack.enter_context(patch.object(harness,'train_predict',side_effect=fit))
            stack.enter_context(patch.object(harness,'score',return_value=validation))
            audit=stack.enter_context(patch.object(f.run,'audit',side_effect=audits,
                                                       return_value={'result':'clean'}))
            check=stack.enter_context(patch.object(f.run,'check_columns',side_effect=reproduction_error))
            f.run.llm.chat.side_effect=chat
            state=f.run.explore('t',2,f.seeds,f.middle)
        return f,state,SimpleNamespace(specifications=specifications,query=query,learner=learner,audit=audit,check=check,
                                        base_sql=base_sql,addition=addition)

    def test_premature_submit_is_rejected_and_only_additions_are_computed(self):
        f,state,trace=self.warm(['submit','validate_additions'])
        row=state['rec']
        self.assertNotIn('submit',trace.specifications[0])
        self.assertTrue(row['tools'][0]['error'])
        self.assertEqual(row['best_val'],0.4)
        self.assertNotEqual(row['final_sql'],trace.base_sql)
        self.assertNotIn(trace.base_sql,state['msgs'][1]['content'])
        self.assertEqual(trace.query.call_count,2)
        self.assertEqual(trace.learner.call_count,1)
        self.assertEqual([x['purpose'] for x in row['feature_fits']],['agent_additions'])
        self.assertTrue(row['validations'][0]['delta']['values_reproduced'])
        self.assertEqual(len(row['llm']),2)

    def test_worse_clean_addition_preserves_the_complete_incumbent(self):
        _,state,trace=self.warm(['validate_additions'],validation=0.6)
        self.assertEqual(state['rec']['final_sql'],trace.base_sql)
        self.assertEqual(state['rec']['best_val'],0.5)
        self.assertFalse(state['rec']['validations'][0]['improved'])
        self.assertEqual(trace.audit.call_count,1)

    def test_failed_audit_can_be_repaired_but_cannot_supply_the_best(self):
        _,state,trace=self.warm(['validate_additions','validate_additions'],
                               audits=[{'result':'error','why':'missing audit seed'},{'result':'clean'}])
        rows=state['rec']['validations']
        self.assertEqual(len(rows),2)
        self.assertFalse(rows[0]['improved'])
        self.assertEqual(rows[0]['audit_result'],'error')
        self.assertTrue(rows[1]['improved'])
        self.assertEqual(trace.learner.call_count,2,'the rejected audit fit is still charged')
        self.assertEqual(state['rec']['stop'],'reached_previous')

    def test_repeated_unknown_audits_exhaust_the_same_budget_and_keep_the_base(self):
        _,state,trace=self.warm(['validate_additions']*4,audits=[{'result':'error'}]*4)
        self.assertEqual(state['rec']['final_sql'],trace.base_sql)
        self.assertEqual(state['rec']['best_val'],0.5)
        self.assertEqual(state['rec']['stop'],'llm_budget')
        self.assertEqual(len(state['rec']['llm']),4)
        self.assertEqual(trace.learner.call_count,4)

    def test_failed_sql_reproduction_never_reaches_an_audit_or_fit(self):
        _,state,trace=self.warm(['validate_additions']*4,reproduction_error=harness.FeatureError('wrong joined values'))
        self.assertEqual(state['rec']['final_sql'],trace.base_sql)
        self.assertTrue(all('wrong joined values' in r['error'] for r in state['rec']['validations']))
        trace.audit.assert_not_called()
        trace.learner.assert_not_called()

    def test_tool_priority_is_warm_only_and_a_clean_trial_allows_submit(self):
        f=self.fixture()
        names=lambda k,n,clean:{s['function']['name'] for s in f.run.delta_step_tools(k,n,0,0,True,clean)}
        self.assertEqual(names(2,3,False),{'validate_additions'})
        self.assertEqual(names(2,3,True),{'validate_additions','submit'})
        self.assertIn('validate_features',names(1,0,False))
        self.assertNotIn('validate_additions',names(1,0,False))
        f.run.arm=harness.ARMS['mavra-refine']
        self.assertIn('submit',names(2,0,False))
        self.assertNotIn('validate_additions',names(2,0,False))

    def test_both_cold_and_warm_prompts_show_the_actual_statement_deadline(self):
        f=directed_tests.DirectedBudgetTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.run.arm=harness.ARMS['mavra-delta']
        cold=f.run.system_prompt('task',1,f.seeds)
        warm=f.run.system_prompt('task',2,f.seeds)
        self.assertIn('40 model calls',cold)
        self.assertIn('stop after 45 seconds',cold)
        self.assertIn('4 model calls',warm)
        self.assertIn('6 executed agent tools',warm)
        self.assertIn('validate_additions',warm)
        self.assertNotIn('only validate_features and submit',warm)

    def test_failed_refit_is_bounded_once_and_skip_is_bound_to_all_labels(self):
        f=self.fixture()
        f.run.prev_sql={'t':(1,f.agent_sql)}
        with patch.object(harness,'features',side_effect=harness.FeatureError('statement timeout')) as query:
            target=f.run.incumbent('t',2,f.seeds)
        self.assertIsNone(target['val'])
        self.assertEqual(target['attempts'],1)
        self.assertEqual(query.call_count,1)
        self.assertEqual(query.call_args.kwargs['timeout_s'],45)
        with patch.object(f.run,'_select_start',return_value=None) as select:
            skipped=f.run.select_start('t',2,f.seeds,{'program_sql':f.agent_sql},{},f.middle,'a','s')
            self.assertTrue(skipped['skipped_failed_current_refit'])
            select.assert_not_called()
            changed={k:v.copy() for k,v in f.seeds.items()}
            changed['val'].loc[0,'label']=9.
            f.run.select_start('t',2,changed,{'program_sql':f.agent_sql},{},f.middle,'a','s')
            select.assert_called_once()

    def test_common_reference_and_parent_statement_limits_are_unchanged(self):
        f=self.fixture()
        f.run.manifest={'tables':{'entities':{'pkey':'id','fkeys':{}}}}
        with patch.object(f.run,'table',return_value=pd.DataFrame({'id':[1,2],'n':[3.,4.],'name':['x','y']})):
            before=f.run.reference_sql('t')
            self.assertEqual(f.run.validation_timeout(1),45)
            f.run.arm=harness.ARMS['mavra-refine']
            self.assertEqual(before,f.run.reference_sql('t'))
            self.assertEqual(f.run.validation_timeout(1),harness.FEATURE_SQL_TIMEOUT_S)

    def test_typed_views_use_validation_and_unknown_audits_never_win(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        schema=pa.schema([('id',pa.int64()),('n',pa.float64()),('city',pa.string())])
        for typed_score,typed_audit,winner in ((0.5,'clean','numeric_date'),(0.3,'clean','typed'),
                                                (0.3,'error','numeric_date')):
            with self.subTest(typed_score=typed_score,audit=typed_audit):
                f=self.fixture()
                f.run.a.data='unused'
                f.run._fit_ledger=[]
                f.run.manifest={'tables':{'entities':{'pkey':'id','fkeys':{},'time_col':None}}}
                def query(url,sql,*args,**kwargs):
                    values={'num_n':[1.,2.,3.,4.]}
                    if 'cat_city' in sql:
                        values.update(cat_city=[0.,1.,0.,1.],len_city=[1.,2.,1.,2.])
                    return pd.DataFrame(values),0.01
                def fit(kind,xt,yt,xv):
                    return np.zeros(len(xv)),[(c,1.) for c in xt],0.01
                with patch.object(pq,'read_schema',return_value=schema), \
                     patch.object(harness,'features',side_effect=query), \
                     patch.object(harness,'train_predict',side_effect=fit), \
                     patch.object(harness,'score',side_effect=[0.4,typed_score]), \
                     patch.object(f.run,'audit',side_effect=[{'result':'clean'},{'result':typed_audit}]):
                    frames,value,record=f.run.typed_reference_start('t',1,f.seeds)
                self.assertEqual(record['chosen']['kind'],winner)
                self.assertFalse(record['framework_reference_changed'])
                self.assertEqual(len(f.run._fit_ledger),2)
                self.assertEqual(value,0.3 if winner=='typed' else 0.4)


if __name__=='__main__':
    unittest.main()
