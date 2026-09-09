"""Backend-neutral reconstruction records."""
from __future__ import annotations
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field

class ScaleState(str, Enum): UNKNOWN="UNKNOWN"; ESTIMATED="ESTIMATED"; METRIC="METRIC"
class ReconstructionCamera(BaseModel):
    model_config=ConfigDict(frozen=True)
    camera_id:int; model:str; width:int; height:int; params:tuple[float,...]
class ReconstructionPose(BaseModel):
    model_config=ConfigDict(frozen=True)
    image_id:int; image_name:str; camera_id:int; qvec:tuple[float,float,float,float]; tvec:tuple[float,float,float]; timestamp_seconds:float|None=None
class ReconstructionPoint(BaseModel):
    model_config=ConfigDict(frozen=True)
    point_id:int; xyz:tuple[float,float,float]; rgb:tuple[int,int,int]|None=None; error:float|None=None
class ReconstructionImage(BaseModel):
    model_config=ConfigDict(frozen=True)
    image_id:int; name:str; camera_id:int; timestamp_seconds:float|None=None
class ReconstructionResult(BaseModel):
    model_config=ConfigDict(frozen=True)
    success:bool; backend_name:str; camera_models:tuple[ReconstructionCamera,...]=(); poses:tuple[ReconstructionPose,...]=(); points:tuple[ReconstructionPoint,...]=(); images:tuple[ReconstructionImage,...]=(); diagnostics:dict=Field(default_factory=dict); scale_state:ScaleState=ScaleState.UNKNOWN; failure_reason:str|None=None
