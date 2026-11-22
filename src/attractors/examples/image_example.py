"""Image example showing the mandelbrot set

Each pixel represets how many iterations of z to z**2 + c it takes to pass |z| > 2 at
which point the orbit grows without bound. Points that never pass this are NaN and drawn
transparent. Use the sliders to move the centre and zoom in and raise the number of
iterations as you zoom in

cool centres:
x=-0.7453, y=0.1127
x=-1.7686, y=0.0017
"""

import numpy as np
from numba import njit


@njit
def escape_times(x0, x1, y0, y1, nx, ny, max_iter):
    out = np.full((ny, nx), np.nan)

    for iy in range(ny):
        # sample pixel centres so the image lines up exactly with its extent
        cy = y0 + (y1 - y0) * (iy + 0.5) / ny
        for ix in range(nx):
            cx = x0 + (x1 - x0) * (ix + 0.5) / nx
            zx = zy = 0.0
            for i in range(max_iter):
                zx, zy = zx * zx - zy * zy + cx, 2 * zx * zy + cy
                if zx * zx + zy * zy > 4.0:
                    out[iy, ix] = i
                    break

    return out


mandelbrot = plots.new("Mandelbrot")
cx = mandelbrot.explore.slider(
    "x", value=-0.75, start=-2.0, end=1.0, step=0.0001
)
cy = mandelbrot.explore.slider(
    "y", value=0.0, start=-1.5, end=1.5, step=0.0001
)
zoom = mandelbrot.explore.slider("zoom", value=0.0, start=0.0, end=14.0,
step=0.1)
iterations = mandelbrot.explore.int_slider(
    "iterations", value=200, start=50, end=3000, step=50
)


# bind values locally so later console assignments with the same names don't
# affect this plot
def view(cx=cx, cy=cy, zoom=zoom):
    half_width = 1.5 / 2**zoom.value
    half_height = half_width * 2 / 3
    return (
        cx.value - half_width,
        cx.value + half_width,
        cy.value - half_height,
        cy.value + half_height,
    )


mandelbrot.explore.image(
    "Mandelbrot",
    lambda iterations=iterations: np.log1p(
        escape_times(*view(), 600, 400, int(iterations.value))
    ),
    extent=view,
)
