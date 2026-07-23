import json

from pyqtgraph.Qt import QtCore

SESSION_VERSION = 1
SESSION_KEY = "session/state"
ORGANISATION = "strange-attractors-qt"
APPLICATION = "Strange Attractors"


def session_settings():
    return QtCore.QSettings(ORGANISATION, APPLICATION)


def save_session(settings, state):
    data = dict(state)
    data["version"] = SESSION_VERSION
    settings.setValue(SESSION_KEY, json.dumps(data))


def clear_session(settings):
    settings.remove(SESSION_KEY)


def load_session(settings):
    raw = settings.value(SESSION_KEY, "")
    if not raw:
        return {}

    try:
        data = json.loads(str(raw))
    except (TypeError, json.JSONDecodeError):
        return {}

    if not isinstance(data, dict) or data.get("version") != SESSION_VERSION:
        return {}

    return data
