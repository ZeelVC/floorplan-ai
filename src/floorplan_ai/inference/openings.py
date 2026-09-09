"""Conservative opening inference: no opening is emitted without supplied support evidence."""
from __future__ import annotations
from floorplan_ai.canonical.schema import Opening

def infer_openings(*_args, **_kwargs) -> tuple[Opening,...]: return ()
