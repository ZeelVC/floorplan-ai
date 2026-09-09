"""Input-organization models; these are intentionally not spatial models."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DatasetModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Orientation(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    UNKNOWN = "unknown"


class OrientationMetadata(DatasetModel):
    value: Orientation
    source: Literal["declared", "derived"] = "declared"


class RoomReference(DatasetModel):
    room_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    label: str | None = None


class CaptureInput(DatasetModel):
    """One original media item supplied to a frontend, never evaluation data."""

    capture_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    source_type: Literal["photo", "video"]
    file: str = Field(min_length=1)
    room_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    sequence: int | None = Field(default=None, ge=0)
    orientation: OrientationMetadata | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    resolved_file: Path | None = Field(default=None, exclude=True)

    @field_validator("file")
    @classmethod
    def relative_file_reference(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("file must be a relative path inside the dataset directory")
        return value


class Trial(DatasetModel):
    trial_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    captures: tuple[CaptureInput, ...] = Field(min_length=1)


class Property(DatasetModel):
    property_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    rooms: tuple[RoomReference, ...] = ()
    trials: tuple[Trial, ...] = Field(min_length=1)


class EvaluationReference(DatasetModel):
    """An opt-in pointer for the evaluation layer; excluded from capture inputs."""

    ground_truth_file: str = Field(min_length=1)
    format: Literal["xlsx", "json", "csv"]

    @field_validator("ground_truth_file")
    @classmethod
    def relative_ground_truth_reference(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("ground_truth_file must be a relative path inside the dataset directory")
        return value


class Manifest(DatasetModel):
    schema_version: Literal["1.0"]
    dataset_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    properties: tuple[Property, ...] = Field(min_length=1)
    evaluation: EvaluationReference | None = None


class CaptureDataset(DatasetModel):
    """Validated inference inputs, ordered independently of filesystem traversal."""

    dataset_id: str
    root: Path = Field(exclude=True)
    properties: tuple[Property, ...]

    @property
    def captures(self) -> tuple[CaptureInput, ...]:
        return tuple(capture for property_ in self.properties for trial in property_.trials for capture in trial.captures)
