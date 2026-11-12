"""Request inlining for a conservative subset of repeated aggregate CTEs.

This is an execution candidate, not a claim that every CTE should be inlined.
The caller must measure it and retain the original when the check fails.
"""
from collections import Counter

from pglast import ast, enums, parse_sql
from pglast.stream import RawStream
from pglast.visitors import Skip, Visitor


AGGREGATES = frozenset(('count','sum','avg','min','max','stddev','stddev_pop',
                        'stddev_samp','variance','var_pop','var_samp'))
FUNCTIONS = AGGREGATES | {'extract', 'date_part'}
SEEDS = '__mavra_inline_seeds__'


def inline_grouped_ctes(sql):
    if SEEDS in sql:
        raise ValueError('reserved seed placeholder already occurs in SQL')
    trees = parse_sql(sql.replace('{seeds}', SEEDS))
    if len(trees) != 1 or not isinstance(trees[0].stmt, ast.SelectStmt):
        raise ValueError('only one SELECT can be considered')
    references = Counter()

    class Check(Visitor):
        def visit_RangeVar(self, ancestors, node):
            if not node.schemaname:
                references[node.relname] += 1

        def visit_CommonTableExpr(self, ancestors, node):
            if not isinstance(node.ctequery, ast.SelectStmt):
                raise ValueError('data-modifying CTEs cannot be considered')

        def visit_SelectStmt(self, ancestors, node):
            if node.intoClause or node.lockingClause:
                raise ValueError('SELECT INTO and locking queries cannot be considered')

    Check()(trees)
    changed = []

    class Eligible(Visitor):
        def __init__(self):
            super().__init__()
            self.safe = True

        def visit_FuncCall(self, ancestors, node):
            name = [part.sval for part in node.funcname]
            if not (name[-1] in FUNCTIONS and (len(name)==1 or name[:-1]==['pg_catalog'])):
                self.safe = False

    class Rewrite(Visitor):
        def visit_WithClause(self, ancestors, node):
            if node.recursive:
                return Skip

        def visit_CommonTableExpr(self, ancestors, node):
            query = node.ctequery
            if (node.ctematerialized != enums.CTEMaterialize.CTEMaterializeDefault
                    or not query.groupClause or references[node.ctename] < 2):
                return
            eligible = Eligible()
            eligible(query)
            if eligible.safe:
                node.ctematerialized = enums.CTEMaterialize.CTEMaterializeNever
                changed.append({'name':node.ctename,'references':references[node.ctename]})

    Rewrite()(trees)
    if not changed:
        return sql, {'changed_ctes':[]}
    rewritten = RawStream()(trees).replace(SEEDS,'{seeds}')
    return rewritten, {'changed_ctes':changed}
