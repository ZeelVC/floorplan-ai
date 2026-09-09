"""Source-independent, serializable canonical spatial data contract."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from math import sqrt
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .validation import (
    SUPPORTED_UNITS,
    require_homogeneous_matrix,
    require_positive_semidefinite,
    require_rotation_matrix,
    require_simple_closed_polygon,
    require_unit_vector,
    require_vector,
)

EntityId = UUID
PositiveFloat = Annotated[float, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]
Point2D = tuple[float, float]
Point3D = tuple[float, float, float]
Matrix4x4 = tuple[tuple[float, float, float, float], tuple[float, float, float, float], tuple[float, float, float, float], tuple[float, float, float, float]]


class CanonicalBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrameType(str, Enum):
    WORLD = "world"
    CAPTURE = "capture"
    LOCAL = "local"


class TransformKind(str, Enum):
    SE3 = "SE3"
    SIM3 = "Sim3"


class FrameTransform(CanonicalBaseModel):
    """A frame-to-parent transform; Sim(3) keeps scale explicit rather than masquerading as SE(3)."""

    transform_type: TransformKind = TransformKind.SE3
    matrix: Matrix4x4
    scale_factor: PositiveFloat = 1.0

    @model_validator(mode="after")
    def validate_transform(self) -> "FrameTransform":
        self.matrix = require_homogeneous_matrix(self.matrix, "transform matrix")  # type: ignore[assignment]
        require_rotation_matrix([row[:3] for row in self.matrix[:3]], "transform rotation")
        if self.transform_type is TransformKind.SE3 and self.scale_factor != 1.0:
            raise ValueError("SE(3) transforms must have scale_factor 1")
        # Sim(3) scale remains an explicit scalar and is never embedded in matrix[:3, :3].
        return self


class CoordinateFrame(CanonicalBaseModel):
    frame_id: EntityId = Field(default_factory=uuid4)
    parent_frame_id: EntityId | None = None
    frame_type: FrameType = FrameType.LOCAL
    transform_to_parent: FrameTransform | None = None
    units: Literal["m"] = "m"
    up_vector: Point3D = (0.0, 0.0, 1.0)
    convention: Literal["right_handed_z_up"] = "right_handed_z_up"

    @model_validator(mode="after")
    def validate_parent_semantics(self) -> "CoordinateFrame":
        self.up_vector = require_unit_vector(self.up_vector, 3, "up_vector")  # type: ignore[assignment]
        if self.parent_frame_id is None and self.transform_to_parent is not None:
            raise ValueError("a root frame cannot have transform_to_parent")
        if self.parent_frame_id is not None and self.transform_to_parent is None:
            raise ValueError("a child frame requires transform_to_parent")
        if self.parent_frame_id == self.frame_id:
            raise ValueError("a frame cannot be its own parent")
        return self


class Capture(CanonicalBaseModel):
    capture_id: EntityId = Field(default_factory=uuid4)
    capture_type: Literal["photo", "video", "other"] = "other"
    payload_reference: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Pose(CanonicalBaseModel):
    pose_id: EntityId = Field(default_factory=uuid4)
    frame_id: EntityId
    camera_to_frame: Matrix4x4

    @model_validator(mode="after")
    def validate_pose(self) -> "Pose":
        matrix = require_homogeneous_matrix(self.camera_to_frame, "camera_to_frame")
        require_rotation_matrix([row[:3] for row in matrix[:3]], "camera_to_frame rotation")
        self.camera_to_frame = matrix  # type: ignore[assignment]
        return self


class Camera(CanonicalBaseModel):
    camera_id: EntityId = Field(default_factory=uuid4)
    capture_id: EntityId
    focal_length: tuple[PositiveFloat, PositiveFloat] | None = None
    principal_point: Point2D | None = None
    distortion_coefficients: tuple[float, ...] = ()
    resolution: tuple[Annotated[int, Field(gt=0)], Annotated[int, Field(gt=0)]] | None = None
    prior_source: str | None = None


class ObservationType(str, Enum):
    IMAGE = "image"
    DEPTH = "depth"
    FEATURE_CORRESPONDENCE = "feature_correspondence"
    PLANE = "plane_observation"
    SEGMENTATION = "segmentation"
    POINT_CLOUD = "point_cloud"
    OTHER = "other"


class Observation(CanonicalBaseModel):
    """Immutable source evidence; structural entities are modeled separately."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: EntityId = Field(default_factory=uuid4)
    pose_id: EntityId | None = None
    camera_id: EntityId | None = None
    observation_type: ObservationType
    payload_reference: str
    confidence_mask: str | None = None


