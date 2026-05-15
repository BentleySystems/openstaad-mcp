"""
Python code template that runs inside the Monty sandbox.

This module generates the wrapper code that is prepended to user code
before execution.  It creates a ``staad`` variable that proxies method
calls through the host-provided ``com_get`` and ``com_invoke`` external
functions.

Since Monty does not yet support classes, we use closures to create
proxy objects with attribute-like access via helper functions.
"""

from __future__ import annotations

# The bridge code is prepended to user code inside Monty.
# It defines helper functions and the `staad` namespace using dicts + functions.
BRIDGE_CODE = '''
import json

# ── Bridge: dict-based COM proxy ──────────────────────────────────────────
# Each "object" is represented as a dict {"_handle": int, "_name": str}.
# Sub-object access and method calls go through com_get / com_invoke.

def _make_root():
    return {"_handle": 0, "_name": "_root"}

def _get_sub(obj, prop):
    """Resolve a sub-object (e.g. staad.Geometry → com_get(0, "Geometry"))."""
    result = com_get(obj["_handle"], prop)
    if isinstance(result, dict) and "error" in result:
        raise RuntimeError(result["error"])
    h = result["handle"]
    return {"_handle": h, "_name": prop}

def _call(obj, method, *args):
    """Call a method on a COM object (e.g. geo.GetNodeCount())."""
    return com_invoke(obj["_handle"], method, *args)

# ── Convenience accessors mirroring staad.XYZ.Method() patterns ──────────

_staad_root = _make_root()

def _get_geometry():
    return _get_sub(_staad_root, "Geometry")

def _get_property():
    return _get_sub(_staad_root, "Property")

def _get_support():
    return _get_sub(_staad_root, "Support")

def _get_load():
    return _get_sub(_staad_root, "Load")

def _get_command():
    return _get_sub(_staad_root, "Command")

def _get_output():
    return _get_sub(_staad_root, "Output")

def _get_design():
    return _get_sub(_staad_root, "Design")

def _get_table():
    return _get_sub(_staad_root, "Table")

def _get_view():
    return _get_sub(_staad_root, "View")

# ── Public API: staad dict with sub-object accessors ─────────────────────

staad = {
    "_handle": 0,
    "_name": "_root",
    # Sub-object references (lazily resolved)
    "Geometry": None,
    "Property": None,
    "Support": None,
    "Load": None,
    "Command": None,
    "Output": None,
    "Design": None,
    "Table": None,
    "View": None,
}

def _ensure_sub(name):
    """Get or lazily resolve a sub-object."""
    if staad[name] is None:
        staad[name] = _get_sub(_staad_root, name)
    return staad[name]

# ── Root method shortcuts ────────────────────────────────────────────────

def staad_call(method, *args):
    """Call a method on the root staad object."""
    return _call(_staad_root, method, *args)

def geo_call(method, *args):
    """Call a method on staad.Geometry."""
    return _call(_ensure_sub("Geometry"), method, *args)

def prop_call(method, *args):
    """Call a method on staad.Property."""
    return _call(_ensure_sub("Property"), method, *args)

def support_call(method, *args):
    """Call a method on staad.Support."""
    return _call(_ensure_sub("Support"), method, *args)

def load_call(method, *args):
    """Call a method on staad.Load."""
    return _call(_ensure_sub("Load"), method, *args)

def cmd_call(method, *args):
    """Call a method on staad.Command."""
    return _call(_ensure_sub("Command"), method, *args)

def output_call(method, *args):
    """Call a method on staad.Output."""
    return _call(_ensure_sub("Output"), method, *args)

def design_call(method, *args):
    """Call a method on staad.Design."""
    return _call(_ensure_sub("Design"), method, *args)

def table_call(method, *args):
    """Call a method on staad.Table."""
    return _call(_ensure_sub("Table"), method, *args)

def view_call(method, *args):
    """Call a method on staad.View."""
    return _call(_ensure_sub("View"), method, *args)
'''
