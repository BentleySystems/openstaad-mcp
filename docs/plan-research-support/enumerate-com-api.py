"""
Enumerate the full OpenSTAAD COM API surface from a live STAAD.Pro instance.

Requires:
  - STAAD.Pro running with a .std model open
  - Run from the project venv:  .\.venv\Scripts\python.exe docs\plan-research-support\enumerate-com-api.py

Outputs:
  - Every method on root + 9 sub-objects (from openstaadpy wrappers)
  - Any additional dispatch objects discovered on root beyond the known 9
  - Security-sensitive methods (file I/O, path args, process control)
  - Raw COM type-library probe (if available)
"""

import inspect
import importlib
import json
import threading
import sys

# ---------------------------------------------------------------------------
# 1. Enumerate openstaadpy wrappers (static — no live instance needed)
# ---------------------------------------------------------------------------

SUB_MODULES = [
    ("Root", "openstaadpy.os_analytical.openstaadroot", "OSRoot"),
    ("Geometry", "openstaadpy.os_analytical.osgeometry", "OSGeometry"),
    ("Property", "openstaadpy.os_analytical.osproperty", "OSProperty"),
    ("Support", "openstaadpy.os_analytical.ossupport", "OSSupport"),
    ("Load", "openstaadpy.os_analytical.osload", "OSLoad"),
    ("Command", "openstaadpy.os_analytical.oscommand", "OSCommand"),
    ("Output", "openstaadpy.os_analytical.osoutput", "OSOutput"),
    ("Design", "openstaadpy.os_analytical.osdesign", "OSDesign"),
    ("Table", "openstaadpy.os_analytical.ostable", "OSTable"),
    ("View", "openstaadpy.os_analytical.osview", "OSView"),
]

IO_NAME_KEYWORDS = ["file", "save", "open", "new", "close", "quit", "export", "folder", "path"]
IO_SIG_KEYWORDS = ["filename", "filepath", "file", "path", "folder", "location"]


def enumerate_wrappers():
    """Return {name: {methods: [...], dangerous: [...]}} from openstaadpy classes."""
    result = {}
    for label, mod_path, cls_name in SUB_MODULES:
        mod = importlib.import_module(mod_path)
        cls = getattr(mod, cls_name)
        methods = []
        dangerous = []
        for m in sorted(dir(cls)):
            if m.startswith("_"):
                continue
            obj = getattr(cls, m, None)
            if not callable(obj):
                continue
            try:
                sig = str(inspect.signature(obj))
            except (ValueError, TypeError):
                sig = "(...)"
            methods.append({"name": m, "sig": sig})

            lower_m = m.lower()
            lower_sig = sig.lower()
            if any(kw in lower_m for kw in IO_NAME_KEYWORDS):
                dangerous.append({"method": m, "sig": sig, "reason": "name"})
            elif any(kw in lower_sig for kw in IO_SIG_KEYWORDS):
                dangerous.append({"method": m, "sig": sig, "reason": "param"})

        result[label] = {"count": len(methods), "methods": methods, "dangerous": dangerous}
    return result


# ---------------------------------------------------------------------------
# 2. Probe live COM instance (requires running STAAD.Pro)
# ---------------------------------------------------------------------------


def probe_live_instance():
    """Connect via ROT and check for dispatch objects beyond the known 9."""
    if sys.platform != "win32":
        return {"error": "Windows only"}

    result = {}
    err = [None]

    def _scan():
        try:
            import pythoncom
            import win32com.client

            pythoncom.CoInitialize()
            try:
                rot = pythoncom.GetRunningObjectTable()
                enum = rot.EnumRunning()
                staad = None
                while True:
                    monikers = enum.Next(1)
                    if not monikers:
                        break
                    moniker = monikers[0]
                    try:
                        ctx = pythoncom.CreateBindCtx(0)
                        dn = moniker.GetDisplayName(ctx, None)
                    except Exception:
                        continue
                    if dn.lower().endswith(".std"):
                        obj = moniker.BindToObject(ctx, None, pythoncom.IID_IDispatch)
                        staad = win32com.client.Dispatch(obj)
                        result["file"] = dn
                        break

                if staad is None:
                    err[0] = "No STAAD.Pro instance with an open .std file found in the ROT."
                    return

                # Check for type library
                try:
                    ti = staad._oleobj_.GetTypeInfo()
                    ta = ti.GetTypeAttr()
                    funcs = []
                    for i in range(ta.cFuncs):
                        fd = ti.GetFuncDesc(i)
                        name = ti.GetNames(fd.memid)[0]
                        funcs.append(name)
                    result["typelib"] = {"guid": str(ta.iid), "funcs": sorted(funcs)}
                except Exception as e:
                    result["typelib"] = {"error": str(e), "note": "Pure late-bound IDispatch, no type library."}

                # Probe root for unknown dispatch sub-objects
                known = {"Geometry", "Property", "Support", "Load", "Command", "Output", "Design", "Table", "View"}
                unknown_dispatches = []
                from openstaadpy.os_analytical.openstaadroot import OSRoot

                for m in dir(OSRoot):
                    if m.startswith("_") or m in known:
                        continue
                    try:
                        val = getattr(staad, m)
                        tname = type(val).__name__
                        if "Dispatch" in tname:
                            unknown_dispatches.append({"name": m, "type": tname})
                    except Exception:
                        pass
                result["unknown_dispatch_objects"] = unknown_dispatches

            finally:
                pythoncom.CoUninitialize()
        except Exception as e:
            import traceback

            err[0] = traceback.format_exc()

    t = threading.Thread(target=_scan, daemon=True)
    t.start()
    t.join(timeout=30)

    if err[0]:
        return {"error": err[0]}
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("OpenSTAAD COM API Enumeration")
    print("=" * 70)

    # Static wrapper enumeration
    wrappers = enumerate_wrappers()

    total = sum(v["count"] for v in wrappers.values())
    print(f"\nTotal methods across all objects: {total}\n")

    for label, data in wrappers.items():
        print(f"--- {label} ({data['count']} methods) ---")
        for m in data["methods"]:
            print(f"  {m['name']}{m['sig']}")
        if data["dangerous"]:
            print(f"  ** Security-sensitive ({len(data['dangerous'])}):")
            for d in data["dangerous"]:
                print(f"     {d['method']}{d['sig']}  [{d['reason']}]")
        print()

    # Live instance probe
    print("=" * 70)
    print("Live instance probe")
    print("=" * 70)
    live = probe_live_instance()
    print(json.dumps(live, indent=2))
