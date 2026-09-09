from __future__ import annotations
from math import sqrt
from floorplan_ai.canonical.schema import Measurement, MeasurementType, Provenance

def interval(value,sigma): return (max(0.,value-1.96*sigma),value+1.96*sigma)
def _sigma(entity, scale_sigma=0.):
 residual=(entity.uncertainty.confidence_bounds[1] if getattr(entity,'uncertainty',None) and entity.uncertainty.confidence_bounds else 0.)
 return sqrt(residual*residual+scale_sigma*scale_sigma)
def measurements_for(model):
 out=[]; prov=Provenance(generating_pipeline_stage='measurement')
 scale_sigma=next((s.uncertainty.confidence_bounds[1] for s in model.scale_estimates if s.uncertainty and s.uncertainty.confidence_bounds),0.)
 for wall in model.walls:
  sigma=_sigma(wall,wall.length*scale_sigma); out.append(Measurement(target_entity_id=wall.wall_id,metric_type=MeasurementType.WALL_LENGTH,nominal_value=wall.length,standard_deviation=sigma,interval_95=interval(wall.length,sigma),unit='m',provenance_ref=prov))
 for room in model.rooms:
  pts=room.boundary_polygon_2d; area=abs(sum(pts[i][0]*pts[(i+1)%len(pts)][1]-pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts)))/2); sigma=_sigma(room,area*scale_sigma); out.append(Measurement(target_entity_id=room.room_id,metric_type=MeasurementType.FLOOR_AREA,nominal_value=area,standard_deviation=sigma,interval_95=interval(area,sigma),unit='m2',provenance_ref=prov))
 for opening in model.openings:
  sigma=_sigma(opening,opening.width*scale_sigma); out.append(Measurement(target_entity_id=opening.opening_id,metric_type='OPENING_WIDTH',nominal_value=opening.width,standard_deviation=sigma,interval_95=interval(opening.width,sigma),unit='m',provenance_ref=prov))
 planes={p.plane_id:p for p in model.planes}
 for room in model.rooms:
  if room.floor_plane_id and room.ceiling_plane_id:
   floor,ceiling=planes[room.floor_plane_id],planes[room.ceiling_plane_id]; z1=-floor.distance_offset/floor.normal_vector[2];z2=-ceiling.distance_offset/ceiling.normal_vector[2]; h=abs(z2-z1); sigma=sqrt((floor.rmse or 0)**2+(ceiling.rmse or 0)**2); out.append(Measurement(target_entity_id=room.room_id,metric_type=MeasurementType.CEILING_HEIGHT,nominal_value=h,standard_deviation=sigma,interval_95=interval(h,sigma),unit='m',provenance_ref=prov))
 return tuple(out)
