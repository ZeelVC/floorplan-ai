"""Deterministic media routing; grouping is an internal pipeline concern."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

IMAGE={'.jpg','.jpeg','.png','.webp','.heic','.heif'}
VIDEO={'.mp4','.mov','.avi','.m4v'}

@dataclass(frozen=True)
class CaptureGroup:
    capture_id:str
    room_group_id:str|None
    source_type:str
    paths:tuple[Path,...]

def detect_input(path:Path)->str:
    if path.is_file():
        return 'video' if path.suffix.lower() in VIDEO else 'photo' if path.suffix.lower() in IMAGE else (_ for _ in ()).throw(ValueError('unsupported input'))
    if any(p.suffix.lower() in VIDEO for p in path.iterdir() if p.is_file()) and any(p.suffix.lower() in IMAGE for p in path.rglob('*') if p.is_file()):
        raise ValueError('mixed photo/video capture is not safely mergeable; provide one modality per run')
    return 'photo' if any(p.suffix.lower() in IMAGE for p in path.rglob('*')) else (_ for _ in ()).throw(ValueError('no supported photos found'))

def photo_groups(path:Path)->tuple[CaptureGroup,...]:
    if path.is_file():
        return (CaptureGroup('photo-000',None,'photo',(path,)),)
    direct=tuple(sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in IMAGE))
    groups=[]
    if direct:
        groups.append(CaptureGroup('photo-000',None,'photo',direct))
    for i,directory in enumerate(sorted(p for p in path.iterdir() if p.is_dir())):
        images=tuple(sorted(p for p in directory.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE))
        if images:
            groups.append(CaptureGroup(f'photo-{i+len(groups):03d}',directory.name,'photo',images))
    if not groups:
        raise ValueError('no supported photos found')
    return tuple(groups)

def photos(path:Path):
    return tuple(p for g in photo_groups(path) for p in g.paths)
