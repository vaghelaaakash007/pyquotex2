"""Regression test: Quotex's public surface must not shrink during refactors."""
import inspect
import json
from pathlib import Path

from pyquotex.stable_api import Quotex

FIXTURE = Path(__file__).parent / "fixtures" / "api_surface.json"


def _current_surface() -> dict[str, dict]:
    surface: dict[str, dict] = {}
    for name in sorted(dir(Quotex)):
        if name.startswith("_"):
            continue
        attr = getattr(Quotex, name)
        if callable(attr):
            try:
                sig = inspect.signature(attr)
            except (TypeError, ValueError):
                surface[name] = {"kind": "callable"}
                continue
            params = [p.name for p in sig.parameters.values()]
            surface[name] = {"kind": "method", "params": params}
        else:
            surface[name] = {"kind": "attribute"}
    return surface


def test_public_methods_present():
    """Every public method in the snapshot must still exist on Quotex."""
    baseline = json.loads(FIXTURE.read_text())
    current = _current_surface()
    missing = sorted(set(baseline) - set(current))
    assert not missing, f"Public symbols removed: {missing}"


def test_public_method_params_unchanged():
    """Parameter names of public methods must not change (order matters)."""
    baseline = json.loads(FIXTURE.read_text())
    current = _current_surface()
    diffs: list[str] = []
    for name, baseline_entry in baseline.items():
        if baseline_entry.get("kind") != "method":
            continue
        if name not in current:
            continue  # caught by previous test
        baseline_params = [
            p["name"] for p in baseline_entry["signature"]["parameters"]
        ]
        current_params = current[name].get("params", [])
        if baseline_params != current_params:
            diffs.append(
                f"{name}: baseline={baseline_params} current={current_params}"
            )
    assert not diffs, "Parameter signatures changed:\n" + "\n".join(diffs)
