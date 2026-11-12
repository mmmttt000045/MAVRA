import unittest

import pandas as pd

from delta_features import delta_pool


class DeltaPoolTests(unittest.TestCase):
    def test_only_genuinely_new_varying_columns_are_offered(self):
        base=pd.DataFrame({'events':[1.,2.,3.],'constant':[0.,0.,0.]})
        added=pd.DataFrame({'copy':[1.,2.,3.],'new':[3.,1.,2.],'flat':[4.,4.,4.]})
        xt,xv,info=delta_pool(base,base,[('events',1.)],added,added)
        self.assertEqual(info['duplicate_columns'],['copy'])
        self.assertEqual(info['constant_columns'],['flat'])
        self.assertEqual(list(info['added_columns']),['new'])
        self.assertEqual(list(xt)[:2],list(base))
        self.assertTrue(xt['events'].equals(base.events))
        self.assertTrue(xv.equals(xt))
        self.assertEqual(list(base),['events','constant'])

    def test_existing_training_gain_rank_limits_the_joined_candidate(self):
        base=pd.DataFrame({'a':[0.,1.,2.],'b':[2.,0.,1.],'c':[1.,2.,0.]})
        added=pd.DataFrame({'new':[3.,4.,7.]})
        xt,_,info=delta_pool(base,base,[('c',9.),('b',3.),('a',1.)],added,added,max_features=3)
        self.assertEqual(info['primary_columns'],['b','c'])
        self.assertEqual(info['dropped_primary'],['a'])
        self.assertEqual(len(xt.columns),3)

    def test_same_training_values_but_different_validation_values_are_distinct(self):
        base=pd.DataFrame({'x':[1.,2.,3.]})
        train=pd.DataFrame({'candidate':[1.,2.,3.]})
        valid=pd.DataFrame({'candidate':[1.,2.,4.]})
        _,_,info=delta_pool(base,base,[('x',1.)],train,valid)
        self.assertEqual(list(info['added_columns']),['candidate'])

    def test_duplicate_only_misaligned_rows_and_excessive_columns_are_refused(self):
        base=pd.DataFrame({'x':[1.,2.,3.]})
        with self.assertRaises(ValueError):
            delta_pool(base,base,[],base,base)
        other=pd.DataFrame({'new':[4.,5.,6.]},index=[2,1,0])
        with self.assertRaises(ValueError):
            delta_pool(base,base,[],other,other)
        wide=pd.DataFrame({str(i):[i,0,1] for i in range(13)})
        with self.assertRaises(ValueError):
            delta_pool(base,base,[],wide,wide)


if __name__=='__main__':
    unittest.main()
