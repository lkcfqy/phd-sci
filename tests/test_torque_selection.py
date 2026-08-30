from __future__ import annotations

import numpy as np
import pytest

from pmsm_sci.torque.selection import candidate_grid, select_hyperparameters


def test_candidate_grids_are_frozen_and_nonempty() -> None:
    assert len(candidate_grid("poly2_ridge")) == 4
    assert len(candidate_grid("rbf_kernel_ridge")) == 12
    assert len(candidate_grid("ard_gaussian_process")) == 1
    assert len(candidate_grid("extra_trees")) == 3
    with pytest.raises(ValueError, match="Unknown"):
        candidate_grid("neural_magic")


def test_source_only_selection_returns_one_selected_candidate() -> None:
    generator = np.random.default_rng(4)
    parameters = generator.uniform(size=(36, 3))
    angle = np.arange(24) * 2.0 * np.pi / 24
    amplitude = 0.1 + parameters[:, 0]
    torque = 0.5 + amplitude[:, None] * np.sin(angle)[None, :]
    selected, rows = select_hyperparameters(
        "poly2_ridge",
        parameters,
        torque,
        seed=11,
        retained_components=5,
        candidates=[{"alpha": 1e-5}, {"alpha": 1e-1}],
    )
    assert selected in ({"alpha": 1e-5}, {"alpha": 1e-1})
    assert len(rows) == 2
    assert sum(int(row["selected"]) for row in rows) == 1


def test_ard_gp_uses_fit_only_marginal_likelihood_selection() -> None:
    selected, rows = select_hyperparameters(
        "ard_gaussian_process",
        np.ones((6, 20)),
        np.ones((6, 120)),
        seed=11,
    )
    assert selected == {"dimensions": 20.0, "length_scale_upper": 10.0}
    assert rows[0]["selection_basis"] == "fit-only log marginal likelihood"
    assert rows[0]["selected"] == 1
