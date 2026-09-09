import pytest
from floorplan_ai.reconstruction.colmap import colmap_pose_to_canonical
def test_identity_and_translation_are_inverted():
 assert colmap_pose_to_canonical((1,0,0,0),(0,0,0)) == ((1.,0.,0.,0.),(0.,1.,0.,0.),(0.,0.,1.,0.),(0.,0.,0.,1.))
 assert colmap_pose_to_canonical((1,0,0,0),(1,2,3))[0][3] == -1
 assert colmap_pose_to_canonical((1,0,0,0),(1,2,3))[1][3] == -2
