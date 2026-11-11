"""Compile one bounded entity-attribute view from schema types alone."""
import re


def ident(name):
    if not isinstance(name, str) or not name or '\x00' in name:
        raise ValueError('SQL identifier must be a nonempty string without NUL')
    return '"' + name.replace('"', '""') + '"'


def compile_view(table, entity_key, seed_key, time_column, foreign_keys, columns,
                 expanded=False, max_features=100):
    """Return SQL and stable output names; no values, labels or task names.

    ``columns`` contains (name, kind), where kind is numeric/date/string/other.
    Only public entity attributes enter this view. String hashes encode equality
    deterministically; they are ordinary numeric features for the fixed learner.
    """
    if max_features < 1:
        raise ValueError('at least one feature must be allowed')
    excluded = {entity_key.lower(), *(key.lower() for key in foreign_keys)}
    if len({name.lower() for name, _ in columns}) != len(columns):
        raise ValueError('database column names must be unique after lowercasing')
    used, base, extra = set(), [], []

    def add(destination, expression, prefix, column):
        stem = prefix + re.sub('[^a-z0-9_]', '_', column)
        name, nonce = stem[:63], 0
        while name in used:
            nonce += 1
            suffix = '_' + str(nonce)
            name = stem[:63-len(suffix)] + suffix
        used.add(name)
        destination.append((name, expression))

    for raw, kind in columns:
        column = raw.lower()
        if column in excluded:
            continue
        value = 'e.' + ident(column)
        if kind == 'boolean':
            add(base, f'CASE WHEN {value} THEN 1.0 WHEN {value} IS FALSE THEN 0.0 ELSE NULL END', 'num_', column)
        elif kind == 'numeric':
            add(base, f'{value}::double precision', 'num_', column)
        elif kind == 'date':
            add(base, f'extract(epoch FROM (s.seed_time - {value})) / 86400.0', 'age_', column)
        elif expanded and kind == 'string':
            # MD5 is stable across query/audit schemas, databases and processes;
            # NULL stays missing. No category dictionary or label statistic is
            # fit on validation or on a future table snapshot.
            encoded = (f"CASE WHEN {value} IS NULL THEN NULL ELSE "
                       f"(('x' || substr(md5({value}::text), 1, 16))::bit(64)::bigint)::double precision "
                       '/ 9223372036854775808.0 END')
            add(extra, encoded, 'cat_', column)
            add(extra, f'char_length({value}::text)::double precision', 'len_', column)
    features = (base + extra)[:max_features]
    if not features:
        features = [('constant', '0.0::double precision')]
    join = f'e.{ident(entity_key.lower())} = s.{ident(seed_key.lower())}'
    if time_column:
        join += f' AND e.{ident(time_column.lower())} <= s.seed_time'
    expressions = ', '.join(f'{value} AS {ident(name)}' for name, value in features)
    sql = (f'SELECT s.{ident(seed_key.lower())}, s.seed_time, {expressions} '
           f'FROM {{seeds}} s LEFT JOIN {ident(table.lower())} e ON {join}')
    return sql, [name for name, _ in features]


def project_columns(sql, seed_key, keep):
    columns = ', '.join('q.' + ident(name) for name in keep)
    if not keep:
        columns = '0.0::double precision AS constant'
    return f'SELECT q.{ident(seed_key)}, q.seed_time, {columns} FROM ({sql}) q'
