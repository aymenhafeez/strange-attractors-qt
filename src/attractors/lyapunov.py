import numba
import numpy as np


@numba.njit(nogil=True)
def _numerical_jacobian(x, y, z, eq, params, eps=1e-6):
    xyz = np.array([x, y, z])
    f0 = eq(xyz, 0.0, params)
    J = np.zeros((3, 3))
    xyz0 = np.array([x + eps, y, z])
    xyz1 = np.array([x, y + eps, z])
    xyz2 = np.array([x, y, z + eps])
    J[:, 0] = (eq(xyz0, 0.0, params) - f0) / eps
    J[:, 1] = (eq(xyz1, 0.0, params) - f0) / eps
    J[:, 2] = (eq(xyz2, 0.0, params) - f0) / eps

    return J


@numba.njit(nogil=True)
def _augmented_rhs(state, params, eq):
    x, y, z = state[0], state[1], state[2]
    xyz = np.array([x, y, z])
    dxdydz = eq(xyz, 0.0, params)
    J = _numerical_jacobian(x, y, z, eq, params)
    theta = state[3:].reshape(3, 3)
    d_theta = J @ theta
    out = np.zeros(12)
    out[0], out[1], out[2] = dxdydz[0], dxdydz[1], dxdydz[2]
    out[3:] = d_theta.ravel()

    return out


@numba.njit(nogil=True)
def _rk4_step(state, dt, params, eq):
    k1 = _augmented_rhs(state, params, eq)
    k2 = _augmented_rhs(state + 0.5 * dt * k1, params, eq)
    k3 = _augmented_rhs(state + 0.5 * dt * k2, params, eq)
    k4 = _augmented_rhs(state + dt * k3, params, eq)

    return state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


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


def compute_lyapunov(
    equation,
    initial_conditions,
    params,
    t_min,
    t_max,
    n,
    gs_interval=10,
    return_history=False,
):
    state = np.zeros(12, dtype=np.float64)
    state[:3] = initial_conditions
    state[3:] = np.eye(3).ravel()
    total_time = t_max - t_min
    dt = total_time / n
    p = np.array(params, dtype=np.float64)
    lyap_sums = np.zeros(3)

    gs_counter = 0

    if return_history:
        t_hist = []
        lyap_hist = []

    for i in range(n):
        state = _rk4_step(state, dt, p, equation)

        if (i + 1) % gs_interval == 0:
            state[3:], sums = _gram_schmidt(state[3:])
            lyap_sums += sums
            gs_counter += 1

            if return_history:
                t_current = gs_counter * gs_interval * dt
                t_hist.append(t_current)
                lyap_hist.append(lyap_sums / t_current)

    total_gs_time = gs_counter * gs_interval * dt
    lyap = lyap_sums / total_gs_time

    if lyap[0] + lyap[1] >= 0 and lyap[2] < 0:
        ky = 2.0 + (lyap[0] + lyap[1]) / abs(lyap[2])
    elif lyap[0] < 0:
        ky = 0.0
    else:
        ky = 3.0

    if return_history:
        return lyap, ky, np.array(t_hist), np.array(lyap_hist)

    return lyap, ky
