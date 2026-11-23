"""Common seed-identifier binding wrapper applied equally to programs and definitions.

Rewrites only the entity seed key column name when transferring feature SQL across
tasks on the same entity table; leaves feature logic, temporal predicates, and
labels unchanged. The feature SQL contract places the entity key and `seed_time` first.
"""
import re


def bind_seed_key(sql, source_key, target_key):
    for key in (source_key, target_key):
        if not re.fullmatch(r'[a-z][a-z0-9_]*', key):
            raise ValueError('unsupported seed identifier')
    if source_key == target_key:
        return sql
    if '{seeds}' not in sql:
        raise ValueError('feature SQL needs the seed placeholder')
    seed = f'(select {target_key} as {source_key}, seed_time from {{seeds}})'
    inner = sql.strip().rstrip(';').replace('{seeds}', seed)
    return f'SELECT * FROM ({inner}) AS memory_transfer({target_key}, seed_time)'