class GeometryType(str, Enum):
    MESH = "mesh"
    POINT_CLOUD = "point_cloud"
    POLYLINE = "polyline"
    OTHER = "other"


class Geometry3D(CanonicalBaseModel):
    geometry_id: EntityId = Field(default_factory=uuid4)
    frame_id: EntityId
    geometry_type: GeometryType
    vertex_buffer_reference: str
    bounding_box: tuple[Point3D, Point3D] | None = None
    point_density: NonNegativeFloat | None = None


class Uncertainty(CanonicalBaseModel):
    uncertainty_id: EntityId = Field(default_factory=uuid4)
    distribution_type: str = "unknown"
    covariance_matrix: tuple[tuple[float, ...], ...] | None = None
    confidence_bounds: tuple[float, float] | None = None

    @model_validator(mode="after")
    def validate_uncertainty(self) -> "Uncertainty":
        if self.covariance_matrix is not None:
            size = len(self.covariance_matrix)
            if size == 0 or any(len(row) != size for row in self.covariance_matrix):
                raise ValueError("covariance_matrix must be non-empty and square")
            if any(abs(self.covariance_matrix[row][column] - self.covariance_matrix[column][row]) > 1e-10 for row in range(size) for column in range(row + 1, size)):
                raise ValueError("covariance_matrix must be symmetric")
            require_positive_semidefinite(self.covariance_matrix, "covariance_matrix")
        if self.confidence_bounds is not None and self.confidence_bounds[0] > self.confidence_bounds[1]:
            raise ValueError("confidence_bounds lower value must not exceed upper value")
        return self


class Provenance(CanonicalBaseModel):
    source_capture_ids: tuple[EntityId, ...] = ()
    source_pose_ids: tuple[EntityId, ...] = ()
    source_observation_ids: tuple[EntityId, ...] = ()
    generating_pipeline_stage: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Plane(CanonicalBaseModel):
    plane_id: EntityId = Field(default_factory=uuid4)
    frame_id: EntityId
    normal_vector: Point3D
    distance_offset: float
    boundary_polygon_3d: tuple[Point3D, ...] = ()
    inlier_count: Annotated[int, Field(ge=0)] = 0
    rmse: NonNegativeFloat | None = None
    uncertainty: Uncertainty | None = None
    provenance: Provenance | None = None

    @model_validator(mode="after")
    def validate_plane(self) -> "Plane":
        self.normal_vector = require_unit_vector(self.normal_vector, 3, "normal_vector")  # type: ignore[assignment]
        self.boundary_polygon_3d = tuple(require_vector(point, 3, "boundary_polygon_3d vertex") for point in self.boundary_polygon_3d)  # type: ignore[assignment]
        return self


class Wall(CanonicalBaseModel):
    wall_id: EntityId = Field(default_factory=uuid4)
    supporting_plane_id: EntityId
    start_point_2d: Point2D
    end_point_2d: Point2D
    thickness: PositiveFloat | None = None
    height: PositiveFloat | None = None
    room_ids: tuple[EntityId, ...] = ()
    manhattan_deviation: NonNegativeFloat | None = None
    uncertainty: Uncertainty | None = None
    provenance: Provenance | None = None

    @model_validator(mode="after")
    def validate_wall(self) -> "Wall":
        self.start_point_2d = require_vector(self.start_point_2d, 2, "start_point_2d")  # type: ignore[assignment]
        self.end_point_2d = require_vector(self.end_point_2d, 2, "end_point_2d")  # type: ignore[assignment]
        if self.length <= 0:
            raise ValueError("wall length must be positive")
        return self

    @property
    def length(self) -> float:
        return sqrt(sum((end - start) ** 2 for start, end in zip(self.start_point_2d, self.end_point_2d)))


