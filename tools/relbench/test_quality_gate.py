"""Reject unfinished cohorts and compare unrounded quality and each cost."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('quality_gate', Path(__file__).with_name('quality-cost-gate.py'))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class QualityGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / 'results/baselines/none-rel-stack-r1'
        self.candidate = self.root / 'candidates/arm-rel-stack-r1'
        self.base.mkdir(parents=True)
        self.candidate.mkdir(parents=True)
        self.records = {(t, k): {'tokens': 100, 'llm': 1, 'tools': 1, 'agent_s': 1.,
                                 'cost': {'offpeak': 0.01}, 'higher': True, 'valid': True, 'test': 0.8}
                        for t in ('a', 'b', 'c') for k in range(1, 6)}
        self.current = copy.deepcopy(self.records)
        (self.base / 'run.json').write_text(json.dumps({'cutoffs': []}))
        self.metadata(finished='2026-11-12')

    def metadata(self, **values):
        (self.candidate / 'run.json').write_text(json.dumps(values))

    def check(self):
        def load(path, reference):
            return copy.deepcopy(self.current if path == self.candidate else self.records)
        with patch.object(gate, 'DIRECTORIES', {'rel-stack': 'baselines'}), \
             patch.object(gate, 'ARMS', ('none', 'mavra-push')), patch.object(gate, 'load', side_effect=load):
            return gate.check(self.root, self.root / 'candidates', 'arm', 1)['panels']['rel-stack']

    def test_finished_record_count_alone_does_not_accept_incomplete_evaluation(self):
        self.metadata(cutoffs=[{'k': 5}])
        self.assertFalse(self.check()['complete'])
        self.metadata(finished='2026-11-12', error='final evaluation failed')
        self.assertFalse(self.check()['complete'])

    def test_each_cost_must_pass_without_compensating_with_another_column(self):
        self.assertTrue(self.check()['accepted'])
        self.current[('a', 2)]['tools'] += 1
        report = self.check()
        self.assertFalse(report['cost_pass']['tool_calls'])
        self.assertFalse(report['accepted'])

    def test_quality_is_compared_before_display_rounding(self):
        self.current[('a', 1)]['test'] -= 1e-7
        report = self.check()
        self.assertFalse(report['quality']['a']['first_or_tied'])
        self.assertFalse(report['accepted'])

    def test_missing_or_invalid_session_prevents_acceptance(self):
        self.current[('a', 1)]['valid'] = False
        self.assertFalse(self.check()['accepted'])
        self.current.pop(('a', 1))
        self.assertFalse(self.check()['complete'])


if __name__ == '__main__':
    unittest.main()
