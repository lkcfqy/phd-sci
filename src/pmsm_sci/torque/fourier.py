"""Fourier reduction for one-period torque signals."""

from __future__ import annotations

import numpy as np


def encode_torque(torque: np.ndarray, retained_components: int = 11) -> np.ndarray:
    """Encode real periodic signals as DC, real, and imaginary Fourier coordinates."""

    values = np.asarray(torque, dtype=float)
    if values.ndim != 2:
        raise ValueError("torque must have shape (designs, angles)")
    maximum = values.shape[1] // 2 + 1
    if not 1 <= retained_components <= maximum:
        raise ValueError(f"retained_components must be between 1 and {maximum}")
    spectrum = np.fft.rfft(values, axis=1)[:, :retained_components]
    return np.concatenate([spectrum.real, spectrum[:, 1:].imag], axis=1)


def decode_torque(
    coordinates: np.ndarray,
    *,
    n_angles: int = 120,
    retained_components: int = 11,
) -> np.ndarray:
    """Reconstruct periodic torque signals from real Fourier coordinates."""

    values = np.asarray(coordinates, dtype=float)
    expected = 2 * retained_components - 1
    if values.ndim != 2 or values.shape[1] != expected:
        raise ValueError(f"coordinates must have shape (designs, {expected})")
    maximum = n_angles // 2 + 1
    if not 1 <= retained_components <= maximum:
        raise ValueError(f"retained_components must be between 1 and {maximum}")

    spectrum = np.zeros((len(values), maximum), dtype=complex)
    spectrum[:, :retained_components] = values[:, :retained_components]
    if retained_components > 1:
        spectrum[:, 1:retained_components] += 1j * values[:, retained_components:]
    return np.fft.irfft(spectrum, n=n_angles, axis=1)


def retained_energy_fraction(torque: np.ndarray, retained_components: int = 11) -> np.ndarray:
    """Return the per-signal fraction of discrete spectral energy retained."""

    values = np.asarray(torque, dtype=float)
    if values.ndim != 2:
        raise ValueError("torque must have shape (designs, angles)")
    spectrum = np.fft.rfft(values, axis=1)
    energy = np.abs(spectrum) ** 2
    return energy[:, :retained_components].sum(axis=1) / energy.sum(axis=1)
