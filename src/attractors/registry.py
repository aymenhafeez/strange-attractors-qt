from aizawa import _aizawa_attractor
from burker_shaw import _burke_shaw_attractor
from loop_choatic import _loop_chaotic_attractor
from lorenz import _lorenz_attractor
from dadras import _dadras_attractor

ATTRACTORS = {
    "Lorenz": _lorenz_attractor,
    "Aizawa": _aizawa_attractor,
    "Loop chaotic": _loop_chaotic_attractor,
    "Burke-Shaw": _burke_shaw_attractor,
    "Dadras": _dadras_attractor,
}
