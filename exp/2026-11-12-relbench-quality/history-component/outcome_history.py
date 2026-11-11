"""Point-in-time summaries of *training* outcomes, never held-out targets.

A target for a window starting at u is treated as observable only at u+horizon.
Every join below uses that availability time, excluding the predicted seed's
own target and all overlapping future windows. No task-specific label SQL is
an input. All benchmark arms already have access to this labelled train split.
"""


FEATURES = ('oh_count', 'oh_sum', 'oh_mean', 'oh_max', 'oh_std', 'oh_positive_rate',
            'oh_count_recent', 'oh_mean_recent', 'oh_count_3h', 'oh_mean_3h',
            'oh_last', 'oh_days_since_last', 'oh_global_mean', 'oh_global_recent', 'oh_global_count')


def ident(value):
    if not isinstance(value, str) or not value or '\x00' in value:
        raise ValueError('SQL identifiers must be nonempty strings without NUL')
    return '"' + value.replace('"', '""') + '"'


def relation(schema, table):
    return ident(schema) + '.' + ident(table)


def interval_sql(horizon_microseconds):
    if (not isinstance(horizon_microseconds, int) or isinstance(horizon_microseconds, bool)
            or horizon_microseconds <= 0):
        raise ValueError('outcome availability requires a positive integer horizon in microseconds')
    return f"INTERVAL '{horizon_microseconds} microseconds'"


def compile_history_features(schema, table, entity, target, horizon_microseconds):
    """Return a numeric feature SQL over {seeds}, using matured train labels.

    The source is the full training split, not the validation split or a sample
    selected with knowledge of future row counts. The final learner's original
    50k training sample is unchanged. Global periods avoid a seed-by-label cross
    product; own-entity history joins only the same entity's earlier windows.
    """
    src, ec, yc = relation(schema, table), ident(entity), ident(target)
    if entity in FEATURES or entity == 'seed_time':
        raise ValueError('entity key collides with the feature contract')
    delta = interval_sql(horizon_microseconds)
    projected = ', '.join('o.' + ident(c) for c in FEATURES[:12])
    return f'''WITH history_rows AS MATERIALIZED (
 SELECT h.{ec} AS entity_key, h.seed_time + {delta} AS available_at, h.{yc}::double precision AS y
 FROM {src} h WHERE h.{yc} IS NOT NULL AND h.seed_time IS NOT NULL
), seed_rows AS MATERIALIZED (
 SELECT s.{ec}, s.seed_time FROM {{seeds}} s
), own_history AS (
 SELECT s.{ec}, s.seed_time,
  count(h.y)::double precision AS oh_count,
  coalesce(sum(h.y),0)::double precision AS oh_sum,
  coalesce(avg(h.y),0)::double precision AS oh_mean,
  coalesce(max(h.y),0)::double precision AS oh_max,
  coalesce(stddev_pop(h.y),0)::double precision AS oh_std,
  coalesce(avg((h.y>0)::int),0)::double precision AS oh_positive_rate,
  count(h.y) FILTER (WHERE h.available_at>s.seed_time-{delta})::double precision AS oh_count_recent,
  coalesce(avg(h.y) FILTER (WHERE h.available_at>s.seed_time-{delta}),0)::double precision AS oh_mean_recent,
  count(h.y) FILTER (WHERE h.available_at>s.seed_time-3*{delta})::double precision AS oh_count_3h,
  coalesce(avg(h.y) FILTER (WHERE h.available_at>s.seed_time-3*{delta}),0)::double precision AS oh_mean_3h,
  coalesce((array_agg(h.y ORDER BY h.available_at DESC NULLS LAST))[1],0)::double precision AS oh_last,
  coalesce(extract(epoch FROM s.seed_time-max(h.available_at))/86400,1000000)::double precision AS oh_days_since_last
 FROM seed_rows s LEFT JOIN history_rows h ON h.entity_key=s.{ec} AND h.available_at<=s.seed_time
 GROUP BY s.{ec},s.seed_time
), history_periods AS (
 SELECT available_at,count(y)::double precision AS n,sum(y)::double precision AS total
 FROM history_rows GROUP BY available_at
), global_history AS (
 SELECT s.seed_time,
  coalesce(sum(h.total)/nullif(sum(h.n),0),0)::double precision AS oh_global_mean,
  coalesce(sum(h.total) FILTER (WHERE h.available_at>s.seed_time-{delta})/
           nullif(sum(h.n) FILTER (WHERE h.available_at>s.seed_time-{delta}),0),0)::double precision AS oh_global_recent,
  coalesce(sum(h.n),0)::double precision AS oh_global_count
 FROM (SELECT DISTINCT seed_time FROM seed_rows) s
 LEFT JOIN history_periods h ON h.available_at<=s.seed_time GROUP BY s.seed_time
)
SELECT o.{ec},o.seed_time,{projected},g.oh_global_mean,g.oh_global_recent,g.oh_global_count
FROM own_history o LEFT JOIN global_history g ON g.seed_time=o.seed_time'''
