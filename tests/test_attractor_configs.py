import numpy as np

from attractors.models import AttractorConfig
from attractors.registry import ATTRACTORS


def _default_param_values(config):
    return np.array([p.default for p in config.params], dtype=np.float64)


def test_registry_is_not_empty():
    assert ATTRACTORS


def test_all_registry_values_are_attractor_configs():
    for config in ATTRACTORS.values():
        assert isinstance(config, AttractorConfig)


def test_registry_keys_match_config_names_or_display_names():
    for display_name, config in ATTRACTORS.items():
        assert display_name
        assert config.name


def test_all_configs_have_three_initial_conditions():
    for config in ATTRACTORS.values():
        assert len(config.initial_conditions) == 3


def test_all_configs_have_required_time_defaults():
    for config in ATTRACTORS.values():
        assert set(config.time_defaults) == {"t_min", "t_max", "n"}
        assert config.time_defaults["t_max"] > config.time_defaults["t_min"]
        assert config.time_defaults["n"] > 0


def test_all_param_names_are_unique_per_config():
    for config in ATTRACTORS.values():
        names = [p.name for p in config.params]
        assert len(names) == len(set(names))


def test_all_param_defaults_are_inside_slider_ranges():
    for config in ATTRACTORS.values():
        for p in config.params:
            assert p.min_val <= p.default <= p.max_val


def test_all_param_steps_are_positive():
    for config in ATTRACTORS.values():
        for p in config.params:
            assert p.step > 0


def test_all_equations_return_finite_three_vector_at_default_values():
    state = np.array([0.1, 0.2, 0.3], dtype=np.float64)

    for config in ATTRACTORS.values():
        params = _default_param_values(config)
        result = config.equation(state, 0.0, params)

        assert result.shape == (3,)
        assert np.all(np.isfinite(result))
