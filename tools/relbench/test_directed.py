"""The warm agent sees its enforced deadline and keeps a final decision slot."""
import unittest

import pandas as pd

import harness


class DirectedBudgetTests(unittest.TestCase):
    def setUp(self):
        self.run = harness.Run.__new__(harness.Run)
        self.run.arm = harness.ARMS['mavra-directed']
        self.run.asm = None
        self.run.manifest = {'tables': {'entity': {'pkey': 'id'}}}
        self.run.task_desc = {'task': {'description': 'predict the next event'}}
        self.run.tasks = {'task': {'entity_col': 'id', 'entity_table': 'entity', 'target_col': 'label',
                                   'task_type': 'binary_classification', 'timedelta': '30 days',
                                   'cutoffs': [dict(val_timestamp='2020-01-01', test_timestamp='2020-02-01'),
                                               dict(val_timestamp='2020-02-01', test_timestamp='2020-03-01')]}}
        self.run.targets = {('task', 2): {'val': 0.8}}
        self.seeds = {'train': pd.DataFrame({'seed_time': pd.to_datetime(['2019-01-01'])}),
                      'val': pd.DataFrame({'id': [1]})}

    def test_prompt_matches_enforced_budget_without_changing_cold_search(self):
        warm = self.run.system_prompt('task', 2, self.seeds)
        self.assertIn('3 model calls', warm)
        self.assertIn('6 executed agent tools', warm)
        self.assertIn('stop after 45 seconds', warm)
        self.assertNotIn('40 model calls', warm)
        self.assertNotIn('next 5 model calls', warm)
        cold = self.run.system_prompt('task', 1, self.seeds)
        self.assertIn('40 model calls', cold)
        self.assertEqual(self.run.validation_timeout(1), harness.FEATURE_SQL_TIMEOUT_S)

    def test_decision_tools_are_reserved_at_either_resource_boundary(self):
        def names(k, calls, tools):
            return {s['function']['name'] for s in self.run.step_tools(k, calls, tools)}
        full = names(2, 0, 0)
        self.assertIn('describe_table', full)
        self.assertEqual(names(2, 2, 0), {'validate_features', 'submit'})
        self.assertEqual(names(2, 0, 5), {'validate_features', 'submit'})
        self.assertEqual(names(1, 2, 5), full)

    def test_existing_frozen_arms_keep_their_original_prompt_and_tools(self):
        for arm in ('none', 'mavra-push', 'mavra-budgeted', 'mavra-portfolio'):
            self.run.arm = harness.ARMS[arm]
            with self.subTest(arm=arm):
                self.assertIn('40 model calls', self.run.system_prompt('task', 2, self.seeds))
                self.assertIsNone(self.run.remaining_budget_message(2, 2, 5))
                self.assertEqual(self.run.validation_timeout(2), harness.FEATURE_SQL_TIMEOUT_S)
                self.assertEqual(self.run.post_goal_window(2, 2), harness.POST_GOAL_LLM_CALLS)
                self.assertIn('describe_table', {s['function']['name'] for s in self.run.step_tools(2, 2, 5)})

    def test_reminder_and_goal_window_use_remaining_calls(self):
        self.assertIn('1 model response(s), 2 executed tool call(s)', self.run.remaining_budget_message(2, 2, 4))
        self.assertEqual(self.run.post_goal_window(2, 2), 1)
        self.assertEqual(self.run.post_goal_window(2, 3), 0)

    def test_failed_audit_reports_the_error_without_claiming_a_detected_leak(self):
        feedback = self.run.audit_rejection_feedback({'result': 'error', 'why': '1 seed missing'})
        self.assertIn('1 seed missing', feedback['audit_error']['reason'])
        self.assertFalse(feedback['audit_error']['counted'])
        self.assertNotIn('leak', feedback)
        leak = self.run.audit_rejection_feedback({'result': 'leak', 'columns_differing': ['future']})
        self.assertEqual(leak['leak']['columns_reading_data_after_seed_time'], ['future'])
        self.assertFalse(leak['leak']['counted'])
        self.run.arm = harness.ARMS['mavra-portfolio']
        self.assertIn('leak', self.run.audit_rejection_feedback({'result': 'error', 'why': '1 seed missing'}))


if __name__ == '__main__':
    unittest.main()
