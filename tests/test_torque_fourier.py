from __future__ import annotations

import numpy as np
import pytest

from pmsm_sci.torque.fourier import decode_torque, encode_torque, retained_energy_fraction


def test_fourier_roundtrip_when_all_components_retained() -> None:
    generator = np.random.default_rng(3)
    torque = generator.normal(size=(7, 120))
    encoded = encode_torque(torque, retained_components=61)
    reconstructed = decode_torque(encoded, n_angles=120, retained_components=61)
    np.testing.assert_allclose(reconstructed, torque, atol=1e-12)


def test_low_harmonic_periodic_curve_is_exactly_reconstructed() -> None:
    angle = np.arange(120) * 2.0 * np.pi / 120
    torque = np.stack([0.5 + 0.1 * np.sin(3 * angle), 0.4 + 0.03 * np.cos(7 * angle)])
    encoded = encode_torque(torque, retained_components=11)
    reconstructed = decode_torque(encoded, n_angles=120, retained_components=11)
    np.testing.assert_allclose(reconstructed, torque, atol=1e-12)
    np.testing.assert_allclose(retained_energy_fraction(torque, 11), 1.0, atol=1e-12)


def test_fourier_shape_validation() -> None:
    with pytest.raises(ValueError, match="shape"):
        encode_torque(np.ones(120))
    with pytest.raises(ValueError, match="coordinates"):
        decode_torque(np.ones((2, 20)), retained_components=11)
