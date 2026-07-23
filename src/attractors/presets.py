import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .expression_parser import compile_system, format_equations
from .models import AttractorConfig, AttractorParam
from .registry import ATTRACTORS

PRESET_VERSION = 1
PRESET_SUFFIX = ".json"


class PresetError(ValueError):
    pass


def preset_filename(name):
    cleaned = re.sub(r"[^A-Za-z0-9_. -]+", "", name).strip()
    cleaned = re.sub(r"\s+", "-", cleaned).strip(".-")
    if not cleaned:
        raise PresetError("Preset name is required")
    return f"{cleaned}{PRESET_SUFFIX}"


def preset_path(directory, name):
    return Path(directory) / preset_filename(name)


def _utc_timestamp():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _param_to_dict(param):
    return {
        "name": param.name,
        "default": float(param.default),
        "min": float(param.min_val),
        "max": float(param.max_val),
        "step": float(param.step),
    }


def _param_from_dict(data):
    try:
        return AttractorParam(
            str(data["name"]),
            float(data["default"]),
            float(data["min"]),
            float(data["max"]),
            float(data["step"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PresetError("Invalid parameter data") from exc


def _custom_equations_from_config(config):
    equations = []
    for line in config.equation_text.splitlines():
        _, sep, rhs = line.partition("=")
        if not sep:
            return None
        equations.append(rhs.strip())

    if len(equations) != 3 or not all(equations):
        return None

    return equations


def _preset_name_for_config(config):
    if config.name == "Custom":
        return "Custom"

    for name, registered_config in ATTRACTORS.items():
        if registered_config is config:
            return name

    return config.name


def custom_config_from_preset_data(data):
    try:
        equations = [str(eq) for eq in data["equations"]]
    except (KeyError, TypeError) as exc:
        raise PresetError("Custom preset is missing equations") from exc

    if len(equations) != 3 or not all(equations):
        raise PresetError("Custom preset requires three equations")

    func, detected_params = compile_system(tuple(equations))
    params_by_name = {
        param.name: param
        for param in [_param_from_dict(p) for p in data.get("params", [])]
    }
    params = []
    for name in detected_params:
        param = params_by_name.get(name)
        if param is None:
            raise PresetError(f"Custom preset is missing range for parameter '{name}'")
        params.append(param)

    try:
        initial_conditions = [float(v) for v in data["initial_conditions"]]
        time_defaults = {
            "t_min": int(data.get("time_defaults", {}).get("t_min", 0)),
            "t_max": int(data["t_max"]),
            "n": int(data["n"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise PresetError("Invalid custom preset values") from exc

    if len(initial_conditions) != 3:
        raise PresetError("Custom preset requires three initial conditions")

    return AttractorConfig(
        name="Custom",
        equation=func,
        params=params,
        initial_conditions=initial_conditions,
        time_defaults=time_defaults,
        equation_text=format_equations(tuple(equations)),
        description="User-defined custom attractor",
    )


def build_preset(
    config,
    values,
    n,
    t_max,
    preset_name=None,
    notes="",
    created_at=None,
    updated_at=None,
):
    attractor_name = _preset_name_for_config(config)
    now = updated_at or _utc_timestamp()
    preset = {
        "version": PRESET_VERSION,
        "attractor": attractor_name,
        "values": {str(k): float(v) for k, v in values.items()},
        "n": int(n),
        "t_max": int(t_max),
        "notes": str(notes or ""),
        "created_at": created_at or now,
        "updated_at": now,
    }
    if preset_name is not None:
        preset["name"] = str(preset_name)

    if attractor_name == "Custom":
        equations = _custom_equations_from_config(config)
        if equations is None:
            raise PresetError("Custom attractor cannot be saved without equations")
        preset.update(
            {
                "equations": equations,
                "initial_conditions": [float(v) for v in config.initial_conditions],
                "params": [_param_to_dict(param) for param in config.params],
            }
        )

    return preset


def save_preset(
    path,
    config,
    values,
    n,
    t_max,
    preset_name=None,
    notes="",
    created_at=None,
):
    preset = build_preset(config, values, n, t_max, preset_name, notes, created_at)
    try:
        Path(path).write_text(json.dumps(preset, indent=2), encoding="utf-8")
    except OSError as exc:
        raise PresetError(f"Could not save preset: {exc}") from exc


def load_preset(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise PresetError(f"Could not read preset: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PresetError("Preset file is not valid JSON") from exc

    if data.get("version") != PRESET_VERSION:
        raise PresetError("Unsupported preset version")

    name = data.get("attractor")
    if name == "Custom":
        config = custom_config_from_preset_data(data)
    elif name in ATTRACTORS:
        config = ATTRACTORS[name]
    else:
        raise PresetError(f"Unknown attractor preset: {name}")

    try:
        values = {str(k): float(v) for k, v in data.get("values", {}).items()}
        n = int(data["n"])
        t_max = int(data["t_max"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PresetError("Invalid preset values") from exc

    return config, values, n, t_max


def list_presets(directory):
    path = Path(directory)
    if not path.exists():
        return []

    names = []
    for preset_file in path.glob(f"*{PRESET_SUFFIX}"):
        try:
            data = json.loads(preset_file.read_text(encoding="utf-8"))
            name = data.get("name") if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            continue
        names.append(str(name or preset_file.stem))

    return sorted(names, key=str.casefold)


def preset_metadata(directory, name):
    try:
        data = json.loads(preset_path(directory, name).read_text(encoding="utf-8"))
    except OSError as exc:
        raise PresetError(f"Could not read preset: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PresetError("Preset file is not valid JSON") from exc

    if not isinstance(data, dict):
        raise PresetError("Preset file is not valid")

    return {
        "name": str(data.get("name") or name),
        "attractor": str(data.get("attractor") or "Unknown"),
        "n": data.get("n"),
        "t_max": data.get("t_max"),
        "parameter_count": len(data.get("values", {})),
        "notes": str(data.get("notes") or ""),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "is_custom": data.get("attractor") == "Custom",
    }


def save_named_preset(directory, name, config, values, n, t_max, notes=""):
    path = preset_path(directory, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    created_at = None
    if path.exists():
        try:
            created_at = preset_metadata(directory, name).get("created_at")
        except PresetError:
            created_at = None
    save_preset(
        path,
        config,
        values,
        n,
        t_max,
        preset_name=name,
        notes=notes,
        created_at=created_at,
    )
    return path


def load_named_preset(directory, name):
    return load_preset(preset_path(directory, name))


def delete_named_preset(directory, name):
    try:
        preset_path(directory, name).unlink()
    except FileNotFoundError as exc:
        raise PresetError(f"Preset not found: {name}") from exc
    except OSError as exc:
        raise PresetError(f"Could not delete preset: {exc}") from exc
