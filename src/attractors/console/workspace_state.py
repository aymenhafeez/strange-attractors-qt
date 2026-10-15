import json


def managers(session):
    return {"plot": session.plots, "view3d": session.views3d, "table": session.tables}


def encode_views(session):
    records = []

    for kind, manager in managers(session).items():
        records.extend({"kind": kind, **record} for record in manager.view_records())

    return json.dumps(records)


def decode_views(raw):
    try:
        records = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid workspace view metadata") from exc

    if not isinstance(records, list):
        raise TypeError("Workspace view metadata must be a list")

    seen_ids, seen_names, defaults = set(), set(), set()

    for record in records:
        if not isinstance(record, dict):
            raise TypeError("Invalid workspace view record")
        kind, key, name, default = (
            record.get(k) for k in ("kind", "id", "name", "default")
        )
        if not isinstance(kind, str) or kind not in {"plot", "view3d", "table"}:
            raise ValueError("Unknown workspace view kind")
        if not isinstance(key, str) or not key.startswith(kind + "."):
            raise ValueError("Invalid workspace view ID")
        if not isinstance(name, str) or not name.strip() or name != name.strip():
            raise ValueError("Invalid workspace view name")
        if not isinstance(default, bool):
            raise TypeError("Invalid default-view flag")
        if key in seen_ids or (kind, name) in seen_names:
            raise ValueError("Duplicate workspace view")
        if default != (key == kind + ".default") or (default and kind in defaults):
            raise ValueError("Invalid default-view identity")

        seen_ids.add(key)

        seen_names.add((kind, name))
        if default:
            defaults.add(kind)

    # keep base names for ommitted defaults before mutating theme
    base_names = {"plot": "Plot", "view3d": "3D View", "table": "Table"}
    for kind, name in base_names.items():
        if kind not in defaults and (kind, name) in seen_names:
            raise ValueError("Named view conflicts with an omitted default")

    return records


def restore_views(session, records):
    owners = managers(session)
    for record in records:
        if record["default"]:
            manager = owners[record["kind"]]
            manager.rename(manager._default_name, record["name"])
    for record in records:
        if not record["default"]:
            owners[record["kind"]].new(
                record["name"], activate=False, _dock_id=record["id"]
            )


def active_view_id(session):
    kind, name = session.active_view_key()
    return managers(session)[kind].view_id(name)


def restore_active_target(session, view_id):
    for kind, manager in managers(session).items():
        if kind != "table" and manager.set_current_id(view_id):
            session.set_active_view(kind)
            return
