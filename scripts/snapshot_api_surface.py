"""Generate a baseline snapshot of Quotex's public API surface.

Run once before the refactor and commit tests/fixtures/api_surface.json.
The regression test in tests/test_api_surface.py compares the live class
against this snapshot.
"""
import inspect
import json
from pathlib import Path

from pyquotex.stable_api import Quotex

OUTPUT = Path(__file__).parent.parent / "tests" / "fixtures" / "api_surface.json"


def _serialize_signature(sig: inspect.Signature) -> dict:
    params = []
    for name, param in sig.parameters.items():
        params.append(
            {
                "name": name,
                "kind": str(param.kind),
                "default": (
                    "<no-default>"
                    if param.default is inspect.Parameter.empty
                    else repr(param.default)
                ),
                "annotation": (
                    "<no-annotation>"
                    if param.annotation is inspect.Parameter.empty
                    else str(param.annotation)
                ),
            }
        )
    return {
        "parameters": params,
        "return_annotation": (
            "<no-annotation>"
            if sig.return_annotation is inspect.Signature.empty
            else str(sig.return_annotation)
        ),
    }


def main() -> None:
    surface: dict[str, dict] = {}
    for name in sorted(dir(Quotex)):
        if name.startswith("_"):
            continue
        attr = getattr(Quotex, name)
        if callable(attr):
            try:
                sig = inspect.signature(attr)
            except (TypeError, ValueError):
                surface[name] = {"kind": "callable", "signature": None}
                continue
            surface[name] = {
                "kind": "method",
                "signature": _serialize_signature(sig),
            }
        else:
            surface[name] = {"kind": "attribute", "type": type(attr).__name__}

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(surface, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {len(surface)} public symbols to {OUTPUT}")


if __name__ == "__main__":
    main()
