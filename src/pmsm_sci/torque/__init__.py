"""Periodic PMSM torque-surrogate and curvewise uncertainty tools."""

from .conformal import (
    KnnGeometryScaler,
    conformal_quantile,
    curvewise_max_error,
    support_p_values,
    wilson_interval,
)
from .covariate_shift import (
    QuadraticLogisticDensityRatio,
    effective_sample_size,
    weighted_conformal_quantiles,
)
from .data import TorqueDataset, load_published_torque_data
from .fourier import decode_torque, encode_torque
from .models import FourierSurrogate, build_regressor
from .selection import candidate_grid, select_hyperparameters
from .splits import TorqueSplit, make_primary_split

__all__ = [
    "FourierSurrogate",
    "KnnGeometryScaler",
    "QuadraticLogisticDensityRatio",
    "TorqueDataset",
    "TorqueSplit",
    "build_regressor",
    "candidate_grid",
    "conformal_quantile",
    "curvewise_max_error",
    "decode_torque",
    "effective_sample_size",
    "encode_torque",
    "load_published_torque_data",
    "make_primary_split",
    "select_hyperparameters",
    "support_p_values",
    "weighted_conformal_quantiles",
    "wilson_interval",
]
