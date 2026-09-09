from __future__ import annotations
from shapely.geometry import LineString
from shapely.ops import polygonize, unary_union
from floorplan_ai.canonical.schema import Room

def rooms_from_walls(walls, floor_id=None, ceiling_id=None, min_area=.5):
 lines=[LineString((w.start_point_2d,w.end_point_2d)) for w in walls]
 polygons=polygonize(unary_union(lines))
 rooms=[]
 for polygon in sorted(polygons,key=lambda p:(p.centroid.x,p.centroid.y)):
  if not polygon.is_valid or polygon.area<min_area: continue
  boundary=tuple((float(x),float(y)) for x,y in list(polygon.exterior.coords)[:-1])
  ids=tuple(w.wall_id for w in walls if LineString((w.start_point_2d,w.end_point_2d)).distance(polygon.boundary)<1e-6)
  rooms.append(Room(boundary_polygon_2d=boundary,floor_plane_id=floor_id,ceiling_plane_id=ceiling_id,wall_ids=ids))
 return tuple(rooms)
