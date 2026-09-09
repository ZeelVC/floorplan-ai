from __future__ import annotations
from floorplan_ai.canonical.schema import RelationshipType, SpatialRelationship

def topology(rooms,walls,openings=()):
 edges=[]
 for room in rooms:
  for wall_id in room.wall_ids: edges.append(SpatialRelationship(source_id=room.room_id,target_id=wall_id,relationship_type=RelationshipType.BOUNDED_BY,confidence=1.0))
 for opening in openings:
  edges.append(SpatialRelationship(source_id=opening.parent_wall_id,target_id=opening.opening_id,relationship_type=RelationshipType.HOSTS,confidence=.8))
 return tuple(edges)