class Room(CanonicalBaseModel):
    room_id: EntityId = Field(default_factory=uuid4)
    room_type: str = "unknown"
    boundary_polygon_2d: tuple[Point2D, ...]
    floor_plane_id: EntityId | None = None
    ceiling_plane_id: EntityId | None = None
    wall_ids: tuple[EntityId, ...] = ()
    opening_ids: tuple[EntityId, ...] = ()
    uncertainty: Uncertainty | None = None
    provenance: Provenance | None = None

    @model_validator(mode="after")
    def validate_room(self) -> "Room":
        self.boundary_polygon_2d = require_simple_closed_polygon(self.boundary_polygon_2d, "boundary_polygon_2d")  # type: ignore[assignment]
        return self


class OpeningType(str, Enum):
    DOOR = "door"
    WINDOW = "window"
    ARCHWAY = "archway"
    OTHER = "other"


class Opening(CanonicalBaseModel):
    opening_id: EntityId = Field(default_factory=uuid4)
    parent_wall_id: EntityId
    opening_type: OpeningType
    offset_along_wall: NonNegativeFloat
    width: PositiveFloat
    height: PositiveFloat
    sill_height: NonNegativeFloat | None = None
    connected_room_ids: tuple[EntityId, ...] = ()
    uncertainty: Uncertainty | None = None
    provenance: Provenance | None = None


class RelationshipType(str, Enum):
    ADJACENT_TO = "ADJACENT_TO"
    CONNECTED_VIA_OPENING = "CONNECTED_VIA_OPENING"
    BOUNDED_BY = "BOUNDED_BY"
    HOSTS = "HOSTS"
    COPLANAR_WITH = "COPLANAR_WITH"


class SpatialRelationship(CanonicalBaseModel):
    edge_id: EntityId = Field(default_factory=uuid4)
    source_id: EntityId
    target_id: EntityId
    relationship_type: RelationshipType
    traversal_cost: NonNegativeFloat | None = None
    confidence: Annotated[float, Field(ge=0, le=1)] | None = None
    provenance: Provenance | None = None


class MeasurementType(str, Enum):
    WALL_LENGTH = "WALL_LENGTH"
    FLOOR_AREA = "FLOOR_AREA"
    CEILING_HEIGHT = "CEILING_HEIGHT"
    FOOTPRINT_AREA = "FOOTPRINT_AREA"
    OTHER = "OTHER"


class Measurement(CanonicalBaseModel):
    measurement_id: EntityId = Field(default_factory=uuid4)
    target_entity_id: EntityId
    metric_type: MeasurementType | str
    nominal_value: PositiveFloat
    standard_deviation: NonNegativeFloat | None = None
    uncertainty_id: EntityId | None = None
    interval_95: tuple[float, float] | None = None
    unit: str = "m"
    provenance_ref: Provenance | None = None

    @model_validator(mode="after")
    def validate_measurement(self) -> "Measurement":
        if self.unit not in SUPPORTED_UNITS:
            raise ValueError(f"unsupported measurement unit: {self.unit}")
        if self.interval_95 is not None and not (self.interval_95[0] <= self.nominal_value <= self.interval_95[1]):
            raise ValueError("interval_95 must contain nominal_value")
        return self


class ScaleEvidenceType(str, Enum):
    METRIC_DEPTH = "metric_depth"
    CAMERA_METADATA = "camera_metadata"
    ARCHITECTURAL_PRIOR = "architectural_prior"
    GEOMETRIC_CONSISTENCY = "geometric_consistency"
    OTHER = "other"


class ScaleEstimate(CanonicalBaseModel):
    scale_id: EntityId = Field(default_factory=uuid4)
    frame_id: EntityId
    scale_factor: PositiveFloat
    uncertainty: Uncertainty | None = None
    confidence: Annotated[float, Field(ge=0, le=1)]
    evidence: tuple[ScaleEvidenceType, ...] = ()
    provenance: Provenance | None = None


