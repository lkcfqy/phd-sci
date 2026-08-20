"""Transparent, scale-aware features for three-phase current windows."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import stats


def _current_window(values: ArrayLike) -> NDArray[np.float64]:
    current = np.asarray(values, dtype=np.float64)
    if current.ndim != 2 or current.shape[1] != 3:
        raise ValueError("current window must have shape (n_samples, 3)")
    if current.shape[0] < 16:
        raise ValueError("current window must contain at least 16 samples")
    if not np.isfinite(current).all():
        raise ValueError("current window contains non-finite values")
    return current


def clarke_transform(values: ArrayLike) -> NDArray[np.float64]:
    """Return amplitude-invariant alpha, beta, and zero-sequence currents."""

    current = _current_window(values)
    phase_a, phase_b, phase_c = current.T
    alpha = (2.0 / 3.0) * (phase_a - 0.5 * phase_b - 0.5 * phase_c)
    beta = (2.0 / 3.0) * (np.sqrt(3.0) / 2.0) * (phase_b - phase_c)
    zero = (phase_a + phase_b + phase_c) / 3.0
    return np.column_stack([alpha, beta, zero])


def _complex_spectrum(
    current: NDArray[np.float64], sample_rate: float
) -> tuple[NDArray[np.float64], NDArray[np.complex128]]:
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    window = np.hanning(current.shape[0])
    centered = current - current.mean(axis=0, keepdims=True)
    spectrum = (2.0 / window.sum()) * np.fft.rfft(centered * window[:, None], axis=0)
    frequencies = np.fft.rfftfreq(current.shape[0], d=1.0 / sample_rate)
    return frequencies, spectrum


def _fundamental_index(
    frequencies: NDArray[np.float64],
    spectrum: NDArray[np.complex128],
    minimum_hz: float,
    maximum_hz: float,
) -> int:
    tolerance = np.finfo(np.float64).eps * max(abs(maximum_hz), 1.0) * 16
    mask = (frequencies >= minimum_hz - tolerance) & (
        frequencies <= maximum_hz + tolerance
    )
    if not mask.any():
        raise ValueError("window is too short to resolve the requested frequency band")
    band_indices = np.flatnonzero(mask)
    mean_magnitude = np.mean(np.abs(spectrum), axis=1)
    return int(band_indices[np.argmax(mean_magnitude[mask])])


def _unbalance_from_phasors(phasors: NDArray[np.complex128]) -> float:
    rotation = np.exp(2j * np.pi / 3)
    sequence_one = (phasors[0] + rotation * phasors[1] + rotation**2 * phasors[2]) / 3
    sequence_two = (phasors[0] + rotation**2 * phasors[1] + rotation * phasors[2]) / 3
    larger = max(abs(sequence_one), abs(sequence_two))
    if larger <= np.finfo(np.float64).eps:
        return 0.0
    return float(min(abs(sequence_one), abs(sequence_two)) / larger)


def estimate_fundamental_frequency(
    values: ArrayLike,
    sample_rate: float,
    *,
    minimum_hz: float = 20.0,
    maximum_hz: float = 500.0,
) -> float:
    """Estimate the strongest phase-A spectral component in a physical band."""

    current = _current_window(values)
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if not 0 < minimum_hz < maximum_hz < sample_rate / 2:
        raise ValueError("frequency bounds must lie inside the Nyquist interval")
    frequencies, spectrum = _complex_spectrum(current, sample_rate)
    index = _fundamental_index(frequencies, spectrum, minimum_hz, maximum_hz)
    return float(frequencies[index])


def sequence_unbalance_ratio(
    values: ArrayLike, sample_rate: float, fundamental_hz: float
) -> float:
    """Return an orientation-invariant negative/positive sequence magnitude ratio."""

    current = _current_window(values)
    if sample_rate <= 0 or not 0 < fundamental_hz < sample_rate / 2:
        raise ValueError("invalid sample or fundamental frequency")
    times = np.arange(current.shape[0], dtype=np.float64) / sample_rate
    kernel = np.exp(-2j * np.pi * fundamental_hz * times)
    phasors = (2.0 / current.shape[0]) * (current.T @ kernel)
    return _unbalance_from_phasors(phasors)


def current_features(values: ArrayLike, sample_rate: float) -> dict[str, float]:
    """Extract the first transparent feature set from one current window."""

    current = _current_window(values)
    rms = np.sqrt(np.mean(np.square(current), axis=0))
    peak = np.max(np.abs(current), axis=0)
    clarke = clarke_transform(current)
    frequencies, spectrum = _complex_spectrum(current, sample_rate)
    fundamental_index = _fundamental_index(frequencies, spectrum, 20.0, 500.0)
    fundamental = float(frequencies[fundamental_index])
    fundamental_amplitudes = np.abs(spectrum[fundamental_index])
    fundamental_mean = float(np.mean(fundamental_amplitudes))
    epsilon = np.finfo(float).eps
    harmonic_ratios: list[NDArray[np.float64]] = []
    for harmonic in range(2, 6):
        target = harmonic * fundamental
        index = int(np.argmin(np.abs(frequencies - target)))
        ratio = np.abs(spectrum[index]) / (fundamental_amplitudes + epsilon)
        harmonic_ratios.append(ratio)

    spectral_band = (frequencies >= 20.0) & (frequencies <= min(2_000.0, sample_rate / 2))
    spectral_power = np.mean(np.abs(spectrum[spectral_band]) ** 2, axis=1)
    probabilities = spectral_power / (spectral_power.sum() + epsilon)
    spectral_entropy = -np.sum(probabilities * np.log(probabilities + epsilon))
    spectral_entropy /= np.log(max(probabilities.size, 2))

    sideband_ratios: dict[str, float] = {}
    for label, factor in (("lower", 0.75), ("upper", 1.25)):
        index = int(np.argmin(np.abs(frequencies - factor * fundamental)))
        sideband_ratios[f"sideband_{label}_ratio"] = float(
            np.mean(np.abs(spectrum[index])) / (fundamental_mean + epsilon)
        )
    result: dict[str, float] = {
        "fundamental_hz": fundamental,
        "sequence_unbalance": _unbalance_from_phasors(spectrum[fundamental_index]),
        "fundamental_amplitude_mean": fundamental_mean,
        "fundamental_amplitude_cv": float(
            np.std(fundamental_amplitudes) / (fundamental_mean + epsilon)
        ),
        "phase_rms_cv": float(np.std(rms) / (np.mean(rms) + epsilon)),
        "clarke_radius_mean": float(np.mean(np.hypot(clarke[:, 0], clarke[:, 1]))),
        "clarke_radius_cv": float(
            np.std(np.hypot(clarke[:, 0], clarke[:, 1]))
            / (np.mean(np.hypot(clarke[:, 0], clarke[:, 1])) + epsilon)
        ),
        "zero_sequence_rms": float(np.sqrt(np.mean(np.square(clarke[:, 2])))),
        "zero_sequence_ratio": float(
            np.sqrt(np.mean(np.square(clarke[:, 2]))) / (np.mean(rms) + epsilon)
        ),
        "spectral_entropy": float(spectral_entropy),
        **sideband_ratios,
    }
    for harmonic, ratio in enumerate(harmonic_ratios, start=2):
        result[f"harmonic_{harmonic}_ratio_mean"] = float(np.mean(ratio))
        result[f"harmonic_{harmonic}_ratio_max"] = float(np.max(ratio))
    stacked_harmonics = np.stack(harmonic_ratios)
    result["thd_2_to_5_mean"] = float(
        np.mean(np.sqrt(np.sum(np.square(stacked_harmonics), axis=0)))
    )
    for index, phase in enumerate(("a", "b", "c")):
        result[f"rms_{phase}"] = float(rms[index])
        result[f"rms_ratio_{phase}"] = float(rms[index] / (np.mean(rms) + epsilon))
        result[f"crest_{phase}"] = float(peak[index] / (rms[index] + epsilon))
        result[f"kurtosis_{phase}"] = float(stats.kurtosis(current[:, index], fisher=False))
    return result
