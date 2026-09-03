import numba
import numpy as np


@numba.njit(nogil=True)
def _numerical_jacobian(x, y, z, eq, params, J, t=0.0, eps=1e-6):
    xyz = np.empty(3, dtype=np.float64)
    f0 = np.empty(3, dtype=np.float64)
    f1 = np.empty(3, dtype=np.float64)

    xyz[0], xyz[1], xyz[2] = x, y, z
    eq(xyz, t, params, f0)

    xyz[0], xyz[1], xyz[2] = x + eps, y, z
    eq(xyz, t, params, f1)
    for i in range(3):
        J[i, 0] = (f1[i] - f0[i]) / eps

    xyz[0], xyz[1], xyz[2] = x, y + eps, z
    eq(xyz, t, params, f1)
    for i in range(3):
        J[i, 1] = (f1[i] - f0[i]) / eps

    xyz[0], xyz[1], xyz[2] = x, y, z + eps
    eq(xyz, t, params, f1)
    for i in range(3):
        J[i, 2] = (f1[i] - f0[i]) / eps


@numba.njit(nogil=True)
def _augmented_rhs(state, t, params, eq, out, J, dxdydz):
    x, y, z = state[0], state[1], state[2]

    dxdydz_state = state[:3]
    eq(dxdydz_state, t, params, dxdydz)

    _numerical_jacobian(x, y, z, eq, params, J, t)

    out[0] = dxdydz[0]
    out[1] = dxdydz[1]
    out[2] = dxdydz[2]

    # d_theta = J @ theta, where theta is state[3:].reshape(3, 3)
    for row in range(3):
        for col in range(3):
            acc = 0.0
            for k in range(3):
                acc += J[row, k] * state[3 + k * 3 + col]
            out[3 + row * 3 + col] = acc


@numba.njit(nogil=True)
def _rk4_step(state, t, dt, params, eq, tmp, k1, k2, k3, k4, J, dxdydz):
    half_dt = 0.5 * dt
    sixth_dt = dt / 6.0

    _augmented_rhs(state, t, params, eq, k1, J, dxdydz)

    for i in range(12):
        tmp[i] = state[i] + half_dt * k1[i]
    _augmented_rhs(tmp, t + half_dt, params, eq, k2, J, dxdydz)

    for i in range(12):
        tmp[i] = state[i] + half_dt * k2[i]
    _augmented_rhs(tmp, t + half_dt, params, eq, k3, J, dxdydz)

    for i in range(12):
        tmp[i] = state[i] + dt * k3[i]
    _augmented_rhs(tmp, t + dt, params, eq, k4, J, dxdydz)

    for i in range(12):
        state[i] += sixth_dt * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i])


@numba.njit(nogil=True)
def _gram_schmidt(theta_flat):
    lyap_sums = np.zeros(3)
    theta = theta_flat.reshape(3, 3).copy()

    for i in range(3):
        for j in range(i):
            dot = (
                theta[0, i] * theta[0, j]
                + theta[1, i] * theta[1, j]
                + theta[2, i] * theta[2, j]
            )
            for k in range(3):
                theta[k, i] -= dot * theta[k, j]

        norm = np.sqrt(theta[0, i] ** 2 + theta[1, i] ** 2 + theta[2, i] ** 2)
        lyap_sums[i] = np.log(norm)

        for k in range(3):
            theta[k, i] /= norm

    return theta.ravel(), lyap_sums


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
    state = np.zeros(12, dtype=np.float64)
    state[:3] = initial_conditions
    state[3:] = np.eye(3).ravel()
    total_time = t_max - t_min
    dt = total_time / n
    lyap_sums = np.zeros(3)

    gs_counter = 0

    n_gs = n // gs_interval
    t_hist = np.empty(n_gs)
    lyap_hist = np.empty((n_gs, 3))

    tmp = np.empty(12, dtype=np.float64)
    k1 = np.empty(12, dtype=np.float64)
    k2 = np.empty(12, dtype=np.float64)
    k3 = np.empty(12, dtype=np.float64)
    k4 = np.empty(12, dtype=np.float64)
    J = np.empty((3, 3), dtype=np.float64)
    dxdydz = np.empty(3, dtype=np.float64)

    for i in range(n):
        t = t_min + i * dt
        _rk4_step(state, t, dt, params, equation, tmp, k1, k2, k3, k4, J, dxdydz)

        if (i + 1) % gs_interval == 0:
            state[3:], sums = _gram_schmidt(state[3:])
            lyap_sums += sums
            gs_counter += 1

            t_current = gs_counter * gs_interval * dt
            t_hist[gs_counter - 1] = t_current
            lyap_hist[gs_counter - 1] = lyap_sums / t_current

    total_gs_time = gs_counter * gs_interval * dt
    lyap = lyap_sums / total_gs_time

    if lyap[0] + lyap[1] >= 0 > lyap[2]:
        ky = 2.0 + (lyap[0] + lyap[1]) / abs(lyap[2])
    elif lyap[0] < 0:
        ky = 0.0
    else:
        ky = 3.0

    return lyap, ky, t_hist[:gs_counter], lyap_hist[:gs_counter]
