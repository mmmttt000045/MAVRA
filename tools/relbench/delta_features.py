"""Bound a complementary addition to an already computed feature matrix.

No labels, SQL execution or model-service input enter this module. The caller
keeps the complete incumbent unless the checked joined candidate improves it.
"""
from feature_selection import complementary_pool


def delta_pool(base_train, base_valid, importance, added_train, added_valid,
               max_new=12, max_features=100):
    if len(added_train.columns)>max_new:
        raise ValueError(f'at most {max_new} added columns are allowed')
    if max_features<1 or max_new<1:
        raise ValueError('feature limits must be positive')
    varying=[c for c in added_train if added_train[c].nunique(dropna=False)>1]
    constants=[c for c in added_train if c not in varying]
    train,valid,mapping,duplicates=complementary_pool(
        base_train,base_valid,added_train,added_valid,[(c,1.) for c in varying],max_extra=max_new)
    if not mapping:
        raise ValueError('no varying complementary columns; propose a different feature signal')
    available=max_features-len(mapping)
    if available<0:
        raise ValueError('added columns exceed the final feature limit')
    ranked=list(dict.fromkeys([c for c,gain in importance if gain>0 and c in base_train]
                              +list(base_train)))
    selected=set(ranked[:available])
    primary=[c for c in base_train if c in selected]
    names=primary+list(mapping.values())
    return train[names],valid[names],{
        'primary_columns':primary,'added_columns':mapping,'duplicate_columns':duplicates,
        'constant_columns':constants,'dropped_primary':[c for c in base_train if c not in selected],
        'selection_inputs':'training gains and complete train/validation feature values; no labels',
        'features':len(names)}
