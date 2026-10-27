# SPDX-FileCopyrightText: 2026 Aymen Hafeez
# SPDX-License-Identifier: GPL-3.0-only

import numba
import numpy as np


@numba.njit(nogil=True)
def _numerical_jacobian(state, eq, params, J, t=0.0, eps=1e-6):
    dimension = len(state)
    perturbed = state.copy()
    f0 = np.empty(dimension, dtype=np.float64)
    f1 = np.empty(dimension, dtype=np.float64)

    eq(state, t, params, f0)

    for col in range(dimension):
        perturbed[col] += eps
        eq(perturbed, t, params, f1)

        for row in range(dimension):
            J[row, col] = (f1[row] - f0[row]) / eps

        perturbed[col] = state[col]


@numba.njit(nogil=True)
def _augmented_rhs(state, t, params, eq, out, J, derivative):
    dimension = len(derivative)
    coordinates = state[:dimension]

    eq(coordinates, t, params, derivative)
    _numerical_jacobian(coordinates, eq, params, J, t)
    out[:dimension] = derivative

    for row in range(dimension):
        for col in range(dimension):
            value = 0.0

            for k in range(dimension):
                value += J[row, k] * state[dimension + k * dimension + col]

            out[dimension + row * dimension + col] = value


@numba.njit(nogil=True)
def _rk4_step(state, t, dt, params, eq, tmp, k1, k2, k3, k4, J, dimension):
    half_dt = 0.5 * dt
    sixth_dt = dt / 6.0

    _augmented_rhs(state, t, params, eq, k1, J, dimension)

    for i in range(len(state)):
        tmp[i] = state[i] + half_dt * k1[i]
    _augmented_rhs(tmp, t + half_dt, params, eq, k2, J, dimension)

    for i in range(len(state)):
        tmp[i] = state[i] + half_dt * k2[i]
    _augmented_rhs(tmp, t + half_dt, params, eq, k3, J, dimension)

    for i in range(len(state)):
        tmp[i] = state[i] + dt * k3[i]
    _augmented_rhs(tmp, t + dt, params, eq, k4, J, dimension)

    for i in range(len(state)):
        state[i] += sixth_dt * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i])


@numba.njit(nogil=True)
def _gram_schmidt(theta_flat):
    dimension = int(np.sqrt(len(theta_flat)))
    theta = theta_flat.reshape(dimension, dimension).copy()
    lyap_sums = np.empty(dimension)

    for col in range(dimension):
        for previous in range(col):
            dot = 0.0

            for row in range(dimension):
                dot += theta[row, col] * theta[row, previous]

            for row in range(dimension):
                theta[row, col] -= dot * theta[row, previous]

        norm_squared = 0.0
        for row in range(dimension):
            norm_squared += theta[row, col] ** 2

        norm = np.sqrt(norm_squared)
        if norm == 0.0 or not np.isfinite(norm):
            raise ValueError("Lyapunov tangent basis became singular or non-finite")

        lyap_sums[col] = np.log(norm)

        for row in range(dimension):
            theta[row, col] /= norm

    return theta.ravel(), lyap_sums


@numba.njit(nogil=True)
def kaplan_yorke(exponents):
    ordered = np.sort(exponents)[::-1]
    total = 0.0

    for index in range(len(ordered)):
        next_total = total + ordered[index]

        if next_total < 0.0:
            return index + total / abs(ordered[index])

        total = next_total

    return len(ordered)


@numba.njit(nogil=True)
def compute_lyapunov(
    equation,
    initial_conditions,
    params,
    t_min,
    t_max,
    n,
    gs_interval=10,
):
    dimension = len(initial_conditions)
    state_size = dimension + dimension**2

    state = np.zeros(state_size)
    state[:dimension] = initial_conditions
    state[dimension:] = np.eye(dimension).ravel()

    total_time = t_max - t_min
    dt = total_time / n
    lyap_sums = np.zeros(dimension)
    gs_counter = 0

    n_gs = n // gs_interval
    t_hist = np.empty(n_gs)
    lyap_hist = np.empty((n_gs, dimension))

    tmp = np.empty(state_size)
    k1 = np.empty(state_size)
    k2 = np.empty(state_size)
    k3 = np.empty(state_size)
    k4 = np.empty(state_size)
    J = np.empty((dimension, dimension))
    derivative = np.empty(dimension)

    for i in range(n):
        t = t_min + i * dt
        _rk4_step(state, t, dt, params, equation, tmp, k1, k2, k3, k4, J, derivative)

        if (i + 1) % gs_interval == 0:
            state[dimension:], sums = _gram_schmidt(state[dimension:])
            lyap_sums += sums
            gs_counter += 1

            t_current = gs_counter * gs_interval * dt
            t_hist[gs_counter - 1] = t_current
            lyap_hist[gs_counter - 1] = lyap_sums / t_current

    total_gs_time = gs_counter * gs_interval * dt
    lyap = lyap_sums / total_gs_time

    ky = kaplan_yorke(lyap)

    return lyap, ky, t_hist[:gs_counter], lyap_hist[:gs_counter]