class CanonicalWorldModel(CanonicalBaseModel):
    model_id: EntityId = Field(default_factory=uuid4)
    frames: tuple[CoordinateFrame, ...] = ()
    captures: tuple[Capture, ...] = ()
    cameras: tuple[Camera, ...] = ()
    poses: tuple[Pose, ...] = ()
    observations: tuple[Observation, ...] = ()
    geometries: tuple[Geometry3D, ...] = ()
    planes: tuple[Plane, ...] = ()
    rooms: tuple[Room, ...] = ()
    walls: tuple[Wall, ...] = ()
    openings: tuple[Opening, ...] = ()
    relationships: tuple[SpatialRelationship, ...] = ()
    measurements: tuple[Measurement, ...] = ()
    scale_estimates: tuple[ScaleEstimate, ...] = ()
    provenance: Provenance | None = None

    @model_validator(mode="after")
    def validate_integrity(self) -> "CanonicalWorldModel":
        collections = {
            "frame": self.frames, "capture": self.captures, "camera": self.cameras, "pose": self.poses,
            "observation": self.observations, "geometry": self.geometries, "plane": self.planes,
            "room": self.rooms, "wall": self.walls, "opening": self.openings, "relationship": self.relationships,
            "measurement": self.measurements, "scale": self.scale_estimates,
        }
        all_ids: set[EntityId] = set()
        for label, items in collections.items():
            ids = [getattr(item, f"{label}_id", getattr(item, "edge_id", None)) for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {label} identifiers")
            if all_ids.intersection(ids):
                raise ValueError("entity identifiers must be globally unique")
            all_ids.update(ids)
        frame_ids, capture_ids, camera_ids, pose_ids = ({item.frame_id for item in self.frames}, {item.capture_id for item in self.captures}, {item.camera_id for item in self.cameras}, {item.pose_id for item in self.poses})
        plane_ids, room_ids, wall_ids, opening_ids = ({item.plane_id for item in self.planes}, {item.room_id for item in self.rooms}, {item.wall_id for item in self.walls}, {item.opening_id for item in self.openings})
        uncertainty_ids = {entity.uncertainty.uncertainty_id for entity in (*self.planes, *self.walls, *self.rooms, *self.openings, *self.scale_estimates) if entity.uncertainty is not None}
        for frame in self.frames:
            if frame.parent_frame_id is not None and frame.parent_frame_id not in frame_ids: raise ValueError("frame parent reference does not resolve")
        for camera in self.cameras:
            if camera.capture_id not in capture_ids: raise ValueError("camera capture reference does not resolve")
        for pose in self.poses:
            if pose.frame_id not in frame_ids: raise ValueError("pose frame reference does not resolve")
        for observation in self.observations:
            if observation.pose_id is not None and observation.pose_id not in pose_ids: raise ValueError("observation pose reference does not resolve")
            if observation.camera_id is not None and observation.camera_id not in camera_ids: raise ValueError("observation camera reference does not resolve")
        for geometry in self.geometries:
            if geometry.frame_id not in frame_ids: raise ValueError("geometry frame reference does not resolve")
        for plane in self.planes:
            if plane.frame_id not in frame_ids: raise ValueError("plane frame reference does not resolve")
        for wall in self.walls:
            if wall.supporting_plane_id not in plane_ids or not set(wall.room_ids).issubset(room_ids): raise ValueError("wall references do not resolve")
        for room in self.rooms:
            if (room.floor_plane_id is not None and room.floor_plane_id not in plane_ids) or (room.ceiling_plane_id is not None and room.ceiling_plane_id not in plane_ids) or not set(room.wall_ids).issubset(wall_ids) or not set(room.opening_ids).issubset(opening_ids): raise ValueError("room references do not resolve")
        for opening in self.openings:
            if opening.parent_wall_id not in wall_ids or not set(opening.connected_room_ids).issubset(room_ids): raise ValueError("opening references do not resolve")
            wall = next(item for item in self.walls if item.wall_id == opening.parent_wall_id)
            if opening.offset_along_wall + opening.width > wall.length + 1e-9: raise ValueError("opening interval lies outside parent wall")
        for relationship in self.relationships:
            if relationship.source_id not in all_ids or relationship.target_id not in all_ids: raise ValueError("relationship endpoints must resolve")
        for measurement in self.measurements:
            if measurement.target_entity_id not in all_ids: raise ValueError("measurement target reference does not resolve")
            if measurement.uncertainty_id is not None and measurement.uncertainty_id not in uncertainty_ids: raise ValueError("measurement uncertainty reference does not resolve")
        for scale in self.scale_estimates:
            if scale.frame_id not in frame_ids: raise ValueError("scale frame reference does not resolve")
        return self

    def to_json(self) -> str:
        """Serialize to stable UTF-8 JSON suitable for exchange and tests."""
        return self.model_dump_json(by_alias=True, exclude_none=True, indent=2)

    @classmethod
    def from_json(cls, payload: str | bytes) -> "CanonicalWorldModel":
        return cls.model_validate_json(payload)

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        return cls.model_json_schema()
