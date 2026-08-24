import numpy as np
from scipy.integrate import solve_ivp

g = 9.81
L = 1.0

duration = 40.0
samples = 10000
t = np.linspace(0.0, duration, samples)


def spherical_pendulum(t, state):
    theta, theta_dot, phi, phi_dot = state

    sin_theta = np.sin(theta)
    cos_theta = np.cos(theta)

    # avoid numbers blowing up if the path gets extremely close to the pole
    safe_sin = np.sign(sin_theta) * max(abs(sin_theta), 1e-8)

    theta_ddot = sin_theta * cos_theta * phi_dot**2 - (g / L) * sin_theta
    phi_ddot = -2.0 * theta_dot * phi_dot * cos_theta / safe_sin

    return [theta_dot, theta_ddot, phi_dot, phi_ddot]


initial = [np.radians(65.0), 0.0, 0.0, 2.3]

solution = solve_ivp(
    spherical_pendulum,
    (t[0], t[-1]),
    initial,
    t_eval=t,
    rtol=1e-10,
    atol=1e-10,
)

theta = solution.y[0]
phi = solution.y[2]

x = L * np.sin(theta) * np.cos(phi)
y = L * np.sin(theta) * np.sin(phi)
z = -L * np.cos(theta)

view = views3d.new("Spherical pendulum")

rod = view.line3d(
    [],
    [],
    [],
    colour=(0.9, 0.9, 0.85, 1.0),
    width=3,
    mode="overlay",
)

bob = view.scatter3d(
    [],
    [],
    [],
    colour=(1.0, 0.55, 0.2, 1.0),
    size=25,
    mode="overlay",
)

pivot = view.scatter3d(
    [],
    [],
    [],
    colour=(0.95, 0.95, 1.0, 1.0),
    size=15,
    mode="overlay",
)

trail = view.line3d(
    [],
    [],
    [],
    colour=(0.2, 0.8, 1.0, 0.85),
    width=2,
    mode="overlay",
)

circle_u = np.linspace(0.0, 2.0 * np.pi, 100)

equator = view.line3d(
    L * np.cos(circle_u),
    L * np.sin(circle_u),
    np.zeros_like(circle_u),
    colour="gray",
    width=5,
    mode="overlay",
)

axis = view.line3d(
    [0.0, 0.0],
    [0.0, 0.0],
    [-L, 0.25 * L],
    colour=(1.0, 1.0, 1.0, 0.55),
    width=1,
    mode="overlay",
)

step = 5
trail_length = 1200


def as_points(x, y, z):
    return np.column_stack([x, y, z])


# bind callback inputs so other console scripts don't overwrite them
def update(
    anim,
    rod=rod,
    bob=bob,
    trail=trail,
    x=x,
    y=y,
    z=z,
    samples=samples,
    trail_length=trail_length,
    frame_step=step,
    as_points=as_points,
):
    i = (anim.frame * frame_step) % samples
    start = max(0, i - trail_length)

    rod.setData(pos=as_points([0.0, x[i]], [0.0, y[i]], [0.0, z[i]]))
    bob.setData(pos=as_points([x[i]], [y[i]], [z[i]]))
    trail.setData(pos=as_points(x[start : i + 1], y[start : i + 1], z[start : i + 1]))


view.explore.animation("Pendulum", callback=update, frames=1000)
view.fit()
view.orbit(True)
view.grid(False)
