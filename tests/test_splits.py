import pandas as pd

from pmsm_sci.splits import make_grouped_split, split_manifest


def test_grouped_split_has_no_profile_overlap() -> None:
    groups = pd.Series([profile for profile in range(20) for _ in range(5)])
    split = make_grouped_split(groups, seed=7)
    train = set(groups.iloc[split.train])
    validation = set(groups.iloc[split.validation])
    test = set(groups.iloc[split.test])
    assert train.isdisjoint(validation)
    assert train.isdisjoint(test)
    assert validation.isdisjoint(test)
    assert len(split.train) + len(split.validation) + len(split.test) == len(groups)


def test_manifest_covers_every_row() -> None:
    groups = pd.Series([profile for profile in range(10) for _ in range(profile + 1)])
    split = make_grouped_split(groups, seed=11)
    manifest = split_manifest(groups, split)
    assert manifest["n_rows"].sum() == len(groups)
    assert manifest["profile_id"].is_unique
