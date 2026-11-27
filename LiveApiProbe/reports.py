"""What the probe serves: Live's Python API, read from the running Live.

Each report returns (content type, text) and must run on Live's main thread.
To change or add one, edit this file (and ROUTES in probe.py) and restart
Live.
"""

import html
import importlib
import inspect
import json
import os
import re

import Live

_LISTENER = re.compile(r"^(?:add|remove)_(\w+)_listener$|^(\w+)_has_listener$")
_PAGE = os.path.join(os.path.dirname(__file__), "page.html")

_HTML = "text/html; charset=utf-8"
_JSON = "application/json"
_TEXT = "text/plain; charset=utf-8"


def api_json():
    """Every class, member, enum value and module function, with help text."""
    return _JSON, json.dumps(collect(), indent=2, sort_keys=True) + "\n"


def page():
    """The same data as one self-contained web page."""
    api = collect()
    with open(_PAGE, encoding="utf-8") as file:
        page = file.read()

    # "</" would end the page's data block early.
    data = json.dumps(api, sort_keys=True).replace("</", "<\\/")
    page = page.replace("__VERSION__", html.escape(api["version"]))
    return _HTML, page.replace("__DATA__", data)


def python_vs_max():
    """The members Max for Live's LiveAPI can't reach, as text."""
    api = collect()
    lines = ["# Python members Max can't reach (Live %s)" % api["version"]]
    unreachable = []

    for path in sorted(api["classes"]):
        cls = api["classes"][path]
        members = [m for m in cls["members"] if m["kind"] in ("property", "method")]
        if not cls["max"]:
            if members:
                unreachable.append(path)
            continue

        missing = [m["name"] for m in members if not m["max"]]
        if missing:
            lines += ["", "## " + path, ", ".join(missing)]

    lines += ["", "## Classes Max can't reach at all", ", ".join(unreachable)]
    lines += ["", "## Module functions (Max can't call any)"]
    lines += [", ".join(sorted(api["functions"])), ""]
    return _TEXT, "\n".join(lines)


def collect():
    """Walk the `Live` module.

    Classes and enums are keyed by where they're found: "Song.Song" is
    Live.Song.Song, "Song.Song.View" the View class nested in it.
    """
    classes = {}
    enums = {}
    functions = {}
    # Class id -> the path it was first found at, so each is listed once.
    paths = {}
    max_allowed = _max_allowed()

    def visit(cls, path):
        if id(cls) in paths:
            return
        paths[id(cls)] = path

        if issubclass(cls, int):
            values = getattr(cls, "names", {})
            enums[path] = {str(k): int(v) for k, v in values.items()}
            return

        allowed = max_allowed.get(cls)
        members = []
        observable = set()

        for name in _names(cls):
            listener = _LISTENER.match(name)
            if listener:
                # Folded into its property as `observable`.
                observable.add(listener.group(1) or listener.group(2))
                continue

            value = getattr(cls, name, None)
            if inspect.isclass(value):
                if value.__module__ != "builtins":
                    visit(value, path + "." + name)
                    ref = paths[id(value)]
                    members.append({"name": name, "kind": "class", "ref": ref})
                continue

            member = {"name": name, "doc": _doc(value)}
            if isinstance(value, property):
                member["kind"] = "property"
                if value.fset is None:
                    member["readonly"] = True
            else:
                member["kind"] = "method" if callable(value) else "value"
            # Whether Max for Live can use it.
            member["max"] = allowed is not None and name in allowed
            members.append(member)

        for member in members:
            if member["name"] in observable:
                member["observable"] = True

        classes[path] = {
            "doc": _doc(cls) if "__doc__" in vars(cls) else "",
            # False: Max can't reach the class at all.
            "max": allowed is not None,
            "members": members,
        }

    for module_name in _names(Live):
        module = getattr(Live, module_name)
        if not inspect.ismodule(module):
            continue
        for name in _names(module):
            value = getattr(module, name)
            if inspect.isclass(value):
                visit(value, module_name + "." + name)
            elif callable(value):
                functions[module_name + "." + name] = _doc(value)

    return {
        "version": _version(),
        "classes": classes,
        "enums": enums,
        "functions": functions,
    }


def _version():
    return Live.Application.get_application().get_version_string()


def _max_allowed():
    """Per class, the member names Max for Live's LiveAPI may use.

    Max goes through Live's own _MxDCore package, which refuses any member not
    listed here, and any class missing from it.
    """
    lom_types = importlib.import_module("_MxDCore.LomTypes")
    return {
        cls: set(p.name for p in props)
        for cls, props in lom_types.AVAILABLE_TYPE_PROPERTIES.items()
    }


def _names(obj):
    return sorted(n for n in dir(obj) if not n.startswith("_"))


def _doc(value):
    """Live's built-in help text, on one line."""
    return re.sub(r"\s+", " ", getattr(value, "__doc__", None) or "").strip()
