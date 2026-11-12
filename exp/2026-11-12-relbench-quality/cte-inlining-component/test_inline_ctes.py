import unittest

from inline_ctes import inline_grouped_ctes


class CteInliningTests(unittest.TestCase):
    def test_repeated_grouped_view_preserves_seed_and_time_expressions(self):
        source = '''WITH a AS (SELECT id, happened_at, sum(n) AS n FROM events GROUP BY id,happened_at)
                    SELECT s.id,s.seed_time,(SELECT sum(n) FROM a WHERE a.id=s.id AND a.happened_at<=s.seed_time) AS n,
                           (SELECT count(*) FROM a WHERE a.id=s.id AND a.happened_at>s.seed_time-interval '7 days'
                             AND a.happened_at<=s.seed_time) AS recent FROM {seeds} s'''
        sql, info = inline_grouped_ctes(source)
        self.assertIn('AS NOT MATERIALIZED',sql)
        self.assertIn('FROM {seeds} AS s',sql)
        self.assertEqual(sql.count('a.happened_at <= s.seed_time'),2)
        self.assertEqual(info['changed_ctes'],[{'name':'a','references':2}])

    def test_explicit_or_single_use_and_ungrouped_views_are_unchanged(self):
        for source in ('WITH a AS MATERIALIZED (SELECT id,sum(n) AS n FROM t GROUP BY id) SELECT * FROM a x JOIN a y USING(id)',
                       'WITH a AS (SELECT id,sum(n) AS n FROM t GROUP BY id) SELECT * FROM a',
                       'WITH a AS (SELECT * FROM t) SELECT * FROM a x JOIN a y USING(id)',
                       'select 1 -- preserve original bytes'):
            sql,info = inline_grouped_ctes(source)
            self.assertEqual(sql,source)
            self.assertFalse(info['changed_ctes'])

    def test_recursive_or_unrecognized_functions_are_unchanged(self):
        for source in ('WITH RECURSIVE a AS (SELECT id,sum(n) AS n FROM t GROUP BY id) SELECT * FROM a x JOIN a y USING(id)',
                       'WITH a AS (SELECT id,sum(random()) AS n FROM t GROUP BY id) SELECT * FROM a x JOIN a y USING(id)'):
            self.assertEqual(inline_grouped_ctes(source),(source,{'changed_ctes':[]}))

    def test_statement_side_effects_and_placeholder_collisions_are_refused(self):
        for source in ('select 1;select 2', 'delete from t',
                       'WITH a AS (DELETE FROM t RETURNING *) SELECT * FROM a',
                       'SELECT * INTO copy FROM t', 'SELECT * FROM t FOR UPDATE',
                       'SELECT * FROM __mavra_inline_seeds__'):
            with self.assertRaises(ValueError):
                inline_grouped_ctes(source)


if __name__ == '__main__':
    unittest.main()
