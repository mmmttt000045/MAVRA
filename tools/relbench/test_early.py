"""Cold exploration must reach validation feedback while search budget remains."""
import unittest

import harness
import test_signal as signal_tests


class EarlyValidationTests(unittest.TestCase):
    def fixture(self):
        f=signal_tests.SignalStartTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.run.arm=harness.ARMS['mavra-early']
        f.run.a.arm='mavra-early'
        return f

    def test_probe_only_agent_gets_a_validation_slot_at_eighth_response(self):
        f=self.fixture()
        requests=[]
        def chat(messages,specs):
            names={s['function']['name'] for s in specs}
            requests.append(names)
            n=len(requests)
            if n<=7:
                self.assertIn('describe_table',names)
                return f.response('describe_table')
            if n==8:
                self.assertEqual(names,{'validate_features'})
                self.assertIn('model response 8',messages[0]['content'])
                return f.response('validate_features',f.agent_sql)
            self.assertIn('describe_table',names)
            return f.response('submit')
        f.run.llm.chat.side_effect=chat
        state=f.explore()
        record=state['rec']
        self.assertEqual(record['final_sql'],f.agent_sql)
        self.assertEqual(record['tools'][7]['name'],'validate_features')
        self.assertEqual(record['tools'][7]['llm_i'],7)
        self.assertEqual(len(record['llm']),9)
        self.assertEqual(len(record['validations']),1)

    def test_attempted_validation_releases_gate_and_old_or_warm_policies_stay_unchanged(self):
        f=self.fixture()
        names=lambda k,n,v:{s['function']['name'] for s in f.run.step_tools(k,n,0,v)}
        self.assertEqual(names(1,7,0),{'validate_features'})
        # A failed attempt is still an attempt: schema tools become available
        # for the error correction instead of burning all eight validations.
        self.assertIn('describe_table',names(1,8,1))
        self.assertEqual(names(2,3,0),{'validate_features','submit'})
        self.assertIn('describe_table',names(2,2,0))
        f.run.arm=harness.ARMS['mavra-refine']
        self.assertIn('describe_table',names(1,7,0))
        self.assertIsNone(f.run.early_validation_hint(1))


if __name__=='__main__':
    unittest.main()
