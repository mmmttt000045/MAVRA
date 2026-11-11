import unittest

from typed_attributes import compile_view, project_columns


class TypedAttributeTests(unittest.TestCase):
    def test_keys_excluded_future_bound_stays_in_left_join_and_hash_is_stable_sql(self):
        sql, names = compile_view('Entities', 'ID', 'ownerid', 'created', ['parent'],
                                  [('ID', 'numeric'), ('parent', 'string'),
                                   ('created', 'date'), ('country', 'string'), ('n', 'numeric')], expanded=True)
        self.assertEqual(names, ['age_created', 'num_n', 'cat_country', 'len_country'])
        self.assertIn('LEFT JOIN "entities" e ON e."id" = s."ownerid" AND e."created" <= s.seed_time', sql)
        self.assertNotIn(' WHERE ', sql)
        self.assertIn('md5(e."country"::text)', sql)
        self.assertIn('CASE WHEN e."country" IS NULL THEN NULL', sql)
        self.assertEqual((sql, names), compile_view('Entities', 'ID', 'ownerid', 'created', ['parent'],
                         [('ID', 'numeric'), ('parent', 'string'), ('created', 'date'),
                          ('country', 'string'), ('n', 'numeric')], expanded=True))

    def test_empty_control_and_bounded_expansion_preserve_numeric_columns_first(self):
        sql, names = compile_view('e', 'id', 'id', None, [], [('id', 'numeric'), ('x', 'string')])
        self.assertEqual(names, ['constant'])
        self.assertIn('0.0::double precision', sql)
        _, names = compile_view('e', 'id', 'id', None, [], [('x', 'string'), ('n', 'numeric')], True, 2)
        self.assertEqual(names, ['num_n', 'cat_x'])

    def test_identifier_escaping_duplicate_rejection_and_constant_projection(self):
        sql, names = compile_view('e', 'id', 'id', None, [], [('a"b', 'string')], True)
        self.assertIn('e."a""b"', sql)
        self.assertEqual(names, ['cat_a_b', 'len_a_b'])
        self.assertIn('0.0::double precision AS constant', project_columns(sql, 'id', []))
        with self.assertRaises(ValueError):
            compile_view('e', 'id', 'id', None, [], [('A', 'string'), ('a', 'numeric')])

    def test_boolean_missing_values_and_long_name_collisions(self):
        sql, names = compile_view('e', 'id', 'id', None, [],
                                  [('flag', 'boolean'), ('x'*80+'a', 'string'),
                                   ('x'*80+'b', 'string')], True)
        self.assertIn('WHEN e."flag" IS FALSE THEN 0.0 ELSE NULL END', sql)
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(len(name.encode()) <= 63 for name in names))


if __name__ == '__main__':
    unittest.main()
