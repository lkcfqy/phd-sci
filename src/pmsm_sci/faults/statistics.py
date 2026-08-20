"""Small-sample statistical summaries used by the fault experiments."""

from __future__ import annotations

from statistics import NormalDist

import numpy as np


def wilson_interval(
    successes: int, trials: int, confidence: float = 0.95
) -> tuple[float, float]:
    """Return a two-sided Wilson score interval for a binomial proportion."""

    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("successes and trials must define a non-empty binomial sample")
    if not 0 < confidence < 1:
        raise ValueError("confidence must lie in (0, 1)")
    z_value = NormalDist().inv_cdf(0.5 + confidence / 2)
    proportion = successes / trials
    denominator = 1 + z_value**2 / trials
    center = (proportion + z_value**2 / (2 * trials)) / denominator
    radius = (
        z_value
        * np.sqrt(
            proportion * (1 - proportion) / trials + z_value**2 / (4 * trials**2)
        )
        / denominator
    )
    return float(max(0.0, center - radius)), float(min(1.0, center + radius))
