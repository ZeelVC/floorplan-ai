"""Unit tests for the Milestone 4 canonical spatial contract."""
from __future__ import annotations
import sys
from pathlib import Path
import unittest
from uuid import uuid4
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path: sys.path.insert(0, str(ROOT / "src"))
from pydantic import ValidationError
from floorplan_ai.canonical.schema import *

I = ((1.,0.,0.,0.),(0.,1.,0.,0.),(0.,0.,1.,0.),(0.,0.,0.,1.))
def provenance(): return Provenance(generating_pipeline_stage="synthetic-test")

class CanonicalSchemaTests(unittest.TestCase):
    def setUp(self):
        self.frame = CoordinateFrame(frame_type=FrameType.WORLD)
        self.capture = Capture(capture_type="photo")
        self.camera = Camera(capture_id=self.capture.capture_id, focal_length=(1000, 1000), resolution=(100, 100))
        self.pose = Pose(frame_id=self.frame.frame_id, camera_to_frame=I)
        self.plane = Plane(frame_id=self.frame.frame_id, normal_vector=(0,0,1), distance_offset=0, provenance=provenance())
        self.room_a = Room(boundary_polygon_2d=((0,0),(4,0),(4,3),(0,3),(0,0)), provenance=provenance())
        self.room_b = Room(boundary_polygon_2d=((4,0),(8,0),(8,3),(4,3),(4,0)), provenance=provenance())
        self.wall = Wall(supporting_plane_id=self.plane.plane_id, start_point_2d=(0,0), end_point_2d=(4,0), room_ids=(self.room_a.room_id, self.room_b.room_id), provenance=provenance())
        self.opening = Opening(parent_wall_id=self.wall.wall_id, opening_type=OpeningType.DOOR, offset_along_wall=1, width=1, height=2, connected_room_ids=(self.room_a.room_id,self.room_b.room_id), provenance=provenance())
        self.room_a = self.room_a.model_copy(update={"wall_ids": (self.wall.wall_id,), "opening_ids": (self.opening.opening_id,)})
        self.room_b = self.room_b.model_copy(update={"wall_ids": (self.wall.wall_id,), "opening_ids": (self.opening.opening_id,)})
    def model(self):
        return CanonicalWorldModel(frames=(self.frame,), captures=(self.capture,), cameras=(self.camera,), poses=(self.pose,), observations=(Observation(pose_id=self.pose.pose_id,camera_id=self.camera.camera_id,observation_type=ObservationType.IMAGE,payload_reference="image.jpg"),), planes=(self.plane,), rooms=(self.room_a,self.room_b), walls=(self.wall,), openings=(self.opening,), relationships=(SpatialRelationship(source_id=self.room_a.room_id,target_id=self.room_b.room_id,relationship_type=RelationshipType.CONNECTED_VIA_OPENING),), measurements=(Measurement(target_entity_id=self.wall.wall_id,metric_type=MeasurementType.WALL_LENGTH,nominal_value=4,interval_95=(3.9,4.1),provenance_ref=provenance()),), scale_estimates=(ScaleEstimate(frame_id=self.frame.frame_id,scale_factor=1,confidence=.5,evidence=(ScaleEvidenceType.CAMERA_METADATA,),provenance=provenance()),), provenance=provenance())
    def test_complete_model_and_round_trip(self):
        model = self.model(); restored = CanonicalWorldModel.from_json(model.to_json())
        self.assertEqual(restored.model_dump(mode="json"), model.model_dump(mode="json"))
    def test_json_schema_generation(self):
        schema = CanonicalWorldModel.json_schema()
        self.assertEqual(schema.get("title"), "CanonicalWorldModel")
        definitions = schema.get("$defs", {})
        for entity in ("CoordinateFrame", "Capture", "Camera", "Pose", "Observation", "Geometry3D", "Plane", "Wall", "Room", "Opening", "SpatialRelationship", "Measurement", "Uncertainty", "Provenance", "ScaleEstimate"):
            self.assertIn(entity, definitions)
    def test_core_entities(self):
        uncertainty = Uncertainty(distribution_type="interval", confidence_bounds=(1, 2))
        geometry = Geometry3D(frame_id=self.frame.frame_id, geometry_type=GeometryType.POINT_CLOUD, vertex_buffer_reference="points.bin", point_density=1)
        self.assertEqual(self.wall.length, 4); self.assertEqual(self.plane.normal_vector, (0.,0.,1.)); self.assertEqual(self.camera.prior_source, None)
        self.assertEqual(uncertainty.confidence_bounds, (1, 2)); self.assertEqual(geometry.geometry_type, GeometryType.POINT_CLOUD)
        self.assertEqual(FrameTransform(matrix=I).transform_type, TransformKind.SE3)
    def test_malformed_matrices_and_covariance_rejected(self):
        with self.assertRaises(ValidationError): Pose(frame_id=self.frame.frame_id, camera_to_frame=((1,0),))
        with self.assertRaises(ValidationError): FrameTransform(matrix=((1,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,0)))
        with self.assertRaises(ValidationError): Uncertainty(covariance_matrix=((1,0),(0,)))
    def test_invalid_plane_wall_and_room_rejected(self):
        with self.assertRaises(ValidationError): Plane(frame_id=self.frame.frame_id,normal_vector=(2,0,0),distance_offset=0)
        with self.assertRaises(ValidationError): Wall(supporting_plane_id=self.plane.plane_id,start_point_2d=(0,0),end_point_2d=(0,0))
        with self.assertRaises(ValidationError): Room(boundary_polygon_2d=((0,0),(2,2),(0,2),(2,0),(0,0)))
        with self.assertRaises(ValidationError): Room(boundary_polygon_2d=((0,0),(1,0),(2,0),(0,0)))
    def test_invalid_opening_measurement_and_scale_rejected(self):
        with self.assertRaises(ValidationError): Opening(parent_wall_id=self.wall.wall_id,opening_type=OpeningType.DOOR,offset_along_wall=0,width=-1,height=2)
        with self.assertRaises(ValidationError): Measurement(target_entity_id=self.wall.wall_id,metric_type="X",nominal_value=1,interval_95=(2,3))
        with self.assertRaises(ValidationError): ScaleEstimate(frame_id=self.frame.frame_id,scale_factor=0,confidence=.5)
    def test_pose_se3_validation(self):
        valid_rotation = ((0, -1, 0, 0), (1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
        self.assertEqual(Pose(frame_id=self.frame.frame_id, camera_to_frame=valid_rotation).camera_to_frame, valid_rotation)
        non_orthogonal = ((1, 1, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
        reflection = ((-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
        with self.assertRaises(ValidationError): Pose(frame_id=self.frame.frame_id, camera_to_frame=non_orthogonal)
        with self.assertRaises(ValidationError): Pose(frame_id=self.frame.frame_id, camera_to_frame=reflection)

    def test_frame_transform_se3_and_sim3_validation(self):
        valid_sim3 = FrameTransform(transform_type=TransformKind.SIM3, matrix=I, scale_factor=2)
        self.assertEqual(FrameTransform(matrix=I).scale_factor, 1)
        self.assertEqual(valid_sim3.scale_factor, 2)
        invalid_rotation = ((1, 1, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
        reflection = ((-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
        with self.assertRaises(ValidationError): FrameTransform(matrix=invalid_rotation)
        with self.assertRaises(ValidationError): FrameTransform(matrix=reflection)
        with self.assertRaises(ValidationError): FrameTransform(matrix=I, scale_factor=2)
        with self.assertRaises(ValidationError): FrameTransform(transform_type=TransformKind.SIM3, matrix=I, scale_factor=0)

    def test_coordinate_frame_parent_semantics(self):
        transform = FrameTransform(matrix=I)
        self.assertEqual(CoordinateFrame(frame_type=FrameType.WORLD).parent_frame_id, None)
        parent = CoordinateFrame(frame_type=FrameType.WORLD)
        child = CoordinateFrame(parent_frame_id=parent.frame_id, transform_to_parent=transform)
        self.assertEqual(child.parent_frame_id, parent.frame_id)
        with self.assertRaises(ValidationError): CoordinateFrame(transform_to_parent=transform)
        with self.assertRaises(ValidationError): CoordinateFrame(parent_frame_id=uuid4())
        identifier = uuid4()
        with self.assertRaises(ValidationError): CoordinateFrame(frame_id=identifier, parent_frame_id=identifier, transform_to_parent=transform)

    def test_uncertainty_covariance_validation(self):
        self.assertEqual(Uncertainty(covariance_matrix=((1, 0), (0, 2))).covariance_matrix, ((1, 0), (0, 2)))
        for covariance in (((1, 0), (0,)), (), ((1, 2), (0, 1)), ((1, 2), (2, 1))):
            with self.assertRaises(ValidationError): Uncertainty(covariance_matrix=covariance)

    def test_observation_is_immutable(self):
        observation = Observation(observation_type=ObservationType.IMAGE, payload_reference="image.jpg")
        with self.assertRaises(ValidationError):
            observation.payload_reference = "replacement.jpg"

    def test_serialization_is_deterministic(self):
        model = self.model()
        self.assertEqual(model.to_json(), model.to_json())

    def test_cross_entity_integrity_rejected(self):
        bad = self.opening.model_copy(update={"offset_along_wall": 3.5})
        with self.assertRaises(ValidationError): CanonicalWorldModel(frames=(self.frame,),planes=(self.plane,),rooms=(self.room_a,self.room_b),walls=(self.wall,),openings=(bad,))
        bad_edge = SpatialRelationship(source_id=self.room_a.room_id,target_id=uuid4(),relationship_type=RelationshipType.ADJACENT_TO)
        with self.assertRaises(ValidationError): CanonicalWorldModel(frames=(self.frame,),planes=(self.plane,),rooms=(self.room_a,self.room_b),walls=(self.wall,),openings=(self.opening,),relationships=(bad_edge,))
        duplicate = self.wall.model_copy()
        with self.assertRaises(ValidationError): CanonicalWorldModel(frames=(self.frame,),planes=(self.plane,),rooms=(self.room_a,self.room_b),walls=(self.wall,duplicate),openings=(self.opening,))
    def test_all_cross_entity_references_rejected(self):
        model = self.model()
        bad_id = uuid4()
        cases = (
            {"cameras": (self.camera.model_copy(update={"capture_id": bad_id}),)},
            {"poses": (self.pose.model_copy(update={"frame_id": bad_id}),)},
            {"observations": (model.observations[0].model_copy(update={"pose_id": bad_id}),)},
            {"observations": (model.observations[0].model_copy(update={"camera_id": bad_id}),)},
            {"geometries": (Geometry3D(frame_id=bad_id, geometry_type=GeometryType.MESH, vertex_buffer_reference="mesh"),)},
            {"planes": (self.plane.model_copy(update={"frame_id": bad_id}),)},
            {"walls": (self.wall.model_copy(update={"supporting_plane_id": bad_id}),)},
            {"rooms": (self.room_a.model_copy(update={"floor_plane_id": bad_id}), self.room_b)},
            {"rooms": (self.room_a.model_copy(update={"ceiling_plane_id": bad_id}), self.room_b)},
            {"rooms": (self.room_a.model_copy(update={"wall_ids": (bad_id,)}), self.room_b)},
            {"rooms": (self.room_a.model_copy(update={"opening_ids": (bad_id,)}), self.room_b)},
            {"openings": (self.opening.model_copy(update={"parent_wall_id": bad_id}),)},
            {"openings": (self.opening.model_copy(update={"connected_room_ids": (bad_id,)}),)},
            {"relationships": (model.relationships[0].model_copy(update={"source_id": bad_id}),)},
            {"relationships": (model.relationships[0].model_copy(update={"target_id": bad_id}),)},
            {"measurements": (model.measurements[0].model_copy(update={"target_entity_id": bad_id}),)},
            {"measurements": (model.measurements[0].model_copy(update={"uncertainty_id": bad_id}),)},
            {"scale_estimates": (model.scale_estimates[0].model_copy(update={"frame_id": bad_id}),)},
        )
        for update in cases:
            with self.subTest(update=update), self.assertRaises(ValidationError):
                CanonicalWorldModel(**{**model.model_dump(), **update})

if __name__ == '__main__': unittest.main()
