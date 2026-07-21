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
