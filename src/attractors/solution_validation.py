import numpy as np


MAX_TRAJECTORY_ABS = 1e6


def validate_solutions(solutions, max_abs=MAX_TRAJECTORY_ABS):
    if not solutions:
        return False, "No trajectory data returned"

    for i, sol in enumerate(solutions):
        if not isinstance(sol, np.ndarray):
            return False, f"Trajectory {i + 1} is not an array"
        if sol.ndim != 2 or sol.shape[1] != 3:
            return False, f"Trajectory {i + 1} has invalid shape"
        if sol.shape[0] == 0:
            return False, f"Trajectory {i + 1} is empty"
        if not np.all(np.isfinite(sol)):
            return False, f"Trajectory {i + 1} diverged for current parameters"
        if float(np.max(np.abs(sol))) > max_abs:
            return False, f"Trajectory {i + 1} exceeded display bounds"

    return True, ""
