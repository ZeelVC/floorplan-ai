from __future__ import annotations
from pathlib import Path
from typing import Iterable
from floorplan_ai.reconstruction.models import ReconstructionPoint
def write_ply(points:Iterable[ReconstructionPoint], path:Path)->None:
    items=list(points); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='ascii') as out:
        out.write('ply\nformat ascii 1.0\nelement vertex %d\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n'%len(items))
        for p in items:
            c=p.rgb or (255,255,255); out.write(f'{p.xyz[0]} {p.xyz[1]} {p.xyz[2]} {c[0]} {c[1]} {c[2]}\n')
